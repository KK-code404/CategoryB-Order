// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 统一前后端业务对象类型，避免订单余额和核销状态在页面间产生歧义。
export type Role = 'ADMIN' | 'SALES' | 'DEALER'

export interface User {
  id: number
  email: string
  display_name: string
  role: Role
  dealer_id: number | null
}

export type ShipmentStatus = 'PENDING' | 'EXCEPTION' | 'RECONCILED' | 'REVERSED'

export interface DashboardStats {
  pending_emails: number
  match_exceptions: number
  reconciled_today: number
  remaining_stock: number
  material_count: number
}

export interface ShipmentLine {
  id: number
  request_id: number
  request_no: string
  sender_email: string
  dealer_name: string
  received_at: string
  requested_ship_date: string
  order_no: string
  material_no: string
  part_no: string | null
  product_name: string
  quantity: number
  receiver: string
  phone: string
  address: string
  remark: string
  status: ShipmentStatus
  confidence: number | null
  exception_reason: string | null
  ai_suggestion_json: string | null
  ordered_qty: number | null
  reconciled_qty: number | null
  remaining_qty: number | null
  supplier_name: string | null
}

export interface ShipmentRequest {
  id: number
  request_no: string
  sender_email: string
  dealer_name: string
  subject: string
  batch_no: string
  attachment_name: string
  received_at: string
  line_count: number
  pending_count: number
  exception_count: number
  reconciled_count: number
  reversed_count: number
}

export type MailStatus = 'PENDING' | 'SENT' | 'FAILED'

export interface OutboundMail {
  id: number
  kind: string
  recipient: string
  subject: string
  status: MailStatus
  attempts: number
  last_error: string | null
  sent_at: string | null
  created_at: string
}

export interface OrderLine {
  id: number
  dealer_name: string
  order_no: string
  part_no: string
  material_no: string
  product_name: string
  ordered_qty: number
  reconciled_qty: number
  remaining_qty: number
  unit: string
  version: number
}

export interface AuditEvent {
  id: number
  created_at: string
  actor_name: string
  action: string
  object_type: string
  object_id: string
  detail: string
  result: string
}

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: Decimal 接口值按字符串或数字读取，区分本月流水与全期订单余额。
export interface DailyShipmentRow extends Omit<OrderLine, 'ordered_qty' | 'reconciled_qty' | 'remaining_qty'> {
  dealer_id: number
  dealer_code: string
  ordered_qty: number | string
  reconciled_qty: number | string
  remaining_qty: number | string
  undated_qty: number | string
  month_qty: number | string
  daily: Record<string, number | string>
}

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 日历列由后端自然月生成，避免前后端时区或闰年不一致。
export interface DailyShipmentReport {
  month: string
  date_basis: 'requested_ship_date'
  dates: string[]
  rows: DailyShipmentRow[]
}

export interface DashboardPayload {
  stats: DashboardStats
  lines: ShipmentLine[]
  audit_events: AuditEvent[]
}

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 定义后台可维护的账号、代理商、供应商和物料映射清单。
export interface AdminConfig {
  dealers: Array<{ id: number; code: string; name: string; email: string; active: boolean }>
  suppliers: Array<{ id: number; code: string; name: string; email: string; active: boolean }>
  materials: Array<{ id: number; material_no: string; part_no: string; product_name: string; brand_code: string; supplier_code: string }>
  users: Array<{ id: number; email: string; display_name: string; role: Role; dealer_code: string | null; active: boolean }>
}
