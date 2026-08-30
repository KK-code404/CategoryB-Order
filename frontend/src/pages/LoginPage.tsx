import { useState } from 'react'
import { ArrowRightOutlined, LockOutlined, UserOutlined } from '@ant-design/icons'
import { App, Button, Form, Input } from 'antd'
import { authApi } from '../api/client'
import type { User } from '../types'

interface Props { onSuccess: (user: User) => void }

// CHANGE [2026-08-30 18:05 +08:00] [WH400]: 提供兼容账号与邮箱的登录入口，并将错误限制在表单内反馈。
export function LoginPage({ onSuccess }: Props) {
  const { message } = App.useApp()
  const [submitting, setSubmitting] = useState(false)

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 登录失败留在当前表单提示，成功后才进入业务页面。
  const handleFinish = async (values: { email: string; password: string }) => {
    setSubmitting(true)
    try {
      onSuccess(await authApi.login(values.email, values.password))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-stage">
        <section className="login-panel" aria-labelledby="login-title">
          <div className="login-panel-topline">
            <div className="login-brand">
              <span className="brand-dot" aria-hidden="true" />
              <strong>油品订单平台</strong>
            </div>
            <span>管理入口</span>
          </div>

          <div className="login-heading">
            <h1 id="login-title">登录</h1>
            <p>订单、发货与核销统一管理</p>
          </div>

          <Form className="login-form" size="large" onFinish={handleFinish} requiredMark={false}>
            <Form.Item name="email" rules={[{ required: true, message: '请输入账号' }]}>
              <Input prefix={<UserOutlined />} placeholder="账号或邮箱" aria-label="账号" autoComplete="username" autoFocus />
            </Form.Item>
            <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
              <Input.Password prefix={<LockOutlined />} placeholder="密码" aria-label="密码" autoComplete="current-password" />
            </Form.Item>
            <div className="login-form-footer">
              <p>请使用管理员或业务账号登录。进入系统后即可处理订单与发货申请。</p>
              <Button className="login-submit" type="primary" shape="circle" htmlType="submit" loading={submitting} aria-label="登录系统" icon={<ArrowRightOutlined />} />
            </div>
          </Form>

          <div className="login-panel-footnote">安全连接 · 统一工作台</div>
        </section>

        <section className="login-discover" aria-hidden="true">
          <div><strong>New workspace</strong><span>订单协同中心</span></div>
          <span>Discover</span>
        </section>

        <aside className="login-event" aria-hidden="true">
          <div className="login-event-rail">
            <div className="login-event-date"><strong>Sun</strong><span>30th</span></div>
            <div className="login-event-place"><span>20:26</span><strong>Order Hub</strong><span>KK Workspace</span></div>
            <div className="login-event-mark"><i />KK Hub</div>
          </div>
          <div className="login-event-body">
            <div className="login-event-copy"><span>业务工作台</span><strong>统一处理中心</strong></div>
            <div className="login-event-orb" />
            <div className="login-event-enter"><span>进入系统</span><i><ArrowRightOutlined /></i></div>
          </div>
        </aside>
      </div>
    </main>
  )
}
