import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { accountSessionSignal, endAccountSession, readAccountToken, saveAccountLogin, syncAccountSession } from '@/api/accountSession'
import * as authApi from '@/api/auth'
import type { LoginRequest, RegisterRequest, UserResponse } from '@/api/types'
import { clearContextMenu } from '@/composables/useContextMenu'
import { clearPlannerClipboard } from '@/composables/usePlannerClipboard'
import { useCategoryStore } from './categories'
import { useFamilyStore } from './family'
import { useMealTypeStore } from './mealTypes'
import { useMenuStore } from './menus'
import { usePreferencesStore } from './preferences'
import { useProductStore } from './products'
import { useRecipeStore } from './recipes'
import { useShoppingListStore } from './shoppingList'
import { useToastStore } from './toast'

const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserResponse | null>(null)
  const accessToken = ref(readAccountToken(ACCESS_TOKEN_KEY) || '')
  const refreshToken = ref(readAccountToken(REFRESH_TOKEN_KEY) || '')
  const isAuthenticated = computed(() => !!accessToken.value)

  const accountStores = [
    useCategoryStore(), useFamilyStore(), useMealTypeStore(), useMenuStore(), usePreferencesStore(),
    useProductStore(), useRecipeStore(), useShoppingListStore(), useToastStore(),
  ]

  watch(accountSessionSignal, () => {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    for (const store of accountStores) store.reset()
    clearContextMenu()
    clearPlannerClipboard()
  }, { flush: 'sync' })

  function saveTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem(ACCESS_TOKEN_KEY, access)
    localStorage.setItem(REFRESH_TOKEN_KEY, refresh)
  }

  async function register(data: RegisterRequest) {
    const session = accountSessionSignal()
    const created = await authApi.register(data)
    syncAccountSession()
    session.throwIfAborted()
    useToastStore().show('Регистрация успешна! Войдите в аккаунт.', 'success')
    return created
  }

  async function login(data: LoginRequest) {
    endAccountSession()
    const session = accountSessionSignal()
    const tokens = await authApi.login(data)
    syncAccountSession()
    session.throwIfAborted()
    saveAccountLogin(() => saveTokens(tokens.access_token, tokens.refresh_token))
    try {
      await fetchUser()
      syncAccountSession()
      session.throwIfAborted()
    } catch (error) {
      if (!session.aborted) endAccountSession()
      throw error
    }
  }

  async function refresh(): Promise<boolean> {
    if (!syncAccountSession()) return false
    const session = accountSessionSignal()
    if (!refreshToken.value) {
      endAccountSession()
      return false
    }
    try {
      const tokens = await authApi.refreshTokens({
        refresh_token: refreshToken.value,
      })
      if (!syncAccountSession() || session.aborted) return false
      saveTokens(tokens.access_token, tokens.refresh_token)
      return true
    } catch {
      if (!session.aborted) endAccountSession()
      return false
    }
  }

  async function fetchUser() {
    if (!syncAccountSession() || !accessToken.value) return
    const session = accountSessionSignal()
    try {
      const profile = await authApi.getMe(accessToken.value)
      if (syncAccountSession() && !session.aborted) user.value = profile
    } catch (error) {
      if (!session.aborted) user.value = null
      throw error
    }
  }

  async function logout() {
    const token = readAccountToken(REFRESH_TOKEN_KEY)
    if (!syncAccountSession()) return
    endAccountSession()
    if (token) {
      try {
        await authApi.logout({ refresh_token: token })
      } catch {
        /* ignore logout errors */
      }
    }
  }

  async function init() {
    if (!syncAccountSession() || !accessToken.value) return
    const session = accountSessionSignal()
    try {
      await fetchUser()
      return
    } catch {
      if (session.aborted) return
    }
    const refreshed = await refresh()
    if (!refreshed || session.aborted) return
    try {
      await fetchUser()
    } catch {
      if (!session.aborted) endAccountSession()
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    register,
    login,
    refresh,
    fetchUser,
    logout,
    init,
  }
})
