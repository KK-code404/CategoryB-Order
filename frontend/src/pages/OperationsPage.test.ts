// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 验证代理商不请求受限邮件接口、沙盘只读及刷新失败不会展示过时余额。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { dataApi } from '../api/client'
import { button, mountPage } from '../test/helpers'
import type { DailyShipmentReport } from '../types'
import OperationsPage from './OperationsPage.vue'

vi.mock('../api/client', () => ({ dataApi: { shipmentLines: vi.fn(), dailyShipments: vi.fn(), outboundMails: vi.fn() } }))
const user = { id: 1, role: 'DEALER', dealer_id: 1, email: 'dealer@example.com', display_name: '代理商' }
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(dataApi.shipmentLines).mockResolvedValue([])
  vi.mocked(dataApi.outboundMails).mockResolvedValue([])
  vi.mocked(dataApi.dailyShipments).mockResolvedValue({ rows: [
    { id: 1, order_no: 'ORDER1', part_no: 'PART', dealer_name: '客户甲', remaining_qty: '10', unit: '桶', undated_qty: '0' },
    { id: 2, order_no: 'ORDER1', part_no: 'PART', dealer_name: '客户乙', remaining_qty: '5', unit: '箱', undated_qty: '1' },
  ] } as DailyShipmentReport)
})
describe('业务驾驶舱', () => {
  it('never fetches supplier mail as dealer and explains report scope', async () => {
    const wrapper = mountPage(OperationsPage, { user })
    await flushPromises()
    expect(dataApi.outboundMails).not.toHaveBeenCalled()
    await button(wrapper, '业务简报').trigger('click')
    expect(wrapper.find('pre').text()).toContain('代理商视角不提供')
    expect(wrapper.find('pre').text()).toContain('历史未分日数量的订单行 1')
  })
  it('simulates independent order identities and keeps hidden rows in its summary', async () => {
    const wrapper = mountPage(OperationsPage, { user: { ...user, role: 'SALES' } })
    await flushPromises()
    expect(dataApi.outboundMails).toHaveBeenCalledOnce()
    await button(wrapper, '发货沙盘').trigger('click')
    await wrapper.find('input[aria-label="订单行 1 拟发数量"]').setValue('11')
    expect(wrapper.text()).toContain('缺口 1 桶')
    expect(wrapper.find('input[aria-label="订单行 2 拟发数量"]').element).toHaveProperty('value', '')
    await wrapper.find('input[placeholder="输入订单、零件或客户"]').setValue('客户乙')
    expect(wrapper.text()).toContain('全沙盘 1 行（含搜索隐藏行），1 行需要调整')
    await button(wrapper, '清空模拟').trigger('click')
    expect(wrapper.text()).toContain('全沙盘 0 行')
  })
  it('hides prior snapshot on refresh failure and allows retry', async () => {
    const wrapper = mountPage(OperationsPage, { user })
    await flushPromises()
    vi.mocked(dataApi.shipmentLines).mockRejectedValueOnce(new Error('网络中断'))
    await button(wrapper, '刷新数据并重置沙盘').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('网络中断')
    expect(wrapper.find('.operations-metrics').exists()).toBe(false)
    await button(wrapper, '刷新数据并重置沙盘').trigger('click')
    await flushPromises()
    expect(wrapper.find('.operations-metrics').exists()).toBe(true)
  })
})
