import { LockOutlined, MailOutlined } from '@ant-design/icons'
import { App, Button, Form, Input } from 'antd'
import { authApi } from '../api/client'
import type { User } from '../types'

interface Props { onSuccess: (user: User) => void }

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供统一邮箱密码入口，并将错误限制在登录表单内反馈。
export function LoginPage({ onSuccess }: Props) {
  const { message } = App.useApp()

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 登录失败留在当前表单提示，成功后才进入业务页面。
  const handleFinish = async (values: { email: string; password: string }) => {
    try {
      onSuccess(await authApi.login(values.email, values.password))
    } catch (error) {
      message.error(error instanceof Error ? error.message : '登录失败')
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand-mark" aria-hidden="true">滴</div>
        <h1 id="login-title">油品发货核销平台</h1>
        <p>订单余额、分批发货与操作记录统一管理</p>
        <Form layout="vertical" size="large" onFinish={handleFinish} requiredMark={false}>
          <Form.Item label="邮箱" name="email" rules={[{ required: true, type: 'email', message: '请输入有效邮箱' }]}>
            <Input prefix={<MailOutlined />} placeholder="name@example.com" autoComplete="email" />
          </Form.Item>
          <Form.Item label="密码" name="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block>登录</Button>
        </Form>
      </section>
    </main>
  )
}
