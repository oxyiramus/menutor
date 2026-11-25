import { expect, it, vi } from 'vitest';
import axios from 'axios';
import { deferred } from './helpers';
async function harness(always401 = false) {
    vi.resetModules();
    localStorage.setItem('access_token', 'old');
    localStorage.setItem('refresh_token', 'refresh');
    const create = axios.create.bind(axios);
    let instance: any;
    vi.spyOn(axios, 'create').mockImplementation(options => { instance = create(options); return instance; });
    const refresh = deferred();
    const refreshCall = vi.spyOn(axios, 'post').mockReturnValue(refresh.promise);
    const api = await import('@/api/client');
    let requests = 0;
    instance.defaults.adapter = async (config: any) => {
        requests++;
        if (!always401 && config.headers.Authorization === 'Bearer new')
            return { data: { items: [], total: 0 }, status: 200, headers: {}, config };
        throw { config, response: { status: 401 } };
    };
    return { api, refresh, refreshCall, requests: () => requests };
}
it('concurrent 401s share one refresh and both retry with new token', async () => {
    const h = await harness();
    const first = h.api.fetchProducts();
    const second = h.api.fetchRecipes();
    await vi.waitFor(() => expect(h.refreshCall).toHaveBeenCalledOnce());
    h.refresh.resolve({ data: { access_token: 'new', refresh_token: 'rotated' } });
    await Promise.all([first, second]);
    expect(h.refreshCall).toHaveBeenCalledOnce();
    expect(h.requests()).toBe(4);
});
it('refresh refusal settles every waiting request', async () => {
    const h = await harness();
    const outcomes: string[] = [];
    const requests = [h.api.fetchProducts(), h.api.fetchRecipes()].map(p => p.then(() => outcomes.push('ok'), () => outcomes.push('rejected')));
    await vi.waitFor(() => expect(h.refreshCall).toHaveBeenCalledOnce());
    h.refresh.reject(new Error('revoked'));
    await vi.waitFor(() => expect(outcomes).toEqual(['rejected', 'rejected']), { timeout: 300 });
    await Promise.all(requests);
    expect(localStorage.getItem('access_token')).toBeNull();
});
it('401 after successful refresh terminates without another refresh', async () => {
    const h = await harness(true);
    const request = h.api.fetchProducts().catch(e => e);
    await vi.waitFor(() => expect(h.refreshCall).toHaveBeenCalledOnce());
    h.refresh.resolve({ data: { access_token: 'new', refresh_token: 'rotated' } });
    const failure = await request;
    expect(failure.response.status).toBe(401);
    expect(h.requests()).toBe(2);
    expect(h.refreshCall).toHaveBeenCalledOnce();
});
