// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 将风险依据和只读沙盘计算集中为可测试规则，不将启发式提示伪装成 AI 预测。
import type { DailyShipmentRow, OutboundMail, ShipmentLine } from '../types'

export interface RiskItem {
  id: string; category: '逾期待处理' | '匹配异常' | '邮件失败'; title: string; reason: string
  destination: 'shipments' | 'inbox'; priority: number
}

// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 统一上海自然日，避免浏览器时区改变逾期判断。
export function chinaDay(now = new Date()): string {
  return now.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' })
}

// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 保留每项命中依据和业务处理入口，已核销行不产生待处理预警。
export function buildRisks(lines: ShipmentLine[], mails: OutboundMail[], today: string): RiskItem[] {
  const risks: RiskItem[] = []
  for (const line of lines) {
    if (!['PENDING', 'EXCEPTION'].includes(line.status)) continue
    const title = `${line.request_no} · ${line.order_no} · ${line.part_no || line.material_no}`
    if (line.requested_ship_date < today) risks.push({ id: `late-${line.id}`, category: '逾期待处理', title,
      reason: `要求发货日 ${line.requested_ship_date} 已过，申请仍未核销；请先核实需求是否有效。`, destination: 'shipments', priority: 0 })
    if (line.status === 'EXCEPTION') risks.push({ id: `exception-${line.id}`, category: '匹配异常', title,
      reason: line.exception_reason || '规则匹配未通过，请人工核对订单及物料。', destination: 'shipments', priority: 1 })
  }
  for (const mail of mails) if (mail.status === 'FAILED') risks.push({ id: `mail-${mail.id}`, category: '邮件失败', title: mail.subject,
    reason: `已尝试 ${mail.attempts} 次。请到邮件收件箱的发信记录检查失败原因；核销余额不会自动回退。`, destination: 'inbox', priority: 0 })
  return risks.sort((a, b) => a.priority - b.priority || a.id.localeCompare(b.id))
}

// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 采用百分位整数校验数量，拒绝负数、超精度和空值，确保模拟不掩盖超扣。
export function quantityUnits(value: string | number): number | null {
  if (!/^\d+(\.\d{1,2})?$/.test(String(value))) return null
  const result = Math.round(Number(value) * 100)
  return Number.isSafeInteger(result) ? result : null
}

// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 只计算单一订单行的快照差额，不写入真实库存或合并不同单位。
export function simulate(row: DailyShipmentRow, quantity: string) {
  const requested = quantityUnits(quantity)
  const balance = quantityUnits(row.remaining_qty)
  if (requested === null || requested <= 0 || balance === null) return { valid: false, after: null, shortage: null }
  return { valid: true, after: (balance - requested) / 100, shortage: Math.max(0, requested - balance) / 100 }
}
