export const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));
export function deferred<T = any>() {
    let resolve!: (x: T) => void, reject!: (x?: any) => void;
    const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
    return { promise, resolve, reject };
}
export const product = (id = 1) => ({ id, name: `Product ${id}`, category_id: 1, recipe_unit: 'g', purchase_unit: 'kg', price_amount: '80', price_currency: 'RUB', conversion_factor: 1000, brand: '', supplier: '' });
export const recipe = (id = 1) => ({ id, name: `Recipe ${id}`, category_id: 1, servings: 2, weight: 200, ingredients: [], steps: [], total_pieces: null, pieces_per_portion: null, link: null, comment: null });
export const slot = (members = [1]) => ({ day: 0, meal_type_id: 1, recipe_id: 1, product_id: null, servings_override: 2, pieces_override: null, position: 0, member_ids: members });
export const member = (id = 1, preference_ids = [1]) => ({ id, name: `Member ${id}`, portion_multiplier: 1, preference_ids, comment: '' });
export const list = () => ({ id: 1, name: 'Shopping', source_menu_id: 1, created_at: '2026-01-01', updated_at: '2026-01-01', items: [{ id: 1, product_id: 1, product_name: 'Flour', category: 'Food', quantity: { amount: .2, unit: 'kg' }, buy_quantity: { amount: 1, unit: 'kg' }, buy_quantity_overridden: false, cost: { amount: '80.00', currency: 'RUB' }, purchased: false, recipe_quantity: { amount: 200, unit: 'g' }, item_order: 0 }] });
export const page = (items: any[], total = items.length) => ({ items, total, page: 1, page_size: 20 });
export const error = () => ({ response: { status: 500, data: { detail: 'Server failure' } } });
