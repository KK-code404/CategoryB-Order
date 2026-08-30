import type { AdminConfig, AuditEvent, DashboardPayload, OrderLine, ShipmentLine, User } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 统一携带安全 Cookie 并解析接口错误，让所有页面获得一致的失败反馈。
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(body.detail || `请求失败（${response.status}）`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供最小认证接口并依赖 HttpOnly Cookie 保存会话。
export const authApi = {
  me: () => request<User>('/auth/me'),
  login: (email: string, password: string) => request<User>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
}

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将独立读取并行化，减少工作台首屏等待时间。
export const dataApi = {
  dashboard: () => request<DashboardPayload>('/dashboard'),
  orders: () => request<OrderLine[]>('/orders'),
  shipmentLines: () => request<ShipmentLine[]>('/shipment-lines'),
  auditEvents: () => request<AuditEvent[]>('/audit-events'),
  confirmLines: (lineIds: number[]) => request<{ confirmed: number; outbound_mails: number }>('/shipment-lines/confirm', { method: 'POST', body: JSON.stringify({ line_ids: lineIds }) }),
  updateLine: (lineId: number, values: Partial<ShipmentLine>) => request<ShipmentLine>(`/shipment-lines/${lineId}`, { method: 'PATCH', body: JSON.stringify(values) }),
  reverseLine: (lineId: number, reason: string) => request<ShipmentLine>(`/shipment-lines/${lineId}/reverse`, { method: 'POST', body: JSON.stringify({ reason }) }),
  retryMail: (mailId: number) => request<void>(`/outbound-mails/${mailId}/retry`, { method: 'POST' }),
  previewOrderImport: (file: File) => {
    const body = new FormData()
    body.append('file', file)
    return request<{ token: string; valid_count: number; error_count: number; errors: Array<{ row: number; message: string }> }>('/orders/import/preview', { method: 'POST', body })
  },
  commitOrderImport: (token: string) => request<{ imported: number }>(`/orders/import/${token}/commit`, { method: 'POST' }),
  adminConfig: () => request<AdminConfig>('/admin/config'),
  createDealer: (values: Record<string, unknown>) => request<{ id: number }>('/admin/dealers', { method: 'POST', body: JSON.stringify(values) }),
  createSupplier: (values: Record<string, unknown>) => request<{ id: number }>('/admin/suppliers', { method: 'POST', body: JSON.stringify(values) }),
  createMaterial: (values: Record<string, unknown>) => request<{ id: number }>('/admin/materials', { method: 'POST', body: JSON.stringify(values) }),
  createUser: (values: Record<string, unknown>) => request<{ id: number }>('/admin/users', { method: 'POST', body: JSON.stringify(values) }),
}
