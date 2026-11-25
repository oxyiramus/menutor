import { beforeEach, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import * as api from '@/api/auth';
vi.mock('@/api/auth');
const user = { id: 1, email: 'a@example.com', nickname: 'A', created_at: '', last_login_at: null };
let useAuthStore: typeof import('@/stores/auth').useAuthStore;
beforeEach(async () => {
    vi.resetModules();
    vi.resetAllMocks();
    vi.mocked(api.getMe).mockResolvedValue(user);
    ({ useAuthStore } = await import('@/stores/auth'));
});
it('login stores session and logout revokes then clears it', async () => {
    vi.mocked(api.login).mockResolvedValue({ access_token: 'access', refresh_token: 'refresh', token_type: 'bearer' });
    const auth = useAuthStore();
    await auth.login({ email: user.email, password: 'password' });
    expect(auth.user).toEqual(user);
    expect(auth.isAuthenticated).toBe(true);
    expect(localStorage.getItem('refresh_token')).toBe('refresh');
    await auth.logout();
    expect(api.logout).toHaveBeenCalledWith({ refresh_token: 'refresh' });
    expect(auth.isAuthenticated).toBe(false);
    expect(auth.user).toBeNull();
    expect(localStorage.getItem('access_token')).toBeNull();
});
it('new store restores persisted session and fetches current user', async () => {
    localStorage.setItem('access_token', 'saved');
    localStorage.setItem('refresh_token', 'saved-refresh');
    setActivePinia(createPinia());
    const auth = useAuthStore();
    await auth.init();
    expect(api.getMe).toHaveBeenCalledWith('saved');
    expect(auth.user).toEqual(user);
});
it('expired access refreshes and loads user', async () => {
    localStorage.setItem('access_token', 'expired');
    localStorage.setItem('refresh_token', 'refresh');
    vi.mocked(api.getMe).mockRejectedValueOnce(new Error('401')).mockResolvedValue(user);
    vi.mocked(api.refreshTokens).mockResolvedValue({ access_token: 'new', refresh_token: 'rotated', token_type: 'bearer' });
    const auth = useAuthStore();
    await auth.init();
    expect(api.refreshTokens).toHaveBeenCalledOnce();
    expect(auth.user).toEqual(user);
    expect(auth.accessToken).toBe('new');
});
it('rejected restored session cannot access protected routes', async () => {
    localStorage.setItem('access_token', 'expired');
    localStorage.setItem('refresh_token', 'revoked');
    vi.mocked(api.getMe).mockRejectedValue(new Error('401'));
    vi.mocked(api.refreshTokens).mockRejectedValue(new Error('401'));
    const auth = useAuthStore();
    await auth.init();
    const router = (await import('@/router')).default;
    await router.push('/products');
    expect(router.currentRoute.value.path).toBe('/login');
    expect(auth.isAuthenticated).toBe(false);
});
it('anonymous protected route redirects; valid session may enter', async () => {
    const router = (await import('@/router')).default;
    await router.push('/recipes');
    expect(router.currentRoute.value.path).toBe('/login');
    const auth = useAuthStore();
    auth.accessToken = 'valid';
    auth.user = user;
    await router.push('/recipes');
    expect(router.currentRoute.value.path).toBe('/recipes');
});
