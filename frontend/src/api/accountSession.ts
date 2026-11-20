import { shallowRef } from 'vue'

const controller = shallowRef(new AbortController())

export function accountSessionSignal(): AbortSignal {
  return controller.value.signal
}

export function endAccountSession() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  controller.value.abort()
  controller.value = new AbortController()
}
