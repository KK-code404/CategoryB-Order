import { describe, expect, it } from 'vitest'
import { dashboardRanges, groupOrders, summarize } from './reconciliationAnalytics'
import type { AnalyticsRow } from './reconciliationAnalytics'

const row = { id: 1, dealer_id: 1, dealer_code: 'A', dealer_name: '甲', order_no: 'O1', part_no: 'P1', unit: '桶', ordered_qty: '100', opening_qty: '80', closing_qty: '69.7', undated_qty: '0', daily: { '2026-08-27': '10.1', '2026-08-28': '.2' } } satisfies AnalyticsRow
describe('看板计算', () => {
  it('groups completion at the order level and flags invalid balances', () => {
    const result = groupOrders([row, { ...row, id: 2, part_no: 'P2', closing_qty: '0' }, { ...row, id: 3, dealer_id: 2, closing_qty: '0' }, { ...row, id: 4, order_no: 'O2', closing_qty: '100' }, { ...row, id: 5, order_no: 'BAD', closing_qty: '-1' }])
    expect(result.map(r => r.status)).toEqual(['部分核销', '已核销完', '未核销', '待核查'])
    expect(result[0]?.ordered).toBe(200)
    expect(result[0]?.remaining).toBe(69.7)
  })
  it('calculates shortcut dates across month and year boundaries', () => {
    expect(dashboardRanges('2026-01-05').find(r => r.id === 'recent')?.start).toBe('2025-12-07')
    expect(dashboardRanges('2026-09-03').find(r => r.id === 'month')?.start).toBe('2026-09-01')
  })
  it('uses exact hundredths and includes zero days', () => {
    const data = summarize([row], ['2026-08-27', '2026-08-28', '2026-08-29'])
    expect(data.quantity).toBe(10.3)
    expect(data.daily.map(d => d.balance)).toEqual([69.9, 69.7, 69.7])
    expect(data.activeDays).toBe(2)
  })
  it('separates orders from lines and different dealers with the same order number', () => {
    const result = summarize([row, { ...row, id: 2, part_no: 'P2' }, { ...row, id: 3, dealer_id: 2 }], [])
    expect(result.orders).toBe(2)
    expect(result.lines).toBe(3)
  })
  it('keeps signed reversals and empty scopes', () => {
    expect(summarize([{ ...row, daily: { '2026-08-27': '-2' } }], ['2026-08-27']).daily[0]?.balance).toBe(82)
    expect(summarize([], ['2026-08-27']).quantity).toBe(0)
  })
  it('counts an active day when different lines offset to a zero net total', () => {
    const result = summarize([row, { ...row, id: 2, daily: { '2026-08-27': '-10.1' } }], ['2026-08-27'])
    expect(result.quantity).toBe(0)
    expect(result.activeDays).toBe(1)
  })
})
