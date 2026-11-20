import { flushPromises, mount } from '@vue/test-utils'
import { AxiosError } from 'axios'
import { createPinia } from 'pinia'
import { expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import * as authApi from '@/api/auth'
import { useToastStore } from '@/stores/toast'
import LoginView from '@/views/LoginView.vue'

vi.mock('@/api/auth')

it.each([
  [422, [{ loc: ['body', 'email'], msg: 'Invalid email' }], 'Введите корректный email'],
  [409, 'Пользователь с таким email уже существует', 'Пользователь с таким email уже существует'],
])('shows a readable registration error for HTTP %i', async (status, detail, message) => {
  const error = new AxiosError()
  error.response = { status, data: { detail } } as AxiosError['response']
  vi.mocked(authApi.register).mockRejectedValueOnce(error)
  const pinia = createPinia()
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: LoginView }],
  })
  await router.push('/')
  const wrapper = mount(LoginView, { global: { plugins: [pinia, router] } })
  try {
    await wrapper.get('p button').trigger('click')
    await wrapper.get('#email').setValue('alice@example.com')
    await wrapper.get('#password').setValue('Password123!')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(useToastStore(pinia).toasts).toMatchObject([{ message, type: 'error' }])
  } finally {
    wrapper.unmount()
  }
})
