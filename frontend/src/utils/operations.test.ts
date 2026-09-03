// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 覆盖日期边界、重叠风险与数量精度，防止错误预警和模拟误判。
import { describe, expect, it } from 'vitest'
import type { DailyShipmentRow, OutboundMail, ShipmentLine } from '../types'
import { buildRisks, chinaDay, quantityUnits, simulate } from './operations'

describe('operations rules', () => {
  it('uses Shanghai calendar date across UTC midnight', () => {
    expect(chinaDay(new Date('2026-09-02T17:00:00Z'))).toBe('2026-09-03')
  })
  it('flags overdue open lines, not today or reconciled lines, and preserves overlapping exceptions', () => {
    const base = { id: 1, requested_ship_date: '2026-09-02', status: 'EXCEPTION', request_no: 'R', order_no: 'O', material_no: 'M', exception_reason: '物料未匹配' } as ShipmentLine
    const risks = buildRisks([base, { ...base, id: 2, status: 'RECONCILED' }, { ...base, id: 3, status: 'PENDING', requested_ship_date: '2026-09-03' }], [], '2026-09-03')
    expect(risks.map(item => item.category)).toEqual(['逾期待处理', '匹配异常'])
    expect(risks[1].reason).toBe('物料未匹配')
  })
  it('only flags failed mail, without exposing delivery addresses or provider errors', () => {
    const mail = { id: 1, status: 'FAILED', subject: '发货', attempts: 3, last_error: 'private', recipient: 'private' } as OutboundMail
    expect(buildRisks([], [mail, { ...mail, id: 2, status: 'SENT' }], '2026-09-03')).toHaveLength(1)
    expect(JSON.stringify(buildRisks([], [mail], '2026-09-03'))).not.toContain('private')
  })
  it('rejects unsafe quantities and calculates decimal shortages exactly', () => {
    for (const value of ['', '-1', '1.001', 'NaN', '1e3', 'Infinity']) expect(quantityUnits(value)).toBeNull()
    const row = { remaining_qty: '0.30' } as DailyShipmentRow
    expect(simulate(row, '0.1')).toEqual({ valid: true, after: 0.2, shortage: 0 })
    expect(simulate(row, '0.4')).toEqual({ valid: true, after: -0.1, shortage: 0.1 })
    expect(simulate(row, '0').valid).toBe(false)
  })
})
