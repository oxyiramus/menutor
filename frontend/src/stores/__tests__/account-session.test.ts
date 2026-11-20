import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '@/App.vue'
import { AxiosError, type AxiosAdapter } from 'axios'
import { createPinia, disposePinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { SavedShoppingListItem } from '@/api/types'
import { useToastStore } from '../toast'
import { useAuthStore } from '../auth'
import { useFamilyStore } from '../family'
import { useMenuStore } from '../menus'
import { useProductStore } from '../products'
import { useRecipeStore } from '../recipes'
import { useShoppingListStore } from '../shoppingList'
import { useCategoryStore } from '../categories'
import { useMealTypeStore } from '../mealTypes'
import { usePreferencesStore } from '../preferences'
import { useRecipeSettingsStore } from '../recipeSettings'
import { usePlannerClipboard } from '@/composables/usePlannerClipboard'
import { useContextMenu } from '@/composables/useContextMenu'

const transport = vi.hoisted(() => ({ send: vi.fn<AxiosAdapter>() }))
vi.mock('axios', async (importOriginal) => {
  const actual = await importOriginal<typeof import('axios')>()
  actual.default.defaults.adapter = transport.send
  return actual
})

function pause() {
  let release!: () => void
  const waiting = new Promise<void>((resolve) => { release = resolve })
  return { waiting, release }
}

let pinia: ReturnType<typeof createPinia>

beforeEach(() => {
  localStorage.clear()
  pinia = createPinia()
  setActivePinia(pinia)
  transport.send.mockReset()
  window.history.replaceState({}, '', '/login')
})

afterEach(() => disposePinia(pinia))

function setupTransport() {
  const started = pause()
  const finish = pause()
  const refreshStarted = pause()
  const refreshFinish = pause()
  let delayRefresh = false
  let delay = false
  let unauthorized = false
  let refreshFails = true
  transport.send.mockImplementation(async (config) => {
    const url = config.url ?? ''
    const account = String(config.headers.Authorization).startsWith('Bearer A') ? 'A' : 'B'
    let data: unknown
    if (url === '/login') {
      const { email } = JSON.parse(config.data)
      const name = email.split('@')[0]
      data = { access_token: name, refresh_token: `refresh-${name}` }
    } else if (url === '/me') {
      data = { id: account === 'A' ? 1 : 2, nickname: account }
    } else if (url === '/logout') {
      data = {}
    } else if (url.endsWith('/refresh')) {
      refreshStarted.release()
      if (delayRefresh) await refreshFinish.waiting
      if (refreshFails) throw new AxiosError('Refresh rejected', undefined, config)
      data = { access_token: 'A-new', refresh_token: 'refresh-A-new' }
    } else {
      if (delay && account === 'A') {
        started.release()
        await finish.waiting
      }
      if (unauthorized && config.headers.Authorization === 'Bearer A') {
        throw new AxiosError('Unauthorized', undefined, config, undefined, {
          data: {}, status: 401, statusText: '', headers: {}, config,
        })
      }
      const item = { id: 1, name: account, items: [], slots: [], created_at: '' }
      data = url === '/shopping-lists/1' || url === '/menus/1' ? item : [item]
      if (url === '/products' || url === '/recipes') {
        data = { items: [item], total: 1, page_size: 20 }
      }
    }
    return { data, status: 200, statusText: '', headers: {}, config }
  })
  return {
    started, finish, refreshStarted, refreshFinish,
    delayRefresh: () => { delayRefresh = true },
    delay: (value: boolean) => { delay = value },
    unauthorized: () => { unauthorized = true },
    refreshSucceeds: () => { refreshFails = false },
  }
}

function stores() {
  return {
    auth: useAuthStore(),
    shopping: useShoppingListStore(),
    products: useProductStore(),
    recipes: useRecipeStore(),
    menus: useMenuStore(),
    family: useFamilyStore(),
    categories: useCategoryStore(),
    mealTypes: useMealTypeStore(),
    preferences: usePreferencesStore(),
  }
}

type Stores = ReturnType<typeof stores>

const login = (s: Stores, name: string) =>
  s.auth.login({ email: `${name}@example.test`, password: 'test' })

async function load(s: Stores) {
  await Promise.all([
    s.shopping.loadLists(), s.shopping.loadList(1), s.products.load(), s.recipes.load(),
    s.menus.load(), s.menus.select(1), s.family.load(), s.categories.load('product'),
    s.categories.load('recipe'), s.mealTypes.load(), s.preferences.load(),
  ])
}

function expectAccount(s: Stores, name: string) {
  expect(s.shopping.data?.name).toBe(name)
  expect(s.menus.current?.name).toBe(name)
  for (const list of [
    s.shopping.savedLists, s.products.items, s.products.allItems, s.products.categories,
    s.recipes.items, s.recipes.allItems, s.recipes.categories, s.menus.menus, s.family.items,
    s.categories.productCategories, s.categories.recipeCategories, s.mealTypes.items,
    s.preferences.items,
  ]) {
    expect(list.map((item) => item.name)).toEqual([name])
  }
}

function expectEmpty(s: Stores) {
  expect(s.auth.isAuthenticated).toBe(false)
  expect(s.shopping.data).toBeNull()
  expect(s.shopping.currentListId).toBeNull()
  expect(s.shopping.isDirty).toBe(false)
  expect(s.menus.selectedId).toBeNull()
  for (const list of [
    s.shopping.savedLists, s.products.items, s.products.allItems, s.products.categories,
    s.recipes.items, s.recipes.allItems, s.recipes.categories, s.menus.menus, s.family.items,
    s.categories.productCategories, s.categories.recipeCategories, s.mealTypes.items,
    s.preferences.items,
  ]) {
    expect(list).toEqual([])
  }
}

describe('account session isolation', () => {
  it('clears stores, selections, drafts and buffers when switching from A to B', async () => {
    setupTransport()
    const s = stores()
    await login(s, 'A')
    await load(s)
    expectAccount(s, 'A')
    const quantity = { amount: 1, unit: 'g' }
    const draft: SavedShoppingListItem = {
      id: 1, product_id: 1, product_name: 'A', category: 'A', quantity, buy_quantity: quantity,
      buy_quantity_overridden: false, cost: { amount: '0', currency: 'RUB' },
      purchased: false, recipe_quantity: null, item_order: 0,
    }
    s.shopping.addItem(draft)
    expect(s.shopping.isDirty).toBe(true)
    const clipboard = usePlannerClipboard()
    clipboard.copySlot([{ day: 1, meal_type_id: 1, product_id: 1 }])
    const context = useContextMenu()
    context.open(0, 0, [{ label: 'A', action: vi.fn() }])
    const display = useRecipeSettingsStore()
    display.toggleShowCostColumn()
    expect(display.showCostColumn).toBe(false)

    await s.auth.logout()

    expectEmpty(s)
    expect(clipboard.pasteSlot()).toBeNull()
    expect(context.state.value.items).toEqual([])
    expect(display.showCostColumn).toBe(false)
    await login(s, 'B')
    await load(s)
    expectAccount(s, 'B')
  })

  it('clears stores when the HTTP interceptor encounters a final refresh failure', async () => {
    const http = setupTransport()
    const s = stores()
    await login(s, 'A')
    await load(s)
    http.unauthorized()
    await s.shopping.loadList(1)
    expectEmpty(s)
    expect(transport.send.mock.calls.some(([request]) => request.url === '/api/auth/refresh')).toBe(true)
  })

  it('unmounts the protected draft and redirects to login after losing authorization', async () => {
    const http = setupTransport()
    const s = stores()
    await login(s, 'A')
    const draftPage = defineComponent({
      setup() {
        const draft = ref('Черновик A')
        return () => h('input', { value: draft.value })
      },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/shopping-list', component: draftPage },
        { path: '/login', component: { render: () => h('p', 'Вход') }, meta: { public: true } },
      ],
    })
    await router.push('/shopping-list')
    const app = mount(App, {
      global: {
        plugins: [pinia, router],
        stubs: { AppSidebar: true, MobileBottomNav: true, ToastNotification: true },
      },
    })
    try {
      expect(app.get('input').element.value).toBe('Черновик A')
      http.unauthorized()
      await s.shopping.loadList(1)
      await flushPromises()
      expect(app.find('input').exists()).toBe(false)
      expect(router.currentRoute.value.path).toBe('/login')
    } finally {
      app.unmount()
    }
  })

  it('clears stores when explicit refresh fails', async () => {
    setupTransport()
    const s = stores()
    await login(s, 'A')
    await load(s)
    expect(await s.auth.refresh()).toBe(false)
    expectEmpty(s)
  })

  it.each([false, true])('discards delayed A responses after loading B (401: %s)', async (unauthorized) => {
    const http = setupTransport()
    const s = stores()
    await login(s, 'A')
    http.delay(true)
    const pending = load(s)
    await http.started.waiting
    if (unauthorized) http.unauthorized()
    await s.auth.logout()
    await login(s, 'B')
    await load(s)
    expectAccount(s, 'B')
    http.finish.release()
    await pending
    expectAccount(s, 'B')
    expect(s.auth.user?.nickname).toBe('B')
    expect(transport.send.mock.calls.some(([request]) => request.url === '/api/auth/refresh')).toBe(false)
    expect(localStorage.getItem('access_token')).toBe('B')
    expect(useToastStore().toasts).toEqual([])
  })

  it('keeps the current account state across a successful refresh', async () => {
    const http = setupTransport()
    const s = stores()
    await login(s, 'A')
    await load(s)
    http.unauthorized()
    http.refreshSucceeds()
    await Promise.all([s.shopping.loadList(1), s.family.load()])
    expectAccount(s, 'A')
    expect(s.auth.isAuthenticated).toBe(true)
    expect(localStorage.getItem('access_token')).toBe('A-new')
    expect(transport.send.mock.calls.filter(([request]) => request.url === '/api/auth/refresh')).toHaveLength(1)
  })

  it.each([false, true])('discards an in-flight refresh after switching to B (success: %s)', async (success) => {
    const http = setupTransport()
    const s = stores()
    await login(s, 'A')
    http.unauthorized()
    http.delayRefresh()
    if (success) http.refreshSucceeds()
    const oldLoad = s.shopping.loadList(1)
    await http.refreshStarted.waiting

    await s.auth.logout()
    await login(s, 'B')
    await load(s)
    http.refreshFinish.release()
    await oldLoad

    expectAccount(s, 'B')
    expect(s.auth.user?.nickname).toBe('B')
    expect(localStorage.getItem('access_token')).toBe('B')
    expect(localStorage.getItem('refresh_token')).toBe('refresh-B')
    expect(useToastStore().toasts).toEqual([])
  })
})
