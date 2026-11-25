import { beforeEach, expect, it, vi } from 'vitest';
import { ref } from 'vue';
import { useMenuStore } from '@/stores/menus';
import { usePlannerClipboard } from '@/composables/usePlannerClipboard';
import { usePreferenceFilter } from '@/composables/usePreferenceFilter';
import { isSlotVisible } from '@/utils/slotVisibility';
import * as api from '@/api/client';
import { slot, recipe, product, member, clone, error } from './helpers';
vi.mock('@/api/client');
beforeEach(() => vi.resetAllMocks());
it('copy preserves members independently of source and repeated paste', () => {
    const clipboard = usePlannerClipboard(), source = [slot([1])];
    clipboard.copySlot(source);
    source[0]!.member_ids.push(2);
    expect(clipboard.pasteSlot()?.[0]?.member_ids).toEqual([1]);
    clipboard.pasteSlot()![0]!.member_ids.push(3);
    expect(clipboard.pasteSlot()?.[0]?.member_ids).toEqual([1]);
});
it('add, move, reorder, remove retain participant identity', async () => {
    let server: any = { id: 1, name: 'Week', slots: [] };
    vi.mocked(api.addSlot).mockImplementation(async (_id, row) => { const i = server.slots.findIndex((x: any) => x.recipe_id === row.recipe_id && x.day === row.day && JSON.stringify(x.member_ids) === JSON.stringify(row.member_ids)); if (i < 0)
        server.slots.push(clone(row));
    else
        server.slots[i] = clone(row); return clone(server); });
    const store = useMenuStore();
    store.menus = [clone(server)];
    store.selectedId = 1;
    await store.addSlotToMenu(slot([1]));
    await store.addSlotToMenu(slot([2]));
    expect(store.current?.slots).toHaveLength(2);
    vi.mocked(api.moveSlotApi).mockImplementation(async (_id, data) => { const row = server.slots.find((x: any) => x.position === data.position); Object.assign(row, { day: data.to_day, meal_type_id: data.to_meal_type_id, position: data.to_position }); return clone(server); });
    // Distinct positions ensure selection is observable at the request boundary.
    server.slots[1].position = 1;
    store.menus = [clone(server)];
    await store.moveSlot(store.current!.slots[1]!, 1, 2, 0);
    expect(api.moveSlotApi).toHaveBeenCalledWith(1, expect.objectContaining({ position: 1, to_day: 1, to_meal_type_id: 2 }));
    expect(store.current!.slots.find(x => x.member_ids.includes(2))?.day).toBe(1);
    await store.reorderSlots(0, 1, [slot([2]), slot([1])]);
    expect(api.addSlot).toHaveBeenLastCalledWith(1, expect.objectContaining({ member_ids: [1], position: 1 }));
    vi.mocked(api.removeSlot).mockResolvedValue({ ...server, slots: [slot([1])] });
    await store.removeSlotFromMenu({ day: 0, meal_type_id: 1, recipe_id: 1, position: 0 });
    expect(store.current!.slots.map(x => x.member_ids)).toEqual([[1]]);
});
it.each(['addSlotToMenu', 'moveSlot', 'reorderSlots', 'removeSlotFromMenu'] as const)('failed %s preserves current menu', async (action) => {
    for (const fn of [api.addSlot, api.moveSlotApi, api.removeSlot])
        vi.mocked(fn).mockRejectedValue(error());
    const store = useMenuStore();
    const before = { id: 1, name: 'Week', slots: [slot()] };
    store.menus = [clone(before)];
    store.selectedId = 1;
    const call = action === 'addSlotToMenu' ? store.addSlotToMenu(slot()) : action === 'moveSlot' ? store.moveSlot(slot(), 1, 2, 0) : action === 'reorderSlots' ? store.reorderSlots(0, 1, [slot()]) : store.removeSlotFromMenu({ day: 0, meal_type_id: 1, recipe_id: 1 });
    await expect(call).rejects.toBeDefined();
    expect(store.current).toEqual(before);
});
it('nested allergen reacts to selected participants and slot visibility', () => {
    const child = { ...recipe(2), ingredients: [{ product_id: 1, sub_recipe_id: null, quantity_amount: 10, quantity_unit: 'g', order: 0 }] };
    const parent = { ...recipe(), ingredients: [{ product_id: null, sub_recipe_id: 2, quantity_amount: 1, quantity_unit: 'serv', order: 0 }] };
    const active = ref(new Set([1]));
    const filter = usePreferenceFilter(active, ref([member(1), member(2, [])]), ref([{ id: 1, name: 'Allergy', type: 'ALLERGY', mode: 'BLOCKED', product_ids: [1], category_ids: [], recipe_category_ids: [] }]) as any, ref([parent, child]) as any, ref([product()]));
    expect([...filter.blockedRecipeIds.value].sort()).toEqual([1, 2]);
    expect(isSlotVisible(slot([1]), active.value)).toBe(true);
    active.value = new Set([2]);
    expect(filter.blockedRecipeIds.value.size).toBe(0);
    expect(isSlotVisible(slot([1]), active.value)).toBe(false);
    expect(isSlotVisible(slot([]), active.value)).toBe(true);
});
it.each([['BLOCKED', [1], true], ['BLOCKED', [2], false], ['ALLOWED', [1], false], ['ALLOWED', [2], true]] as const)('%s recipe categories %j follow backend contract', (mode, categories, blocked) => {
    const filter = usePreferenceFilter(ref(new Set([1])), ref([member()]), ref([{ id: 1, name: 'Diet', type: 'CATEGORY_BASED', mode, product_ids: [], category_ids: [], recipe_category_ids: [...categories] }]) as any, ref([recipe()]), ref([product()]));
    expect(filter.blockedRecipeIds.value.has(1)).toBe(blocked);
});
it('mutating pasted members does not change the clipboard for the next paste', () => {
    const clipboard = usePlannerClipboard();
    clipboard.copySlot([slot([1])]);
    clipboard.pasteSlot()![0]!.member_ids.push(2);
    expect(clipboard.pasteSlot()![0]!.member_ids).toEqual([1]);
});
it.each([['BLOCKED', [1], true], ['BLOCKED', [2], false], ['ALLOWED', [1], false], ['ALLOWED', [2], true]] as const)('%s product categories %j apply to nested products', (mode, categories, blocked) => {
    const child = { ...recipe(2), ingredients: [{ product_id: 1, sub_recipe_id: null, quantity_amount: 10, quantity_unit: 'g', order: 0 }] };
    const parent = { ...recipe(), ingredients: [{ product_id: null, sub_recipe_id: 2, quantity_amount: 1, quantity_unit: 'serv', order: 0 }] };
    const filter = usePreferenceFilter(ref(new Set([1])), ref([member()]), ref([{ id: 1, name: 'Diet', type: 'CATEGORY_BASED', mode, product_ids: [], category_ids: [...categories], recipe_category_ids: [] }]) as any, ref([parent, child]) as any, ref([product()]));
    expect(filter.blockedRecipeIds.value.has(1)).toBe(blocked);
    expect(filter.blockedProductIds.value.has(1)).toBe(blocked);
});
