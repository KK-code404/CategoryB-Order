import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  MailOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { App, Button, DatePicker, Descriptions, Empty, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import type { TableColumnsType } from 'antd'
import dayjs from 'dayjs'
import { dataApi } from '../api/client'
import type { AuditEvent, DashboardPayload, ShipmentLine, User } from '../types'
import { formatChinaDateTime } from '../utils/date'

interface Props { user: User }

const statusLabel = { PENDING: '待确认', EXCEPTION: '匹配异常', RECONCILED: '已核销', REVERSED: '已冲销' }
const statusColor = { PENDING: 'processing', EXCEPTION: 'warning', RECONCILED: 'success', REVERSED: 'default' }

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 将状态样式集中映射，保证列表与详情对同一业务状态使用一致表达。
function StatusTag({ status }: { status: ShipmentLine['status'] }) {
  return <Tag color={statusColor[status]}>{statusLabel[status]}</Tag>
}

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 构建可直接完成逐行核销、异常修正和审计追踪的主工作台。
export function DashboardPage({ user }: Props) {
  const { message } = App.useApp()
  const [payload, setPayload] = useState<DashboardPayload | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [form] = Form.useForm()

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 刷新时同步统计、明细和审计，且尽量保留当前选中行。
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await dataApi.dashboard()
      setPayload(data)
      setSelectedId(current => current && data.lines.some(line => line.id === current) ? current : data.lines[0]?.id ?? null)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '工作台加载失败')
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => { void load() }, [load])

  const selected = payload?.lines.find(line => line.id === selectedId) ?? null

  const columns = useMemo<TableColumnsType<ShipmentLine>>(() => [
    { title: '申请编号', dataIndex: 'request_no', width: 168, ellipsis: true },
    { title: '来源邮箱', dataIndex: 'sender_email', width: 150, ellipsis: true },
    { title: '客户', dataIndex: 'dealer_name', width: 130, ellipsis: true },
    { title: '申请日期', dataIndex: 'received_at', width: 132, render: value => formatChinaDateTime(value).slice(0, 16) },
    { title: '订单号', dataIndex: 'order_no', width: 100 },
    { title: '零件号', dataIndex: 'part_no', width: 92, render: value => value || '—' },
    { title: '申请数量', dataIndex: 'quantity', width: 82, align: 'right' },
    { title: '匹配状态', dataIndex: 'status', width: 92, render: value => <StatusTag status={value} /> },
    { title: '操作', width: 64, fixed: 'right', render: (_, line) => <Button type="link" size="small" onClick={() => setSelectedId(line.id)}>查看</Button> },
  ], [])

  const auditColumns = useMemo<TableColumnsType<AuditEvent>>(() => [
    { title: '时间', dataIndex: 'created_at', width: 150, render: value => formatChinaDateTime(value) },
    { title: '操作人', dataIndex: 'actor_name', width: 100 },
    { title: '操作类型', dataIndex: 'action', width: 110 },
    { title: '对象编号', dataIndex: 'object_id', width: 170 },
    { title: '操作内容', dataIndex: 'detail', ellipsis: true },
    { title: '结果', dataIndex: 'result', width: 70, render: value => <span className={value === '成功' ? 'text-success' : 'text-warning'}>{value}</span> },
  ], [])

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 核销成功后重新读取服务端余额，避免客户端自行推算造成偏差。
  const handleConfirm = async () => {
    if (!selected) return
    try {
      await dataApi.confirmLines([selected.id])
      message.success('核销成功，供应商发货邮件已进入发送队列')
      await load()
    } catch (error) { message.error(error instanceof Error ? error.message : '核销失败') }
  }

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 仅将当前可编辑申请填入表单，不在打开弹窗时修改服务端状态。
  const startEdit = () => {
    if (!selected) return
    form.setFieldsValue({ ...selected, requested_ship_date: dayjs(selected.requested_ship_date) })
    setEditing(true)
  }

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 保存修正后触发服务端重新匹配并刷新整个工作台。
  const handleEdit = async () => {
    if (!selected) return
    const values = await form.validateFields()
    try {
      await dataApi.updateLine(selected.id, { ...values, requested_ship_date: values.requested_ship_date.format('YYYY-MM-DD') })
      message.success('申请已更新并重新匹配')
      setEditing(false)
      await load()
    } catch (error) { message.error(error instanceof Error ? error.message : '修改失败') }
  }

  const stats = payload?.stats
  const balanceBefore = selected?.remaining_qty == null ? null : selected.status === 'RECONCILED' ? Number(selected.remaining_qty) + Number(selected.quantity) : Number(selected.remaining_qty)
  const balanceAfter = selected?.remaining_qty == null ? null : selected.status === 'RECONCILED' ? Number(selected.remaining_qty) : Number(selected.remaining_qty) - Number(selected.quantity)

  return (
    <div className="dashboard-page">
      <section className="stat-strip" aria-label="今日核销概览">
        <div className="stat-item"><MailOutlined className="stat-icon blue" /><div><span>待处理邮件</span><strong>{stats?.pending_emails ?? 0}</strong><small>等待销售确认</small></div></div>
        <div className="stat-item"><WarningOutlined className="stat-icon amber" /><div><span>匹配异常</span><strong>{stats?.match_exceptions ?? 0}</strong><small>需要人工修正</small></div></div>
        <div className="stat-item"><CheckCircleOutlined className="stat-icon green" /><div><span>今日已核销</span><strong>{stats?.reconciled_today ?? 0}</strong><small>条发货明细</small></div></div>
        <div className="stat-item"><DatabaseOutlined className="stat-icon blue" /><div><span>待发库存（可用）</span><strong>{(stats?.remaining_stock ?? 0).toLocaleString()}</strong><small>{stats?.material_count ?? 0} 个物料</small></div></div>
      </section>

      <section className="workspace-grid">
        <div className="workspace-list surface">
          <div className="section-heading"><Typography.Title level={5}>待核销发货申请</Typography.Title><Button icon={<ReloadOutlined />} onClick={load}>刷新</Button></div>
          <Space className="filter-row" wrap>
            <Select defaultValue="all" options={[{ value: 'all', label: '全部状态' }, { value: 'PENDING', label: '待确认' }, { value: 'EXCEPTION', label: '匹配异常' }]} />
            <Select defaultValue="all" options={[{ value: 'all', label: '全部客户' }]} />
            <DatePicker.RangePicker />
            <Input.Search placeholder="搜索申请号/订单号/零件号" allowClear />
          </Space>
          <Table
            rowKey="id"
            size="small"
            loading={loading}
            columns={columns}
            dataSource={payload?.lines ?? []}
            scroll={{ x: 1030, y: 390 }}
            pagination={{ pageSize: 8, showSizeChanger: false, showTotal: total => `共 ${total} 条` }}
            rowClassName={line => line.id === selectedId ? 'selected-row' : ''}
            onRow={line => ({ onClick: () => setSelectedId(line.id) })}
          />
        </div>

        <aside className="request-detail surface" aria-label="申请详情">
          {selected ? <>
            <div className="section-heading"><Typography.Title level={5}>申请详情 <small>{selected.request_no}</small></Typography.Title><StatusTag status={selected.status} /></div>
            <h3>邮件摘要</h3>
            <Descriptions size="small" column={2} colon={false} items={[
              { key: 'email', label: '来源邮箱', children: selected.sender_email },
              { key: 'date', label: '期望发货日', children: selected.requested_ship_date },
              { key: 'dealer', label: '客户', children: selected.dealer_name },
              { key: 'address', label: '收货地址', children: selected.address },
              { key: 'remark', label: '备注', span: 2, children: selected.remark || '无' },
            ]} />
            <h3>申请明细 <small>（系统解析结果，可编辑）</small></h3>
            <div className="detail-line"><div><span>零件号</span><strong>{selected.part_no || '待匹配'}</strong></div><div className="grow"><span>品名</span><strong>{selected.product_name}</strong></div><div><span>申请数量</span><strong>{selected.quantity}</strong></div></div>
            <h3>匹配结果 <small>（以订单台账为准）</small></h3>
            <Descriptions bordered size="small" column={3} items={[
              { key: 'order', label: '订单号', children: selected.order_no },
              { key: 'ordered', label: '订单数量', children: selected.ordered_qty ?? '—' },
              { key: 'reconciled', label: '已核销量', children: selected.reconciled_qty ?? '—' },
              { key: 'remaining', label: '核销前余额', children: <span className="text-success">{balanceBefore ?? '—'}</span> },
              { key: 'current', label: '本次申请', children: selected.quantity },
              { key: 'after', label: '核销后余额', children: balanceAfter ?? '—' },
            ]} />
            <div className={`match-message ${selected.status === 'EXCEPTION' ? 'error' : 'success'}`}>
              {selected.status === 'EXCEPTION' ? selected.exception_reason : selected.status === 'RECONCILED' ? '核销完成：供应商发货指令已进入发送队列。' : selected.status === 'REVERSED' ? '该明细已冲销，订单余额已恢复。' : '匹配成功：申请数量未超过剩余未发数量，可核销。'}
            </div>
            <div className="detail-actions">
              {user.role !== 'DEALER' ? <Button type="primary" disabled={selected.status !== 'PENDING'} onClick={handleConfirm}>确认核销</Button> : null}
              <Button disabled={!['PENDING', 'EXCEPTION'].includes(selected.status)} onClick={startEdit}>修改申请</Button>
            </div>
          </> : <Empty description="请选择一条发货申请" />}
        </aside>
      </section>

      <section className="audit-panel surface">
        <div className="section-heading"><Typography.Title level={5}>最近操作记录</Typography.Title><Button type="link">查看更多</Button></div>
        <Table rowKey="id" size="small" columns={auditColumns} dataSource={payload?.audit_events ?? []} pagination={false} scroll={{ x: 900 }} />
      </section>

      <Modal title="修改待处理申请" open={editing} onCancel={() => setEditing(false)} onOk={handleEdit} okText="保存并重新匹配" destroyOnHidden>
        <Form form={form} layout="vertical">
          <Form.Item name="order_no" label="订单号" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="material_no" label="物料号" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="quantity" label="数量" rules={[{ required: true }]}><InputNumber min={1} precision={0} style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="requested_ship_date" label="要求发货日期" rules={[{ required: true }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
          <Form.Item name="receiver" label="收货人" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="phone" label="联系电话" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="address" label="收货地址" rules={[{ required: true }]}><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
