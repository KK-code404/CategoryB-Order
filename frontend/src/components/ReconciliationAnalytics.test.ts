import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { dataApi } from '../api/client'
import { button, mountPage } from '../test/helpers'
import type { AnalyticsReport, AnalyticsRow } from '../utils/reconciliationAnalytics'
import ReconciliationAnalytics from './ReconciliationAnalytics.vue'

vi.mock('../api/client', () => ({ dataApi: { reconciliationAnalytics: vi.fn() } }))
const row: AnalyticsRow = { id: 1, dealer_id: 1, dealer_code: 'A', dealer_name: '测试代理商甲', order_no: 'O1', part_no: 'P1', unit: '桶', ordered_qty: '100', opening_qty: '80', closing_qty: '70', undated_qty: '0', daily: { '2026-08-27': '10' } }
const report: AnalyticsReport = { start: '2026-08-27', end: '2026-09-03', dates: ['2026-08-27', '2026-08-28'], generated_at: '2026-09-03T10:00:00Z',
  actual: [row, { ...row, id: 2, dealer_id: 2, dealer_name: '测试代理商乙', closing_qty: '75', daily: { '2026-08-27': '5' } }],
  simulation: { available: false, imported: true, cutoff: '2026-08-26', start: '2026-08-27', end: '2026-09-03', version: 'conservative-v1', reason: '已纳入正式核销', rows: [], events: [] } }
beforeEach(() => { vi.mocked(dataApi.reconciliationAnalytics).mockReset().mockResolvedValue(structuredClone(report)) })
describe('图表核销看板', () => {
  it('shows six charts with formal data and no tables, forms or simulation controls', async () => {
    const wrapper = mountPage(ReconciliationAnalytics)
    await flushPromises()
    expect(wrapper.findAll('table, form, input, select')).toHaveLength(0)
    expect(wrapper.findAll('section.board-panel')).toHaveLength(6)
    expect(wrapper.find('.board-summary').text()).toContain('区间净核销15桶')
    expect(wrapper.text()).not.toContain('模拟演示')
    expect(wrapper.text()).toContain('来源与批准记录保留在操作日志')
    expect(dataApi.reconciliationAnalytics).toHaveBeenCalledWith('2026-08-27', '2026-09-03')
  })
  it('filters all charts by dealer and preserves the selection on refresh', async () => {
    const wrapper = mountPage(ReconciliationAnalytics)
    await flushPromises()
    await button(wrapper, '测试代理商甲').trigger('click')
    expect(wrapper.find('.board-summary').text()).toContain('区间净核销10桶')
    await button(wrapper, '刷新看板').trigger('click')
    await flushPromises()
    expect(wrapper.find('.board-summary').text()).toContain('区间净核销10桶')
    expect(button(wrapper, '测试代理商甲').attributes('aria-pressed')).toBe('true')
    await button(wrapper, '全部代理商').trigger('click')
    expect(wrapper.find('.board-summary').text()).toContain('区间净核销15桶')
  })
  it('provides direct bar interaction and detail navigation', async () => {
    const wrapper = mountPage(ReconciliationAnalytics)
    await flushPromises()
    await wrapper.find('g[role="button"]').trigger('keydown', { key: 'Enter' })
    expect(wrapper.find('.board-chart-detail').text()).toContain('测试代理商甲 10 桶')
    await button(wrapper, '查看订单台账').trigger('click')
    expect(wrapper.findComponent(ReconciliationAnalytics).emitted('navigate')).toEqual([['orders']])
  })
  it('hides stale results, retries and handles empty data', async () => {
    const wrapper = mountPage(ReconciliationAnalytics)
    await flushPromises()
    vi.mocked(dataApi.reconciliationAnalytics).mockRejectedValueOnce(new Error('网络中断'))
    await button(wrapper, '刷新看板').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('网络中断')
    expect(wrapper.find('.board-summary').exists()).toBe(false)
    await button(wrapper, '刷新看板').trigger('click')
    await flushPromises()
    expect(wrapper.find('.board-summary').exists()).toBe(true)
    vi.mocked(dataApi.reconciliationAnalytics).mockResolvedValue({ ...report, actual: [] })
    await button(wrapper, '8 月').trigger('click')
    await flushPromises()
    expect(dataApi.reconciliationAnalytics).toHaveBeenLastCalledWith('2026-08-01', '2026-08-31')
    expect(wrapper.text()).toContain('当前范围没有订单')
  })
  it('ignores old date responses and separates units', async () => {
    let resolveOld!: (value: AnalyticsReport) => void
    vi.mocked(dataApi.reconciliationAnalytics).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
    const wrapper = mountPage(ReconciliationAnalytics)
    await button(wrapper, '8 月').trigger('click')
    await flushPromises()
    resolveOld({ ...report, actual: [] })
    await flushPromises()
    expect(wrapper.find('.board-summary').exists()).toBe(true)
    vi.mocked(dataApi.reconciliationAnalytics).mockResolvedValue({ ...report, actual: [row, { ...row, id: 3, unit: '箱', daily: { '2026-08-27': '2' }, closing_qty: '78' }] })
    await button(wrapper, '刷新看板').trigger('click')
    await flushPromises()
    expect(wrapper.find('.board-summary').text()).toContain('区间净核销10桶')
    await button(wrapper, '箱').trigger('click')
    expect(wrapper.find('.board-summary').text()).toContain('区间净核销2箱')
  })
})
