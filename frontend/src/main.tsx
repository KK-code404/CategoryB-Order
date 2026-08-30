import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import './styles.css'

// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 注入中文本地化与统一设计令牌，保持业务控件和概念图一致。
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1677ff',
          colorSuccess: '#16a36a',
          colorWarning: '#f5a623',
          colorError: '#e5484d',
          colorText: '#172033',
          colorBorder: '#e5eaf2',
          borderRadius: 6,
          fontFamily: 'Inter, PingFang SC, Microsoft YaHei, sans-serif',
          fontSize: 13,
        },
        components: {
          Table: { headerBg: '#f7f9fc', headerColor: '#33415c', cellPaddingBlockSM: 10 },
          Layout: { bodyBg: '#f4f7fb', siderBg: '#062b5c', headerBg: '#062b5c' },
          Menu: { darkItemBg: '#062b5c', darkSubMenuItemBg: '#062b5c', darkItemSelectedBg: '#0d63ce' },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)

