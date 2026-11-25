import { beforeEach, expect, it, vi } from 'vitest';
import { mount, flushPromises } from '@vue/test-utils';
import ImportModal from '@/components/ui/ImportModal.vue';
import ExportModal from '@/components/ui/ExportModal.vue';
import { downloadBlob } from '@/composables/useFileDownload';
import * as api from '@/api/client';
import { error } from './helpers';
vi.mock('@/api/client');
const global = { stubs: { teleport: true } };
const button = (w: any, label: string) => w.findAll('button').find((x: any) => x.text() === label)!;
async function choose(w: any, name = 'recipes.json') {
    const file = new File(['[]'], name, { type: 'application/json' });
    Object.defineProperty(w.get('input[type=file]').element, 'files', { configurable: true, value: [file] });
    await w.get('input').trigger('change');
    return file;
}
beforeEach(() => vi.resetAllMocks());
it('import displays created/updated counts and warnings after actual file selection', async () => {
    const result = { created: 2, updated: 1, errors: ['Unknown subrecipe skipped'] };
    vi.mocked(api.importEntities).mockResolvedValue(result);
    const w = mount(ImportModal, { props: { open: true, entityType: 'recipes', allowedExtensions: ['json'] }, global });
    const file = await choose(w);
    await button(w, 'Импорт').trigger('click');
    await flushPromises();
    expect(api.importEntities).toHaveBeenCalledWith('recipes', 'json', file);
    expect(w.text()).toContain('Создано: 2, Обновлено: 1');
    expect(w.text()).toContain(result.errors[0]);
    expect(w.emitted('imported')).toEqual([[result]]);
});
it('invalid extension is visible and cannot be submitted', async () => {
    const w = mount(ImportModal, { props: { open: true, entityType: 'recipes', allowedExtensions: ['json'] }, global });
    await choose(w, 'bad.exe');
    expect(w.text()).toContain('Недопустимый формат');
    expect(button(w, 'Импорт').attributes('disabled')).toBeDefined();
    expect(api.importEntities).not.toHaveBeenCalled();
});
it('server import error is visible without imported event', async () => {
    vi.mocked(api.importEntities).mockRejectedValue(error());
    const w = mount(ImportModal, { props: { open: true, entityType: 'recipes', allowedExtensions: ['json'] }, global });
    await choose(w);
    await button(w, 'Импорт').trigger('click');
    await flushPromises();
    expect(w.text()).toContain('Server failure');
    expect(w.emitted('imported')).toBeUndefined();
});
it.each([true, false])('export success=%s downloads only successful response', async (success) => {
    vi.stubGlobal('URL', class extends URL {
        static createObjectURL = vi.fn(() => 'blob:test');
        static revokeObjectURL = vi.fn();
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => { });
    if (success)
        vi.mocked(api.exportEntities).mockResolvedValue(new Blob(['[]']));
    else
        vi.mocked(api.exportEntities).mockRejectedValue(error());
    const w = mount(ExportModal, { props: { open: true, entityType: 'recipes', formats: [{ value: 'json', label: 'JSON' }], selectedIds: [7] }, global });
    await button(w, 'Скачать').trigger('click');
    await flushPromises();
    expect(api.exportEntities).toHaveBeenCalledWith('recipes', 'json', [7]);
    expect(click).toHaveBeenCalledTimes(success ? 1 : 0);
    if (success)
        expect(w.emitted('close')).toEqual([[]]);
    else {
        expect(w.text()).toContain('Server failure');
        expect(w.emitted('close')).toBeUndefined();
    }
    vi.unstubAllGlobals();
});
it('download uses filename and revokes created URL', async () => {
    vi.useFakeTimers();
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test'), revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => { });
    let filename = '';
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { filename = this.download; });
    const blob = new Blob(['content']);
    downloadBlob(blob, 'recipes.json');
    expect(create).toHaveBeenCalledWith(blob);
    expect(filename).toBe('recipes.json');
    await vi.advanceTimersByTimeAsync(100);
    expect(revoke).toHaveBeenCalledWith('blob:test');
    expect(document.querySelector('a')).toBeNull();
});
