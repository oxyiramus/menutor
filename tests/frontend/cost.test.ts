import { beforeEach, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import CostSummaryBlock from '@/components/recipes/CostSummaryBlock.vue';
import CostBadge from '@/components/recipes/CostBadge.vue';
import FlattenedProductList from '@/components/recipes/FlattenedProductList.vue';
import * as api from '@/api/client';
import { deferred } from './helpers';
vi.mock('@/api/client');
const ingredient = (amount = 100) => ({ product_id: 1, sub_recipe_id: null, quantity_amount: amount, quantity_unit: 'g' });
const props = () => ({ ingredients: [ingredient()], servings: 2, totalPieces: null, piecesPerPortion: null, isPiecesMode: false });
const cost = (value: number | null, partial = false) => ({ cost_per_portion: value, cost_currency: value == null ? null : 'RUB', cost_is_partial: partial, total_cost: value == null ? null : value * 2, computed_servings: 2, ingredient_costs: [] });
beforeEach(() => vi.resetAllMocks());
it.each([[10, false, '10.00'], [10, true, 'не полностью'], [null, false, 'не может быть рассчитана']] as const)('cost %s partial %s has distinguishable output', async (value, partial, text) => {
    vi.useFakeTimers();
    vi.mocked(api.previewRecipeCost).mockResolvedValue(cost(value, partial));
    const w = mount(CostSummaryBlock, { props: props() });
    await vi.advanceTimersByTimeAsync(300);
    await flushPromises();
    expect(w.text()).toContain(text);
});
it.each([false, true])('badge partial=%s has warning exactly when partial', partial => {
    const w = mount(CostBadge, { props: { costPerPortion: 10, costIsPartial: partial, badge: true } });
    expect(w.text()).toContain('10.00');
    expect(w.find('svg').exists()).toBe(partial);
});
it('badge absent cost is distinguishable from zero cost', async () => {
    const w = mount(CostBadge, { props: { costPerPortion: null, costIsPartial: false } });
    expect(w.text()).toBe('--');
    await w.setProps({ costPerPortion: 0 });
    expect(w.text()).toContain('0.00');
});
it('cost preview sends current pieces data and ignores stale responses', async () => {
    vi.useFakeTimers();
    const old = deferred(), fresh = deferred();
    vi.mocked(api.previewRecipeCost).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const w = mount(CostSummaryBlock, { props: props() });
    await vi.advanceTimersByTimeAsync(300);
    await w.setProps({ ingredients: [ingredient(300)], isPiecesMode: true, totalPieces: 8, piecesPerPortion: 2 });
    await vi.advanceTimersByTimeAsync(300);
    expect(api.previewRecipeCost).toHaveBeenLastCalledWith(expect.objectContaining({ ingredients: [ingredient(300)], total_pieces: 8, pieces_per_portion: 2, servings: 4 }));
    fresh.resolve(cost(30));
    await flushPromises();
    old.resolve(cost(10));
    await flushPromises();
    expect(w.text()).toContain('30.00');
    expect(w.text()).not.toContain('10.00');
});
it('flattened products refresh uses edited ingredient values', async () => {
    vi.mocked(api.previewFlattenedProducts).mockResolvedValueOnce([{ product_id: 1, product_name: 'Flour', quantity_amount: 100, quantity_unit: 'g' }]).mockResolvedValueOnce([{ product_id: 1, product_name: 'Flour', quantity_amount: 300, quantity_unit: 'g' }]);
    const w = mount(FlattenedProductList, { props: { recipeId: 1, ingredients: [ingredient()], isDirty: false } });
    await w.get('button').trigger('click');
    await flushPromises();
    expect(w.text()).toContain('100');
    await w.setProps({ ingredients: [ingredient(300)], isDirty: true });
    await w.get('[title="Пересчитать продукты"]').trigger('click');
    await flushPromises();
    expect(api.previewFlattenedProducts).toHaveBeenLastCalledWith(1, [ingredient(300)]);
    expect(w.text()).toContain('300');
});
