import { expect, it } from 'vitest';
import { useCategoryFilter } from '@/composables/useCategoryFilter';
it('uppercase search matches mixed-case names while retaining category restriction', () => {
    const filter = useCategoryFilter();
    const items = [{ id: 1, name: 'Apple', category_id: 1 }, { id: 2, name: 'apple pie', category_id: 2 }, { id: 3, name: 'Banana', category_id: 1 }];
    expect(filter.applyFilter(items, 'APPLE').map(x => x.id)).toEqual([1, 2]);
    filter.categoryFilter.value = 1;
    expect(filter.applyFilter(items, 'APPLE').map(x => x.id)).toEqual([1]);
});
