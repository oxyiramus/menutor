import { expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import MemberSelectorSheet from '@/components/ui/MemberSelectorSheet.vue';
import MergedSlotSheet from '@/components/ui/MergedSlotSheet.vue';
import MobileDayView from '@/components/planner/MobileDayView.vue';
import MobileMealView from '@/components/planner/MobileMealView.vue';
import MobileWeekView from '@/components/planner/MobileWeekView.vue';
import GridCell from '@/components/planner/GridCell.vue';
import { member, slot } from './helpers';
const global = { stubs: { teleport: true } };
const button = (w: any, text: string) => w.findAll('button').find((b: any) => b.text() === text)!;
it.each(['apply', 'cancel'])('member sheet %s keeps edits local until confirmation', async (action) => {
    const selected = [1], w = mount(MemberSelectorSheet, { props: { members: [member(1), member(2)], selectedIds: selected }, global });
    await w.findAll('input')[1]!.setValue(true);
    expect(selected).toEqual([1]);
    await button(w, action === 'apply' ? 'Применить' : 'Отмена').trigger('click');
    if (action === 'apply')
        expect(w.emitted('apply')).toEqual([[[1, 2]]]);
    else {
        expect(w.emitted('cancel')).toEqual([[]]);
        expect(w.emitted('apply')).toBeUndefined();
    }
});
it('merged sheet edits/removes the correct participant slot and close changes nothing', async () => {
    const slots = [slot([1]), { ...slot([2]), position: 1 }], w = mount(MergedSlotSheet, { props: { recipeName: 'Bread', totalServings: 4, slots, familyMembers: [member(1), member(2)] }, global });
    await w.findAll('button').filter(b => b.text() === 'Ред.')[1]!.trigger('click');
    expect(w.emitted('edit-slot')).toEqual([[slots[1]]]);
    await w.findAll('button').filter(b => b.text() === '×')[0]!.trigger('click');
    expect(w.emitted('remove-slot')).toEqual([[slots[0]]]);
    await button(w, 'Закрыть').trigger('click');
    expect(w.emitted('close')).toEqual([[]]);
    expect(slots.map(x => x.member_ids)).toEqual([[1], [2]]);
});
it.each([MobileDayView, MobileMealView])('mobile planner forwards cell actions with exact target coordinates', async (Component) => {
    const w = mount(Component as any, { props: { currentDay: 2, currentMealTypeId: 1, slots: [slot()], mealTypes: [{ id: 1, name: 'Breakfast' }], recipeNames: { 1: 'Bread' }, productNames: {}, activeMemberIds: new Set([1]), familyMembers: [member()] }, global: { stubs: { GridCell: true } } });
    const cell = w.getComponent(GridCell);
    cell.vm.$emit('add-item', { type: 'recipe', id: 7 });
    cell.vm.$emit('remove-item', { recipe_id: 1 });
    cell.vm.$emit('edit-item', slot());
    cell.vm.$emit('open-picker');
    expect(w.emitted('add-item')).toEqual([[2, 1, { type: 'recipe', id: 7 }]]);
    expect(w.emitted('remove-item')).toEqual([[2, 1, { recipe_id: 1 }]]);
    expect(w.emitted('edit-item')).toEqual([[slot()]]);
    expect(w.emitted('open-picker')).toEqual([[2, 1]]);
});
it('mobile week renders visible member dishes and allows day navigation', async () => {
    const w = mount(MobileWeekView, { props: { slots: [slot([1]), { ...slot([2]), recipe_id: 2 }], mealTypes: [{ id: 1, name: 'Breakfast' }], recipeNames: { 1: 'Visible', 2: 'Hidden' }, productNames: {}, activeMemberIds: new Set([1]) } });
    expect(w.text()).toContain('Visible');
    expect(w.text()).not.toContain('Hidden');
    await w.findAll('button')[2]!.trigger('click');
    expect(w.emitted('select-day')).toEqual([[2]]);
});
it.each(['cancel', 'confirm'])('shared confirmation dialog %s emits only the chosen action', async (action) => {
    const ConfirmDialog = (await import('@/components/ui/ConfirmDialog.vue')).default;
    const w = mount(ConfirmDialog, { props: { open: true, message: 'Delete this dish?' }, global });
    await button(w, action === 'cancel' ? 'Отмена' : 'Да').trigger('click');
    expect(w.emitted(action)).toEqual([[]]);
    expect(w.emitted(action === 'cancel' ? 'confirm' : 'cancel')).toBeUndefined();
});

it.each([MobileDayView, MobileMealView])('real mobile add control opens picker for visible coordinates', async Component => {
    const w = mount(Component as any, { props: { currentDay: 2, currentMealTypeId: 1, slots: [], mealTypes: [{ id: 1, name: 'Breakfast' }], recipeNames: {}, productNames: {}, activeMemberIds: new Set([1]), familyMembers: [member()] }, global });
    await w.get('button[aria-label="Добавить"]').trigger('click');
    expect(w.emitted('open-picker')).toEqual([[2, 1]]);
});
