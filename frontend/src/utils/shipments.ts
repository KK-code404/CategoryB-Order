import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { ShipmentLine, ShipmentRequest } from '../types'

export type DateRange = [Dayjs, Dayjs] | null | undefined
export const shipmentLabels = { PENDING: '待确认', EXCEPTION: '匹配异常', RECONCILED: '已核销', REVERSED: '已冲销' }
export const shipmentColors = {
  PENDING: 'processing',
  EXCEPTION: 'warning',
  RECONCILED: 'success',
  REVERSED: 'default',
}
export const mailLabels = { PENDING: '待发送', SENT: '已发送', FAILED: '发送失败' }
export const mailColors = { PENDING: 'processing', SENT: 'success', FAILED: 'error' }
export function includesSearch(values: unknown[], search: string) {
  const normalized = search.trim().toLocaleLowerCase()
  return (
    !normalized ||
    values.some((value) =>
      String(value ?? '')
        .toLocaleLowerCase()
        .includes(normalized),
    )
  )
}
export function withinRange(value: string, range: DateRange) {
  if (!range?.[0] || !range[1]) return true
  const date = dayjs(value)
  return !date.isBefore(range[0].startOf('day')) && !date.isAfter(range[1].endOf('day'))
}
export function shipmentRequestStatus(row: ShipmentRequest): ShipmentLine['status'] {
  if (row.exception_count) return 'EXCEPTION'
  if (row.pending_count) return 'PENDING'
  if (row.reconciled_count) return 'RECONCILED'
  return 'REVERSED'
}
export function shipmentBalances(line: ShipmentLine | null) {
  if (line?.remaining_qty == null) return { before: null, after: null }
  const remaining = Number(line.remaining_qty)
  const quantity = Number(line.quantity)
  return {
    before: line.status === 'RECONCILED' ? remaining + quantity : remaining,
    after: line.status === 'RECONCILED' || line.status === 'REVERSED' ? remaining : remaining - quantity,
  }
}
