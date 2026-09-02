import type {
  AdminConfig,
  DashboardPayload,
  OrderLine,
  OutboundMail,
  ShipmentLine,
  ShipmentRequest,
  User,
} from '../types'

export const admin: User = { id: 1, email: 'admin-test', display_name: '测试管理员', role: 'ADMIN', dealer_id: null }
export const dealer: User = { ...admin, id: 2, role: 'DEALER', dealer_id: 1 }
export const line: ShipmentLine = {
  id: 11,
  request_id: 1,
  request_no: 'REQ-TEST-001',
  sender_email: 'dealer@example.com',
  dealer_name: '测试代理商',
  received_at: '2026-09-03T02:30:00Z',
  requested_ship_date: '2026-09-04',
  order_no: 'ORDER-001',
  material_no: 'MAT-001',
  part_no: 'PART-001',
  product_name: '测试油品',
  quantity: 10,
  receiver: '测试收货人',
  phone: '13800000000',
  address: '测试地址',
  remark: '',
  status: 'PENDING',
  confidence: 1,
  exception_reason: null,
  ai_suggestion_json: null,
  ordered_qty: 100,
  reconciled_qty: 20,
  remaining_qty: 80,
  supplier_name: '测试供应商',
}
export const request: ShipmentRequest = {
  id: 1,
  request_no: line.request_no,
  sender_email: line.sender_email,
  dealer_name: line.dealer_name,
  subject: '[发货申请] TEST B001',
  batch_no: 'B001',
  attachment_name: '申请.xlsx',
  received_at: line.received_at,
  line_count: 1,
  pending_count: 1,
  exception_count: 0,
  reconciled_count: 0,
  reversed_count: 0,
}
export const mail: OutboundMail = {
  id: 12,
  kind: 'SHIPMENT',
  recipient: 'supplier@example.com',
  subject: '发货指令',
  status: 'FAILED',
  attempts: 5,
  last_error: '测试发送失败',
  sent_at: null,
  created_at: line.received_at,
}
export const order: OrderLine = {
  id: 1,
  dealer_name: line.dealer_name,
  order_no: line.order_no,
  part_no: 'PART-001',
  material_no: line.material_no,
  product_name: line.product_name,
  ordered_qty: 100,
  reconciled_qty: 20,
  remaining_qty: 80,
  unit: '桶',
  version: 1,
}
export const dashboard: DashboardPayload = {
  stats: { pending_emails: 1, match_exceptions: 0, reconciled_today: 2, remaining_stock: 80, material_count: 1 },
  lines: [line],
  audit_events: [
    {
      id: 1,
      created_at: line.received_at,
      actor_name: '测试销售',
      action: '核销',
      object_type: '申请',
      object_id: '10',
      detail: '测试核销记录',
      result: '成功',
    },
  ],
}
export const config: AdminConfig = {
  dealers: [{ id: 1, code: 'DL01', name: line.dealer_name, email: line.sender_email, active: true }],
  suppliers: [{ id: 1, code: 'SP01', name: '测试供应商', email: mail.recipient, active: true }],
  materials: [
    {
      id: 1,
      material_no: line.material_no,
      part_no: 'PART-001',
      product_name: line.product_name,
      brand_code: 'BR01',
      supplier_code: 'SP01',
    },
  ],
  users: [
    { id: 3, email: 'sales-test', display_name: '测试销售', role: 'SALES', dealer_code: null, active: true },
    { ...admin, dealer_code: null, active: true },
  ],
}
