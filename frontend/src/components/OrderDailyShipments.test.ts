// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 验证 Excel 式日历的日期列、独立订单工作表、月份请求和错误重试，不依赖演示业务数据。
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { dataApi } from '../api/client'
import type { DailyShipmentReport, DailyShipmentRow } from '../types'
import { button, mountPage } from '../test/helpers'
import OrderDailyShipments from './OrderDailyShipments.vue'

vi.mock('../api/client', () => ({ dataApi: { dailyShipments: vi.fn() } }))
const row: DailyShipmentRow = {
  id: 1, dealer_id: 1, dealer_code: 'A', dealer_name: '代理商A', order_no: 'ORDER1', part_no: 'TK10018',
  material_no: 'TK10018X', product_name: '测试机油', unit: '桶', version: 1,
  ordered_qty: '100', reconciled_qty: '42.5', remaining_qty: '57.5', undated_qty: '40', month_qty: '2.5',
  daily: { '2026-02-03': '2.5' },
}
const report: DailyShipmentReport = {
  month: '2026-02', date_basis: 'requested_ship_date', dates: ['2026-02-01', '2026-02-02', '2026-02-03'],
  rows: [row, { ...row, id: 2, dealer_id: 2, dealer_code: 'B', dealer_name: '代理商B', part_no: 'OTHER', material_no: 'OTHER-X', unit: '箱', daily: {}, month_qty: 0 }],
}
beforeEach(() => { vi.mocked(dataApi.dailyShipments).mockReset().mockResolvedValue(structuredClone(report)) })

describe('每日发货台账', () => {
  // CHANGE [2026-09-03 09:01 +08:00] [WH400]: 日期零值留空且历史差额不混入日历，合计按计量单位隔离。
  it('renders a day grid with undated history and separate unit totals', async () => {
    const wrapper = mountPage(OrderDailyShipments)
    await flushPromises()
    expect(wrapper.findAll('thead .daily-date-header')).toHaveLength(3)
    expect(wrapper.find('[data-order-line="1"] [data-date="2026-02-03"]').text()).toBe('2.5')
    expect(wrapper.find('[data-order-line="1"] [data-date="2026-02-01"]').text()).toBe('—')
    expect(wrapper.find('[data-order-line="1"] .daily-undated').text()).toBe('40')
    expect(wrapper.findAll('tfoot tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('不是物流实发或签收数量')
  })
  // CHANGE [2026-09-03 09:01 +08:00] [WH400]: 同号订单通过代理商复合标识切换，防止合并其他客户明细。
  it('switches same-number orders independently and searches parts', async () => {
    const wrapper = mountPage(OrderDailyShipments)
    await flushPromises()
    await button(wrapper, 'ORDER1 · B').trigger('click')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.find('tbody').text()).toContain('OTHER')
    expect(wrapper.find('tbody').text()).not.toContain('TK10018')
    await wrapper.find('input[placeholder="搜索订单号、零件或客户"]').setValue('TK10018')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    expect(wrapper.find('tbody').text()).toContain('TK10018')
    await wrapper.find('input[placeholder="搜索订单号、零件或客户"]').setValue('missing')
    expect(wrapper.text()).toContain('没有符合条件的订单')
  })
  // CHANGE [2026-09-03 09:01 +08:00] [WH400]: 隐藏无发货日期只改变展示，不重算余额；切月触发新接口请求。
  it('toggles active dates and fetches the next month', async () => {
    const wrapper = mountPage(OrderDailyShipments)
    await flushPromises()
    await wrapper.find('button[role="switch"]').trigger('click')
    expect(wrapper.findAll('.daily-date-header')).toHaveLength(1)
    const previousMonth = vi.mocked(dataApi.dailyShipments).mock.calls[0][0]
    await wrapper.find('button[aria-label="下个月"]').trigger('click')
    await flushPromises()
    expect(dataApi.dailyShipments).toHaveBeenCalledTimes(2)
    expect(vi.mocked(dataApi.dailyShipments).mock.calls[1][0]).not.toBe(previousMonth)
  })
  // CHANGE [2026-09-03 09:01 +08:00] [WH400]: 网络失败不伪装为空台账，保留可重试入口。
  it('retries load failure without showing stale rows', async () => {
    vi.mocked(dataApi.dailyShipments).mockRejectedValueOnce(new Error('读取失败'))
    const wrapper = mountPage(OrderDailyShipments)
    await flushPromises()
    expect(wrapper.text()).toContain('读取失败')
    expect(wrapper.find('table').exists()).toBe(false)
    await button(wrapper, '重试').trigger('click')
    await flushPromises()
    expect(wrapper.find('table').exists()).toBe(true)
  })
  // CHANGE [2026-09-03 09:01 +08:00] [WH400]: 快速切换月份时，迟到的旧请求不得覆盖当前表格。
  it('ignores a stale month response', async () => {
    let finishFirst!: (value: DailyShipmentReport) => void
    vi.mocked(dataApi.dailyShipments).mockImplementationOnce(() => new Promise(resolve => { finishFirst = resolve }))
    const wrapper = mountPage(OrderDailyShipments)
    await wrapper.find('button[aria-label="下个月"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('tbody').text()).toContain('ORDER1')
    finishFirst({ ...report, rows: [] })
    await flushPromises()
    expect(wrapper.find('tbody').text()).toContain('ORDER1')
  })
})
