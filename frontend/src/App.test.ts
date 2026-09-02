import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { authApi } from './api/client'
import { admin } from './test/fixtures'
import App from './App.vue'

vi.mock('./api/client', () => ({ authApi: { me: vi.fn() } }))
vi.mock('./pages/LoginPage.vue', () => ({ default: { template: '<div data-testid="login">登录</div>' } }))
vi.mock('./components/AppShell.vue', () => ({
  __esModule: true,
  default: { props: ['user'], template: '<div data-testid="shell">{{ user.display_name }}</div>' },
}))
beforeEach(() => {
  vi.mocked(authApi.me).mockReset()
})
describe('Vue authentication lifecycle', () => {
  it('restores a session before rendering protected content', async () => {
    vi.mocked(authApi.me).mockResolvedValue(admin)
    const wrapper = mount(App)
    expect(wrapper.find('.app-loading').exists()).toBe(true)
    expect(wrapper.find('[data-testid="shell"]').exists()).toBe(false)
    await vi.waitFor(() => expect(wrapper.text()).toContain(admin.display_name))
    window.dispatchEvent(new Event('auth-expired'))
    await flushPromises()
    expect(wrapper.find('[data-testid="login"]').exists()).toBe(true)
  })
  it('shows login when no valid cookie session exists', async () => {
    vi.mocked(authApi.me).mockRejectedValue(new Error('未登录'))
    const wrapper = mount(App)
    await flushPromises()
    expect(wrapper.find('[data-testid="login"]').exists()).toBe(true)
    expect(wrapper.find('.app-loading').exists()).toBe(false)
  })
  it('does not restore a stale response after session expiration', async () => {
    let resolve!: (user: typeof admin) => void
    vi.mocked(authApi.me).mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = mount(App)
    window.dispatchEvent(new Event('auth-expired'))
    resolve(admin)
    await flushPromises()
    expect(wrapper.find('[data-testid="shell"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="login"]').exists()).toBe(true)
  })
})
