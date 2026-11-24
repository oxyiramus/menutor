import { flushPromises, mount } from '@vue/test-utils'
import { AxiosError } from 'axios'
import { createPinia } from 'pinia'
import { expect, it, vi } from 'vitest'
import { changePassword } from '@/api/client'
import ChangePasswordPanel from '@/components/settings/ChangePasswordPanel.vue'
import { useToastStore } from '@/stores/toast'

vi.mock('@/api/client', () => ({ changePassword: vi.fn() }))

it.each([
  ['abcde', 'Пароль должен содержать не менее 12 символов'],
  ['🔒'.repeat(18) + 'a', 'Пароль должен занимать не более 72 байт в UTF-8'],
])('shows the server password validation error', async (password, message) => {
  const error = new AxiosError()
  error.response = { status: 422, data: { detail: message } } as AxiosError['response']
  vi.mocked(changePassword).mockReset().mockRejectedValueOnce(error)
  const pinia = createPinia()
  const wrapper = mount(ChangePasswordPanel, { global: { plugins: [pinia] } })
  try {
    const [current, next, confirmation] = wrapper.findAll('input')
    await current!.setValue('old')
    await next!.setValue(password)
    await confirmation!.setValue(password)
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(changePassword).toHaveBeenLastCalledWith('old', password)
    expect(useToastStore(pinia).toasts).toMatchObject([{ message, type: 'error' }])
  } finally {
    wrapper.unmount()
  }
})
