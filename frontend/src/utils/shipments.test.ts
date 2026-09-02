import { describe, expect, it } from 'vitest'
import dayjs from 'dayjs'
import { includesSearch, shipmentBalances, shipmentRequestStatus, withinRange } from './shipments'
import { formatChinaDateTime } from './date'
import { line, request } from '../test/fixtures'

describe('shared business presentation', () => {
  it('searches case-insensitively and handles absent values', () => {
    expect(includesSearch([null, 'ORDER-001'], ' order-001 ')).toBe(true)
    expect(includesSearch([undefined], 'missing')).toBe(false)
    expect(includesSearch([], ' ')).toBe(true)
  })
  it('includes complete first and last days in a range', () => {
    const range: [dayjs.Dayjs, dayjs.Dayjs] = [dayjs('2026-09-03'), dayjs('2026-09-04')]
    expect(withinRange('2026-09-03T00:00:00', range)).toBe(true)
    expect(withinRange('2026-09-04T23:59:59', range)).toBe(true)
    expect(withinRange('2026-09-05T00:00:00', range)).toBe(false)
    expect(withinRange(line.received_at, null)).toBe(true)
  })
  it('shows request exception and pending states before completed states', () => {
    expect(shipmentRequestStatus({ ...request, exception_count: 1 })).toBe('EXCEPTION')
    expect(shipmentRequestStatus(request)).toBe('PENDING')
    expect(shipmentRequestStatus({ ...request, pending_count: 0, reconciled_count: 1 })).toBe('RECONCILED')
    expect(shipmentRequestStatus({ ...request, pending_count: 0, reversed_count: 1 })).toBe('REVERSED')
  })
  it('does not deduct already reconciled or reversed quantities twice', () => {
    expect(shipmentBalances(line)).toEqual({ before: 80, after: 70 })
    expect(shipmentBalances({ ...line, status: 'RECONCILED' })).toEqual({ before: 90, after: 80 })
    expect(shipmentBalances({ ...line, status: 'REVERSED' })).toEqual({ before: 80, after: 80 })
    expect(shipmentBalances(null)).toEqual({ before: null, after: null })
  })
  it('renders server UTC timestamps in Shanghai time', () => {
    expect(formatChinaDateTime('2026-09-03T02:30:00Z')).toBe('2026-09-03 10:30:00')
  })
})
