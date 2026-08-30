import { useState } from 'react'
import {
  AuditOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  MailOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SendOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { App, Avatar, Button, Layout, Menu, Space, Typography } from 'antd'
import { authApi } from '../api/client'
import type { User } from '../types'
import { DashboardPage } from '../pages/DashboardPage'
import { ResourcePage } from '../pages/ResourcePage'

const { Header, Sider, Content } = Layout

interface Props { user: User; onLogout: () => void }

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 用稳定应用壳承载角色化导航和响应式折叠，避免各页面重复布局状态。
export function AppShell({ user, onLogout }: Props) {
  const { message } = App.useApp()
  const [active, setActive] = useState('dashboard')
  const [collapsed, setCollapsed] = useState(false)
  const [mobile, setMobile] = useState(false)

  const items = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: '工作台' },
    { key: 'orders', icon: <DatabaseOutlined />, label: '订单台账' },
    { key: 'shipments', icon: <SendOutlined />, label: '发货申请' },
    { key: 'inbox', icon: <MailOutlined />, label: '邮件收件箱' },
    { key: 'audit', icon: <AuditOutlined />, label: '操作日志' },
    ...(user.role === 'ADMIN' ? [{ key: 'settings', icon: <SettingOutlined />, label: '后台配置' }] : []),
  ]

  // CHANGE [2026-08-30 12:58 +08:00] [WH400]: 先清除服务端 Cookie 再释放本地用户状态，避免退出后仍可访问数据。
  const handleLogout = async () => {
    try { await authApi.logout() } finally { message.success('已安全退出'); onLogout() }
  }

  return (
    <Layout className="app-shell">
      {mobile && !collapsed ? <button className="sider-backdrop" aria-label="关闭导航菜单" onClick={() => setCollapsed(true)} /> : null}
      <Sider
        className={`app-sider${mobile ? ' is-mobile' : ''}`}
        width={216}
        collapsedWidth={mobile ? 0 : 72}
        collapsible
        collapsed={collapsed}
        trigger={null}
        breakpoint="lg"
        onBreakpoint={broken => { setMobile(broken); setCollapsed(broken) }}
      >
        <div className="sider-brand" aria-label="油品订单平台">
          <span className="header-drop" aria-hidden="true">滴</span>
          {collapsed ? null : <strong>油品订单平台</strong>}
        </div>
        <Menu mode="inline" selectedKeys={[active]} items={items} onClick={({ key }) => { setActive(key); if (mobile) setCollapsed(true) }} />
        <Button className="sider-toggle" type="text" icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />} aria-label={collapsed ? '展开导航菜单' : '收起导航菜单'} onClick={() => setCollapsed(value => !value)}>
          {collapsed ? null : '收起菜单'}
        </Button>
      </Sider>
      <Layout className="app-main">
        <Header className="app-header">
          <Button
            type="text"
            className="mobile-menu-button"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            aria-label={collapsed ? '展开导航菜单' : '收起导航菜单'}
            onClick={() => setCollapsed(value => !value)}
          />
          <Space size={12} className="header-profile">
            <Avatar size="small">{user.display_name.slice(0, 1)}</Avatar>
            <span className="header-identity">
              <Typography.Text className="header-user">{user.display_name}</Typography.Text>
              <Typography.Text className="header-role">{user.role === 'DEALER' ? '代理商' : '系统管理员'}</Typography.Text>
            </span>
            <Button type="text" className="header-action" icon={<LogoutOutlined />} aria-label="退出登录" onClick={handleLogout} />
          </Space>
        </Header>
        <Content className="app-content">
          {active === 'dashboard' ? <DashboardPage user={user} /> : <ResourcePage resource={active} user={user} />}
        </Content>
      </Layout>
    </Layout>
  )
}
