import { afterEach, beforeEach, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { enableAutoUnmount } from '@vue/test-utils';
enableAutoUnmount(afterEach);
beforeEach(() => { localStorage.clear(); setActivePinia(createPinia()); });
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); document.body.innerHTML = ''; });
