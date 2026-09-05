export interface AnalyticsRow {
  id: number
  dealer_id: number
  dealer_code: string
  dealer_name: string
  order_no: string
  part_no: string
  unit: string
  ordered_qty: string
  opening_qty: string
  closing_qty: string
  undated_qty: string
  daily: Record<string, string>
  baseline_remaining_qty?: string
}
export interface AnalyticsReport {
  start: string
  end: string
  dates: string[]
  generated_at: string
  actual: AnalyticsRow[]
  simulation: {
    available: boolean
    cutoff: string
    start: string
    end: string
    version: string
    reason: string
    imported?: boolean
    rows: AnalyticsRow[]
    events: Array<{ id: string; order_line_id: number; date: string; quantity: string; simulated: true }>
  }
}

// Integer hundredths avoid rounding drift when summing Decimal API strings.
export const cents = (value: string | number) => Math.round(Number(value) * 100)
export const sumQty = (rows: AnalyticsRow[], get: (row: AnalyticsRow) => string | number) => rows.reduce((sum, row) => sum + cents(get(row)), 0) / 100
export const formatQty = (value: string | number) => Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
export const chartColors = ['#665cf6', '#208d8a', '#bd7623', '#6084c0', '#ae5f88']
export function groupOrders(rows: AnalyticsRow[]) {
  const groups = new Map<string, AnalyticsRow[]>()
  for (const row of rows) {
    const key = `${row.dealer_id}:${row.order_no}`
    groups.set(key, [...(groups.get(key) ?? []), row])
  }
  return [...groups].map(([key, items]) => {
    const ordered = sumQty(items, r => r.ordered_qty), remaining = sumQty(items, r => r.closing_qty)
    const invalid = items.some(r => Number(r.ordered_qty) <= 0 || Number(r.closing_qty) < 0 || Number(r.closing_qty) > Number(r.ordered_qty))
    const status = invalid ? '待核查' : items.every(r => cents(r.closing_qty) === 0) ? '已核销完' : items.every(r => cents(r.ordered_qty) === cents(r.closing_qty)) ? '未核销' : '部分核销'
    return { key, order: items[0]!.order_no, dealer: items[0]!.dealer_name, dealerId: items[0]!.dealer_id, ordered, remaining, status }
  })
}
export function dashboardRanges(day: string) {
  const last = new Date(`${day}T00:00:00Z`)
  last.setUTCDate(last.getUTCDate() - 29)
  return [
    { id: 'batch', label: '8.27—9.3', start: '2026-08-27', end: '2026-09-03' },
    { id: 'month', label: '本月', start: `${day.slice(0, 7)}-01`, end: day },
    { id: 'recent', label: '近 30 天', start: last.toISOString().slice(0, 10), end: day },
    { id: 'august', label: '8 月', start: '2026-08-01', end: '2026-08-31' },
  ]
}
export function summarize(rows: AnalyticsRow[], dates: string[]) {
  const daily = dates.map(date => ({ date, quantity: sumQty(rows, r => r.daily[date] ?? 0),
    lines: rows.filter(r => cents(r.daily[date] ?? 0) !== 0).length }))
  let balance = cents(sumQty(rows, r => r.opening_qty))
  const trend = daily.map(day => { balance -= cents(day.quantity); return { ...day, balance: balance / 100 } })
  return {
    daily: trend,
    orders: new Set(rows.map(r => `${r.dealer_id}:${r.order_no}`)).size,
    lines: rows.length,
    openLines: rows.filter(r => cents(r.closing_qty) > 0).length,
    closedLines: rows.filter(r => cents(r.closing_qty) === 0).length,
    opening: sumQty(rows, r => r.opening_qty),
    closing: sumQty(rows, r => r.closing_qty),
    quantity: daily.reduce((sum, day) => sum + cents(day.quantity), 0) / 100,
    activeDays: daily.filter(day => day.lines > 0).length,
  }
}
