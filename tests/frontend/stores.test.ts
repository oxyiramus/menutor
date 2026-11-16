import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useProductStore } from '@/stores/products';
import { useRecipeStore } from '@/stores/recipes';
import { useShoppingListStore } from '@/stores/shoppingList';
import { useToastStore } from '@/stores/toast';
import { useCrudView } from '@/composables/useCrudView';
import * as api from '@/api/client';
import { clone, deferred, product, recipe, list, page, error } from './helpers';
vi.mock('@/api/client');
beforeEach(() => { vi.resetAllMocks(); vi.mocked(api.fetchProductCategories).mockResolvedValue([]); vi.mocked(api.fetchRecipeCategories).mockResolvedValue([]); });
describe.each([
    ['products', useProductStore, 'fetchProducts', 'createProduct', 'deleteProduct', 'batchDeleteProducts', product],
    ['recipes', useRecipeStore, 'fetchRecipes', 'createRecipe', 'deleteRecipe', 'batchDeleteRecipes', recipe],
] as const)('%s behavior', (_name, factory, fetchName, createName, deleteName, batchName, entity) => {
    it('search/category reset page and pickers retain complete list', async () => {
        vi.mocked(api[fetchName]).mockImplementation(async (params: any) => page(params ? [entity(1)] : [entity(1), entity(2)]) as any);
        const store = factory();
        await store.load();
        await store.setPage(3);
        await store.setFilters('APPLE', 2);
        expect(store.page).toBe(1);
        expect(api[fetchName]).toHaveBeenLastCalledWith({ page: 1, search: 'APPLE', categoryId: 2 });
        expect(store.allItems.map(x => x.id)).toEqual([1, 2]);
        expect(store.items.map(x => x.id)).toEqual([1]);
    });
    it('late old response cannot replace the new filter result', async () => {
        const old = deferred(), recent = deferred();
        vi.mocked(api[fetchName]).mockReturnValueOnce(old.promise).mockReturnValueOnce(recent.promise);
        const store = factory();
        const first = store.setFilters('old', null);
        const second = store.setFilters('new', null);
        recent.resolve(page([entity(2)]));
        await second;
        old.resolve(page([entity(1)]));
        await first;
        expect(store.items.map(x => x.id)).toEqual([2]);
    });
    it('deleting last item returns to an existing page', async () => {
        vi.mocked(api[fetchName]).mockImplementation(async (params: any) => page(params?.page === 2 ? [] : [entity(1)], 1) as any);
        const store = factory();
        store.page = 2;
        store.items = [entity(2)] as any;
        await store.remove(2);
        expect(store.page).toBe(1);
        expect(store.items.map(x => x.id)).toEqual([1]);
    });
    it('successful real store create closes form and exposes persisted response', async () => {
        let persisted: any[] = [];
        vi.mocked(api[createName]).mockImplementation(async (body: any) => { persisted = [{ ...body, id: 7 }]; return clone(persisted[0]); });
        vi.mocked(api[fetchName]).mockImplementation(async () => page(clone(persisted)) as any);
        const store = factory(), view = useCrudView(store as any);
        view.openNew();
        await view.onSave({ ...entity(7), name: 'Saved' }, null);
        expect(view.formOpen.value).toBe(false);
        expect(view.selectedItem.value).toMatchObject({ id: 7, name: 'Saved' });
    });
    it('failed save preserves form and selected data and shows error', async () => {
        vi.mocked(api[createName]).mockRejectedValue(error());
        const toast = vi.spyOn(useToastStore(), 'show');
        const store = factory(), view = useCrudView(store as any);
        view.openNew();
        await view.onSave(entity(), null);
        expect(view.formOpen.value).toBe(true);
        expect(store.items).toEqual([]);
        expect(toast).toHaveBeenLastCalledWith('Server failure', 'error');
    });
    it('canceling deletion does not send a request', () => {
        const view = useCrudView(factory() as any);
        view.onRemove(1);
        view.confirmDeleteOpen.value = false;
        expect(api[deleteName]).not.toHaveBeenCalled();
    });
    it.each(['single', 'batch'])('failed %s delete keeps records and never announces success', async (mode) => {
        vi.mocked(api[deleteName]).mockRejectedValue(error());
        vi.mocked(api[batchName]).mockRejectedValue(error());
        const store = factory();
        store.items = [entity()] as any;
        const view = useCrudView(store as any);
        const toast = vi.spyOn(useToastStore(), 'show');
        if (mode === 'single') {
            view.onSelect(1);
            view.onRemove(1);
            await view.onConfirmDelete();
        }
        else {
            view.selection.selected.value = new Set([1]);
            await view.onConfirmBatchDelete();
            expect(view.selection.selected.value.has(1)).toBe(true);
        }
        expect(store.items).toHaveLength(1);
        expect(toast).toHaveBeenLastCalledWith('Server failure', 'error');
        expect(toast.mock.calls.some(x => x[1] === 'success')).toBe(false);
    });
});
describe('shopping persistence', () => {
    beforeEach(() => { vi.mocked(api.generateShoppingList).mockResolvedValue(list() as any); vi.mocked(api.fetchSavedShoppingList).mockResolvedValue(list() as any); });
    it('generate, edit amount/price, save and reload retain values', async () => {
        const store = useShoppingListStore();
        await store.generate(1);
        store.updateQuantity(1, 3);
        store.updatePrice(1, 12.5);
        expect(store.isDirty).toBe(true);
        let saved: any;
        vi.mocked(api.updateSavedShoppingList).mockImplementation(async (_id, body) => { const row = body.items[0]!; saved = list(); Object.assign(saved.items[0], { buy_quantity: { amount: row.buy_quantity_amount, unit: row.buy_quantity_unit }, cost: { amount: row.cost_amount.toFixed(2), currency: row.cost_currency }, buy_quantity_overridden: true }); return clone(saved); });
        await store.saveChanges();
        expect(store.isDirty).toBe(false);
        vi.mocked(api.fetchSavedShoppingList).mockImplementation(async () => clone(saved));
        await store.loadList(1);
        expect(store.items[0]?.buy_quantity.amount).toBe(3);
        expect(store.items[0]?.cost.amount).toBe('37.50');
    });
    it('purchased-only toggle stays clean', async () => {
        const store = useShoppingListStore();
        await store.loadList(1);
        const server = list();
        server.items[0]!.purchased = true;
        vi.mocked(api.toggleItemPurchasedApi).mockResolvedValue(server as any);
        await store.togglePurchased(1);
        expect(store.items[0]?.purchased).toBe(true);
        expect(store.isDirty).toBe(false);
    });
    it('toggle preserves unsaved quantity and price changes', async () => {
        const store = useShoppingListStore();
        await store.loadList(1);
        store.updateQuantity(1, 3);
        store.updatePrice(1, 12.5);
        const server = list();
        server.items[0]!.purchased = true;
        vi.mocked(api.toggleItemPurchasedApi).mockResolvedValue(server as any);
        await store.togglePurchased(1);
        expect(store.items[0]?.buy_quantity.amount).toBe(3);
        expect(store.items[0]?.cost.amount).toBe('37.50');
        expect(store.isDirty).toBe(true);
    });
    it('failed save retains edits and dirty state', async () => {
        const store = useShoppingListStore();
        await store.loadList(1);
        store.updateQuantity(1, 3);
        vi.mocked(api.updateSavedShoppingList).mockRejectedValue(error());
        await store.saveChanges();
        expect(store.items[0]?.buy_quantity.amount).toBe(3);
        expect(store.isDirty).toBe(true);
    });
});
