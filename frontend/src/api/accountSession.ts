import { shallowRef } from 'vue'

const controller = shallowRef(new AbortController())

export function accountSessionSignal(): AbortSignal {
  return controller.value.signal
}

const SESSION_KEY = 'menutor_account_session'
const CLOSED_SESSION = 'closed:'
let observedSession = localStorage.getItem(SESSION_KEY)
let currentSession = !observedSession?.startsWith(CLOSED_SESSION)

function resetLocalSession() {
  controller.value.abort()
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

export function saveAccountLogin(saveTokens: () => void) {
  // Tabs opened while the two token keys are being written must wait for a new login.
  publishSession(true)
  saveTokens()
  publishSession(false)
}

window.addEventListener('storage', (event) => {
  if (event.storageArea === localStorage && (event.key === SESSION_KEY || event.key === null)) {
    syncAccountSession()
  }
})
