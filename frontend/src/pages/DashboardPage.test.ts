import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { dataApi } from '../api/client'
import { admin, dashboard, dealer, line } from '../test/fixtures'
import { button, mountPage } from '../test/helpers'
import DashboardPage from './DashboardPage.vue'

vi.mock('../api/client', () => ({ dataApi: { dashboard: vi.fn(), confirmLines: vi.fn() } }))
beforeEach(() => {
  vi.mocked(dataApi.dashboard).mockReset().mockResolvedValue(structuredClone(dashboard))
  vi.mocked(dataApi.confirmLines).mockReset().mockResolvedValue({ confirmed: 1, outbound_mails: 1 })
})
describe('Vue dashboard', () => {
  it('renders statistics, real table cells and the selected application', async () => {
    const wrapper = mountPage(DashboardPage, { user: admin })
    await flushPromises()
    expect(wrapper.find('.stat-strip').text()).toContain('待处理邮件1')
    expect(wrapper.find('.workspace-list').text()).toContain(line.request_no)
    expect(wrapper.find('.request-detail').text()).toContain(line.product_name)
    expect(wrapper.find('.request-detail').text()).toContain('核销后余额70')
    await wrapper.find('input[placeholder="搜索申请号/订单号/零件号"]').setValue('not-found')
    expect(wrapper.find('.workspace-list').text()).not.toContain(line.request_no)
  })
  it('confirms a pending application then refreshes its status and balance', async () => {
    const wrapper = mountPage(DashboardPage, { user: admin })
    await flushPromises()
    vi.mocked(dataApi.dashboard).mockResolvedValue({
      ...dashboard,
      lines: [{ ...line, status: 'RECONCILED', remaining_qty: 70 }],
    })
    await button(wrapper, '确认核销').trigger('click')
    await vi.waitFor(() => expect(dataApi.confirmLines).toHaveBeenCalledWith([line.id]))
    await flushPromises()
    expect(wrapper.find('.request-detail').text()).toContain('已核销')
    expect(button(wrapper, '确认核销').attributes('disabled')).toBeDefined()
  })
  it('hides reconciliation for dealers while retaining their edit control', async () => {
    const wrapper = mountPage(DashboardPage, { user: dealer })
    await flushPromises()
    expect(wrapper.find('.detail-actions').text()).not.toContain('确认核销')
    expect(button(wrapper, '修改申请').exists()).toBe(true)
  })
  it('shows a retryable load failure and recovers', async () => {
    vi.mocked(dataApi.dashboard).mockRejectedValueOnce(new Error('服务暂不可用'))
    const wrapper = mountPage(DashboardPage, { user: admin })
    await flushPromises()
    expect(wrapper.find('.page-alert').text()).toContain('服务暂不可用')
    await button(wrapper, '重试').trigger('click')
    await flushPromises()
    expect(wrapper.find('.page-alert').exists()).toBe(false)
    expect(wrapper.find('.request-detail').text()).toContain(line.request_no)
  })
})
