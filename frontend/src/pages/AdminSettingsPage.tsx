import { useCallback, useEffect, useMemo, useState } from 'react'
import { DownloadOutlined, InboxOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { App, Button, Form, Input, Modal, Select, Space, Table, Tabs, Typography, Upload } from 'antd'
import type { UploadProps } from 'antd'
import { dataApi } from '../api/client'
import type { AdminConfig, User } from '../types'

interface Props { user: User }
type CreateKind = 'dealer' | 'supplier' | 'material' | 'user'

const createTitles: Record<CreateKind, string> = { dealer: '新增代理商', supplier: '新增供应商', material: '新增物料映射', user: '新增用户' }

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供真实的订单导入和主数据维护界面，使试点扩展无需直接操作数据库。
export function AdminSettingsPage({ user }: Props) {
  const { message } = App.useApp()
  const [config, setConfig] = useState<AdminConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [importPreview, setImportPreview] = useState<{ token: string; valid_count: number; error_count: number; errors: Array<{ row: number; message: string }> } | null>(null)
  const [importing, setImporting] = useState(false)
  const [createKind, setCreateKind] = useState<CreateKind | null>(null)
  const [form] = Form.useForm()

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 一次刷新全部主数据，使跨表映射在同一页面保持一致。
  const load = useCallback(async () => {
    setLoading(true)
    try { setConfig(await dataApi.adminConfig()) }
    catch (error) { message.error(error instanceof Error ? error.message : '配置加载失败') }
    finally { setLoading(false) }
  }, [message])

  useEffect(() => { void load() }, [load])

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 拦截默认直传并改为平台“预览校验—人工确认”两阶段导入。
  const uploadProps: UploadProps = useMemo(() => ({
    accept: '.xlsx', maxCount: 1, showUploadList: false,
    beforeUpload(file) {
      setImporting(true)
      void dataApi.previewOrderImport(file as File).then(result => { setImportPreview(result); message.success('订单文件校验完成') }).catch(error => message.error(error instanceof Error ? error.message : '订单文件校验失败')).finally(() => setImporting(false))
      return false
    },
  }), [message])

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 只有无错误预览才能提交，提交成功后立即关闭确认窗口。
  const commitImport = async () => {
    if (!importPreview) return
    try {
      const result = await dataApi.commitOrderImport(importPreview.token)
      message.success(`已导入 ${result.imported} 行订单`)
      setImportPreview(null)
    } catch (error) { message.error(error instanceof Error ? error.message : '订单导入失败') }
  }

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 切换主数据类型时清空旧表单，避免字段串用。
  const openCreate = (kind: CreateKind) => { form.resetFields(); setCreateKind(kind) }

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 按当前配置类型调用最小新增接口，并在成功后刷新关联选项。
  const submitCreate = async () => {
    if (!createKind) return
    const values = await form.validateFields()
    try {
      if (createKind === 'dealer') await dataApi.createDealer(values)
      if (createKind === 'supplier') await dataApi.createSupplier(values)
      if (createKind === 'material') await dataApi.createMaterial(values)
      if (createKind === 'user') await dataApi.createUser(values)
      message.success(`${createTitles[createKind]}成功`)
      setCreateKind(null)
      await load()
    } catch (error) { message.error(error instanceof Error ? error.message : '保存失败') }
  }

  const tableItems = [
    { key: 'materials', label: `物料映射（${config?.materials.length ?? 0}）`, children: <Table rowKey="id" size="small" loading={loading} dataSource={config?.materials ?? []} columns={[{ title: '物料号', dataIndex: 'material_no' }, { title: '零件号', dataIndex: 'part_no' }, { title: '品名', dataIndex: 'product_name', ellipsis: true }, { title: '品牌', dataIndex: 'brand_code' }, { title: '供应商', dataIndex: 'supplier_code' }]} pagination={false} /> },
    { key: 'dealers', label: `代理商（${config?.dealers.length ?? 0}）`, children: <Table rowKey="id" size="small" loading={loading} dataSource={config?.dealers ?? []} columns={[{ title: '编码', dataIndex: 'code' }, { title: '名称', dataIndex: 'name' }, { title: '发件邮箱', dataIndex: 'email' }]} pagination={false} /> },
    { key: 'suppliers', label: `供应商（${config?.suppliers.length ?? 0}）`, children: <Table rowKey="id" size="small" loading={loading} dataSource={config?.suppliers ?? []} columns={[{ title: '编码', dataIndex: 'code' }, { title: '名称', dataIndex: 'name' }, { title: '收件邮箱', dataIndex: 'email' }]} pagination={false} /> },
    { key: 'users', label: `用户（${config?.users.length ?? 0}）`, children: <Table rowKey="id" size="small" loading={loading} dataSource={config?.users ?? []} columns={[{ title: '姓名', dataIndex: 'display_name' }, { title: '邮箱', dataIndex: 'email' }, { title: '角色', dataIndex: 'role' }, { title: '代理商', dataIndex: 'dealer_code', render: value => value || '—' }]} pagination={false} /> },
  ]

  return <div className="resource-page">
    <div className="page-title-row"><div><Typography.Title level={4}>后台配置</Typography.Title><Typography.Text type="secondary">维护账号、邮件归属和供应商路由</Typography.Text></div><Button icon={<ReloadOutlined />} onClick={load}>刷新</Button></div>
    <div className="settings-grid">
      <section className="surface settings-section"><h3>订单批量导入</h3><p>先校验 Excel，再确认写入；示例行请在正式上传前替换或删除。</p><Space className="template-links" wrap><Button icon={<DownloadOutlined />} href="/templates/销售订单导入模板.xlsx" download>下载订单模板</Button><Button icon={<DownloadOutlined />} href="/templates/发货申请标准模板.xlsx" download>下载发货模板</Button></Space><Upload.Dragger {...uploadProps} disabled={importing}><p className="ant-upload-drag-icon"><InboxOutlined /></p><p>{importing ? '正在校验…' : '点击或拖放订单 Excel 到此处'}</p><p className="muted">仅支持无宏 .xlsx，单文件不超过 5 MB</p></Upload.Dragger></section>
      <section className="surface settings-section"><h3>新增主数据</h3><p>所有新增动作都会写入操作日志。</p><Space direction="vertical" style={{ width: '100%' }}><Button block icon={<PlusOutlined />} onClick={() => openCreate('dealer')}>新增代理商</Button><Button block icon={<PlusOutlined />} onClick={() => openCreate('supplier')}>新增供应商</Button><Button block icon={<PlusOutlined />} onClick={() => openCreate('material')}>新增物料映射</Button><Button block icon={<PlusOutlined />} onClick={() => openCreate('user')}>新增用户</Button></Space><dl><dt>当前账号</dt><dd>{user.display_name} / 管理员</dd><dt>邮件抓取</dt><dd>IMAP 每分钟轮询</dd><dt>供应商通知</dt><dd>失败自动重试 5 次</dd></dl></section>
    </div>
    <section className="surface config-tables"><Tabs items={tableItems} /></section>

    {/* CHANGE [2026-08-30 12:58 +08:00] [WH400]: 预渲染表单以确保重置操作始终连接真实表单实例，消除管理弹窗的运行时警告。 */}
    <Modal title={createKind ? createTitles[createKind] : ''} open={Boolean(createKind)} onCancel={() => setCreateKind(null)} onOk={submitCreate} okText="保存" destroyOnHidden forceRender>
      <Form form={form} layout="vertical">
        {createKind === 'dealer' || createKind === 'supplier' ? <><Form.Item name="code" label="编码" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="email" label={createKind === 'dealer' ? '发件邮箱' : '供应商收件邮箱'} rules={[{ required: true, type: 'email' }]}><Input /></Form.Item></> : null}
        {createKind === 'material' ? <><Form.Item name="material_no" label="物料号" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="part_no" label="零件号" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="product_name" label="品名" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="brand_code" label="品牌编码" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="supplier_code" label="供应商" rules={[{ required: true }]}><Select options={(config?.suppliers ?? []).map(item => ({ value: item.code, label: `${item.code} · ${item.name}` }))} /></Form.Item></> : null}
        {createKind === 'user' ? <><Form.Item name="display_name" label="姓名" rules={[{ required: true }]}><Input /></Form.Item><Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}><Input /></Form.Item><Form.Item name="password" label="初始密码" rules={[{ required: true, min: 10 }]}><Input.Password /></Form.Item><Form.Item name="role" label="角色" rules={[{ required: true }]}><Select options={[{ value: 'ADMIN', label: '管理员' }, { value: 'SALES', label: '零件销售' }, { value: 'DEALER', label: '代理商' }]} /></Form.Item><Form.Item noStyle shouldUpdate={(previous, current) => previous.role !== current.role}>{({ getFieldValue }) => getFieldValue('role') === 'DEALER' ? <Form.Item name="dealer_code" label="绑定代理商" rules={[{ required: true }]}><Select options={(config?.dealers ?? []).map(item => ({ value: item.code, label: `${item.code} · ${item.name}` }))} /></Form.Item> : null}</Form.Item></> : null}
      </Form>
    </Modal>
    <Modal title="订单导入校验结果" open={Boolean(importPreview)} onCancel={() => setImportPreview(null)} onOk={commitImport} okText="确认导入" okButtonProps={{ disabled: Boolean(importPreview?.error_count) }}><p>有效数据：<strong>{importPreview?.valid_count ?? 0}</strong> 行；错误：<strong className={importPreview?.error_count ? 'text-warning' : 'text-success'}>{importPreview?.error_count ?? 0}</strong> 行。</p>{importPreview?.errors.map(error => <p key={`${error.row}-${error.message}`}>第 {error.row} 行：{error.message}</p>)}</Modal>
  </div>
}
