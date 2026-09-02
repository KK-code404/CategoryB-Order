import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { LayoutSider } from 'ant-design-vue'
import { authApi } from '../api/client'
import { admin, dealer } from '../test/fixtures'
import { mountPage } from '../test/helpers'
import AppShell from './AppShell.vue'

vi.mock('../api/client', () => ({ authApi: { logout: vi.fn() } }))
vi.mock('../pages/DashboardPage.vue', () => ({
  default: { template: '<div data-testid="dashboard">工作台内容</div>' },
}))
vi.mock('../pages/ResourcePage.vue', () => ({
  __esModule: true,
  default: { props: ['resource'], template: '<div data-testid="resource">{{ resource }}</div>' },
}))
vi.mock('../pages/AdminSettingsPage.vue', () => ({
  __esModule: true,
  default: { template: '<div data-testid="settings">后台配置内容</div>' },
}))
beforeEach(() => {
  vi.mocked(authApi.logout).mockReset().mockResolvedValue(undefined)
})
describe('Vue application navigation', () => {
  it('switches every business destination and the admin configuration page', async () => {
    const wrapper = mountPage(AppShell, { user: admin })
    expect(wrapper.find('[data-testid="dashboard"]').exists()).toBe(true)
    for (const [label, resource] of [
      ['订单台账', 'orders'],
      ['发货申请', 'shipments'],
      ['邮件收件箱', 'inbox'],
      ['操作日志', 'audit'],
    ]) {
      await wrapper
        .findAll('[role="menuitem"]')
        .find((item) => item.text().includes(label))!
        .trigger('click')
      await vi.waitFor(() => expect(wrapper.find('[data-testid="resource"]').text()).toBe(resource))
    }
    await wrapper
      .findAll('[role="menuitem"]')
      .find((item) => item.text().includes('后台配置'))!
      .trigger('click')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="settings"]').exists()).toBe(true))
  })
  it('hides admin navigation for a dealer', () => {
    const wrapper = mountPage(AppShell, { user: dealer })
    expect(wrapper.findAll('[role="menuitem"]').some((item) => item.text().includes('后台配置'))).toBe(false)
  })
  it('closes mobile navigation after a destination is chosen', async () => {
    const wrapper = mountPage(AppShell, { user: admin })
    wrapper.findComponent(LayoutSider).vm.$emit('breakpoint', true)
    await flushPromises()
    await wrapper.find('.mobile-menu-button').trigger('click')
    expect(wrapper.find('.sider-backdrop').exists()).toBe(true)
    await wrapper
      .findAll('[role="menuitem"]')
      .find((item) => item.text().includes('订单台账'))!
      .trigger('click')
    expect(wrapper.find('.sider-backdrop').exists()).toBe(false)
  })
  it('clears the local session only after server logout succeeds', async () => {
    const wrapper = mountPage(AppShell, { user: admin })
    vi.mocked(authApi.logout).mockRejectedValueOnce(new Error('网络不可用'))
    await wrapper.find('button[aria-label="退出登录"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(AppShell).emitted('logout')).toBeUndefined()
    await wrapper.find('button[aria-label="退出登录"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent(AppShell).emitted('logout')).toHaveLength(1)
  })
})
