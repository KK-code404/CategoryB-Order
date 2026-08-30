import { useCallback, useEffect, useMemo, useState } from 'react'
import { ReloadOutlined } from '@ant-design/icons'
import { App, Button, Empty, Input, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import { dataApi } from '../api/client'
import type { AuditEvent, OrderLine, ShipmentLine, User } from '../types'
import { formatChinaDateTime } from '../utils/date'
import { AdminSettingsPage } from './AdminSettingsPage'

interface Props { resource: string; user: User }

const titles: Record<string, string> = { orders: '订单台账', shipments: '发货申请', inbox: '邮件收件箱', audit: '操作日志', settings: '后台配置' }
// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将服务端稳定状态码转换为双方可理解的中文业务状态。
const shipmentLabels: Record<string, string> = { PENDING: '待确认', EXCEPTION: '匹配异常', RECONCILED: '已核销', REVERSED: '已冲销' }

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 为台账、申请、收件箱和日志提供统一的数据页面，同时保留各自的高密度表格字段。
export function ResourcePage({ resource, user }: Props) {
  const { message } = App.useApp()
  const [rows, setRows] = useState<Array<OrderLine | ShipmentLine | AuditEvent>>([])
  const [loading, setLoading] = useState(false)

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 根据导航资源选择对应接口并统一处理加载失败状态。
  const load = useCallback(async () => {
    if (resource === 'settings') return
    setLoading(true)
    try {
      const data = resource === 'orders' ? await dataApi.orders() : resource === 'audit' ? await dataApi.auditEvents() : await dataApi.shipmentLines()
      setRows(data)
    } catch (error) { message.error(error instanceof Error ? error.message : '数据加载失败') }
    finally { setLoading(false) }
  }, [message, resource])

  useEffect(() => { void load() }, [load])

  const columns = useMemo<TableColumnsType<Record<string, unknown>>>(() => {
    if (resource === 'orders') return [
      { title: '代理商', dataIndex: 'dealer_name' }, { title: '订单号', dataIndex: 'order_no' }, { title: '零件号', dataIndex: 'part_no' },
      { title: '物料号', dataIndex: 'material_no' }, { title: '品名', dataIndex: 'product_name', ellipsis: true },
      { title: '订单数量', dataIndex: 'ordered_qty', align: 'right' }, { title: '已核销', dataIndex: 'reconciled_qty', align: 'right' },
      { title: '剩余未发', dataIndex: 'remaining_qty', align: 'right', render: value => <strong className="text-success">{String(value)}</strong> }, { title: '单位', dataIndex: 'unit' },
    ]
    if (resource === 'audit') return [
      { title: '时间', dataIndex: 'created_at', render: value => formatChinaDateTime(String(value)) }, { title: '操作人', dataIndex: 'actor_name' },
      { title: '操作类型', dataIndex: 'action' }, { title: '对象类型', dataIndex: 'object_type' }, { title: '对象编号', dataIndex: 'object_id' },
      { title: '内容', dataIndex: 'detail', ellipsis: true }, { title: '结果', dataIndex: 'result' },
    ]
    return [
      { title: '申请编号', dataIndex: 'request_no' }, { title: '来源邮箱', dataIndex: 'sender_email' }, { title: '代理商', dataIndex: 'dealer_name' },
      { title: '订单号', dataIndex: 'order_no' }, { title: '物料号', dataIndex: 'material_no' }, { title: '零件号', dataIndex: 'part_no' },
      { title: '数量', dataIndex: 'quantity', align: 'right' }, { title: '发货日', dataIndex: 'requested_ship_date' },
      { title: '状态', dataIndex: 'status', render: value => <Tag color={value === 'RECONCILED' ? 'success' : value === 'EXCEPTION' ? 'warning' : 'processing'}>{shipmentLabels[String(value)] ?? String(value)}</Tag> },
    ]
  }, [resource])

  if (resource === 'settings') {
    return <AdminSettingsPage user={user} />
  }

  return (
    <div className="resource-page">
      <div className="page-title-row"><div><Typography.Title level={4}>{titles[resource]}</Typography.Title><Typography.Text type="secondary">{resource === 'inbox' ? '原始邮件与解析结果统一留档' : '实时数据，以平台核销流水为准'}</Typography.Text></div><Button icon={<ReloadOutlined />} onClick={load}>刷新</Button></div>
      <section className="surface resource-table"><Space className="filter-row"><Input.Search placeholder="搜索订单号、物料号或申请编号" allowClear /></Space><Table rowKey="id" loading={loading} columns={columns} dataSource={rows as unknown as Record<string, unknown>[]} scroll={{ x: 980 }} locale={{ emptyText: <Empty description="暂无数据" /> }} /></section>
    </div>
  )
}
