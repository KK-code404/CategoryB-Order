import { useEffect, useState } from 'react'
import { App as AntApp, Spin } from 'antd'
import { authApi } from './api/client'
import type { User } from './types'
import { LoginPage } from './pages/LoginPage'
import { AppShell } from './components/AppShell'

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 在显示业务数据前恢复服务端会话，避免未授权内容短暂闪现。
export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    authApi.me().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="app-loading" aria-label="正在载入核销平台"><Spin size="large" /></div>
  }

  return (
    <AntApp>
      {user ? <AppShell user={user} onLogout={() => setUser(null)} /> : <LoginPage onSuccess={setUser} />}
    </AntApp>
  )
}
