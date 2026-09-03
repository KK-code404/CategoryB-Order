// CHANGE [2026-09-03 13:03 +08:00] [WH400]: 登录改版测试覆盖新插画、账号偏好、存储失败与帮助入口，确保视觉改版不破坏认证。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { authApi } from '../api/client'
import { button, mountPage } from '../test/helpers'
import { admin } from '../test/fixtures'
import LoginPage from './LoginPage.vue'

vi.mock('../api/client', () => ({ authApi: { login: vi.fn() } }))
beforeEach(() => {
  localStorage.clear()
  vi.mocked(authApi.login).mockReset()
})
describe('Vue login', () => {
  // CHANGE [2026-09-03 13:03 +08:00] [WH400]: 密码显隐必须通过真实按钮切换，且不能意外提交表单。
  it('toggles password visibility with an accessible non-submit button', async () => {
    const wrapper = mountPage(LoginPage)
    await wrapper.find('button[aria-label="显示密码"]').trigger('click')
    expect(wrapper.find('input[aria-label="密码"]').attributes('type')).toBe('text')
    await wrapper.find('button[aria-label="隐藏密码"]').trigger('click')
    expect(wrapper.find('input[aria-label="密码"]').attributes('type')).toBe('password')
    expect(authApi.login).not.toHaveBeenCalled()
  })
  it('renders the technology illustration, accessible fields and required validation', async () => {
    const wrapper = mountPage(LoginPage)
    // CHANGE [2026-09-03 16:32 +08:00] [WH400]: 锁定油品参考图背景与单行平台标题，避免重新出现“登录到”。
    expect(wrapper.find('.login-visual-image').attributes('src')).toContain('login-oil-logistics-20260903.png')
    expect(wrapper.find('h1').text()).toBe('油品订单协同平台')
    expect(wrapper.text()).not.toContain('登录到')
    expect(wrapper.text()).not.toContain('整单备货，分批协同')
    expect(wrapper.find('.login-business-tags').exists()).toBe(false)
    expect(wrapper.find('[aria-label="账号"]').attributes('autocomplete')).toBe('username')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('请输入账号'))
    expect(authApi.login).not.toHaveBeenCalled()
  })
  it('only remembers the account after opt-in successful login, never the password', async () => {
    vi.mocked(authApi.login).mockResolvedValue(admin)
    const wrapper = mountPage(LoginPage)
    await wrapper.find('input[aria-label="账号"]').setValue(' test-admin ')
    await wrapper.find('input[aria-label="密码"]').setValue('test-only-password')
    await wrapper.find('input[type="checkbox"]').setValue(true)
    expect(localStorage.length).toBe(0)
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(localStorage.getItem('categoryb.remembered-account')).toBe('test-admin'))
    expect(localStorage.length).toBe(1)
    expect(authApi.login).toHaveBeenCalledWith('test-admin', 'test-only-password')
  })
  it('restores and immediately forgets saved account on opt-out', async () => {
    localStorage.setItem('categoryb.remembered-account', 'saved-account')
    const wrapper = mountPage(LoginPage)
    await flushPromises()
    expect(wrapper.find('input[aria-label="账号"]').element).toHaveProperty('value', 'saved-account')
    expect(wrapper.find('input[aria-label="密码"]').element).toHaveProperty('value', '')
    await wrapper.find('input[type="checkbox"]').setValue(false)
    expect(localStorage.getItem('categoryb.remembered-account')).toBeNull()
  })
  it('does not block authentication when browser storage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    vi.mocked(authApi.login).mockResolvedValue(admin)
    const wrapper = mountPage(LoginPage)
    await wrapper.find('input[aria-label="账号"]').setValue('test-admin')
    await wrapper.find('input[aria-label="密码"]').setValue('test-only-password')
    await wrapper.find('input[type="checkbox"]').setValue(true)
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.findComponent(LoginPage).emitted('success')).toEqual([[admin]]))
  })
  it('explains administrator-assisted password recovery without submitting the form', async () => {
    const wrapper = mountPage(LoginPage)
    await button(wrapper, '忘记密码').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('请联系平台管理员核验身份并重置密码')
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
