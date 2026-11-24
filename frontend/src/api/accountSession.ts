import { shallowReadonly, shallowRef } from 'vue'
import { logout, refreshTokens } from './auth'
import type { TokenResponse } from './types'

const controller = shallowRef(new AbortController())

export function accountSessionSignal(): AbortSignal {
  return controller.value.signal
}

const SESSION_KEY = 'menutor_account_session'
const CLOSED_SESSION = 'closed:'
let observedSession = localStorage.getItem(SESSION_KEY)
let currentSession = !observedSession?.startsWith(CLOSED_SESSION)
const tokens = shallowRef<Pick<TokenResponse, 'access_token' | 'refresh_token'>>()
export const accountTokens = shallowReadonly(tokens)

function resetLocalSession() {
  controller.value.abort()
  tokens.value = undefined
  controller.value = new AbortController()
}

export function syncAccountSession(): boolean {
  const sharedSession = localStorage.getItem(SESSION_KEY)
  if (sharedSession !== observedSession) {
    observedSession = sharedSession
    currentSession = false
    resetLocalSession()
  }
  return currentSession
}

function publishSession(closed: boolean) {
  const id = crypto.getRandomValues(new Uint32Array(4)).join('-')
  observedSession = closed ? CLOSED_SESSION + id : id
  currentSession = !closed
  localStorage.setItem(SESSION_KEY, observedSession)
}

export function endAccountSession() {
  if (syncAccountSession()) {
    // Invalidate other tabs before removing the tokens so an old refresh is discarded.
    publishSession(true)
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }
  resetLocalSession()
}

export function readAccountToken(key: 'access_token' | 'refresh_token'): string | null {
  if (!syncAccountSession()) return null
  const token = localStorage.getItem(key)
  return syncAccountSession() ? token : null
}

function saveTokens(pair: TokenResponse) {
  localStorage.setItem('access_token', pair.access_token)
  localStorage.setItem('refresh_token', pair.refresh_token)
  tokens.value = pair
}

export function saveAccountLogin(pair: TokenResponse) {
  // Tabs opened while the two token keys are being written must wait for a new login.
  publishSession(true)
  saveTokens(pair)
  publishSession(false)
}

export async function revokeAccountRefresh(token: string) {
  try {
    await logout({ refresh_token: token })
  } catch {
    /* Remote revocation is best effort if the transport fails. */
  }
}

const pendingRefreshes = new WeakMap<AbortSignal, Promise<boolean>>()

export function refreshAccount(): Promise<boolean> {
  if (!syncAccountSession()) return Promise.resolve(false)
  const session = accountSessionSignal()
  const pending = pendingRefreshes.get(session)
  if (pending) return pending

  const refresh = rotateTokens(session).finally(() => pendingRefreshes.delete(session))
  pendingRefreshes.set(session, refresh)
  return refresh
}

async function rotateTokens(session: AbortSignal): Promise<boolean> {
  const token = readAccountToken('refresh_token')
  if (!token) {
    endAccountSession()
    return false
  }

  try {
    // Keep the transport alive so a replacement issued before logout can be revoked.
    const pair = await refreshTokens({ refresh_token: token })
    if (!syncAccountSession() || session.aborted) {
      await revokeAccountRefresh(pair.refresh_token)
      return false
    }

    saveTokens(pair)
    return true
  } catch {
    if (syncAccountSession() && !session.aborted) endAccountSession()
    return false
  }
}

window.addEventListener('storage', (event) => {
  if (event.storageArea !== localStorage) return
  if (event.key === SESSION_KEY || event.key === null) {
    syncAccountSession()
  }
  if (event.key === 'refresh_token' && syncAccountSession()) {
    const access = readAccountToken('access_token')
    const refresh = readAccountToken('refresh_token')
    if (access && refresh) tokens.value = { access_token: access, refresh_token: refresh }
  }
})
