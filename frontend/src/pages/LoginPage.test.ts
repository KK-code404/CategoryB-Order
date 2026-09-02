import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { authApi } from '../api/client'
import { mountPage } from '../test/helpers'
import { admin } from '../test/fixtures'
import LoginPage from './LoginPage.vue'

vi.mock('../api/client', () => ({ authApi: { login: vi.fn() } }))
beforeEach(() => {
  vi.mocked(authApi.login).mockReset()
})
describe('Vue login', () => {
  it('retains the car illustration, accessible fields and required validation', async () => {
    const wrapper = mountPage(LoginPage)
    expect(wrapper.find('.login-visual-image').attributes('src')).toContain('login-operations-3d.webp')
    expect(wrapper.find('[aria-label="账号"]').attributes('autocomplete')).toBe('username')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('请输入账号'))
    expect(authApi.login).not.toHaveBeenCalled()
  })
  it('submits real credentials once and emits the authenticated account', async () => {
    vi.mocked(authApi.login).mockResolvedValue(admin)
    const wrapper = mountPage(LoginPage)
    await wrapper.find('input[aria-label="账号"]').setValue('test-admin')
    await wrapper.find('input[aria-label="密码"]').setValue('test-only-password')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(authApi.login).toHaveBeenCalledWith('test-admin', 'test-only-password'))
    await flushPromises()
    expect(wrapper.findComponent(LoginPage).emitted('success')).toEqual([[admin]])
  })
  it('shows server errors and allows retry without losing the form', async () => {
    vi.mocked(authApi.login).mockRejectedValue(new Error('账号已停用'))
    const wrapper = mountPage(LoginPage)
    await wrapper.find('input[aria-label="账号"]').setValue('test-admin')
    await wrapper.find('input[aria-label="密码"]').setValue('test-only-password')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(document.body.textContent).toContain('账号已停用'))
    expect(wrapper.findComponent(LoginPage).emitted('success')).toBeUndefined()
    expect(wrapper.find('button[type="submit"]').classes()).not.toContain('ant-btn-loading')
  })
})
