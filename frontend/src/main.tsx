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
          colorPrimary: '#665cf6',
          colorSuccess: '#138a5b',
          colorWarning: '#ad6800',
          colorError: '#c73a43',
          colorText: '#292743',
          colorTextSecondary: '#73718a',
          colorBorder: '#e7e8f2',
          colorBgBase: '#ffffff',
          colorBgLayout: '#f4f5fb',
          borderRadius: 8,
          fontFamily: 'Segoe UI, PingFang SC, Microsoft YaHei, sans-serif',
          fontSize: 13,
        },
        components: {
          Button: { controlHeight: 36, primaryColor: '#ffffff', defaultBg: '#ffffff', defaultBorderColor: '#e2e3ef' },
          Table: { headerBg: '#f7f7fc', headerColor: '#5b5872', cellPaddingBlockSM: 10, borderColor: '#ececf4', rowHoverBg: '#f5f3ff' },
          Layout: { bodyBg: '#f4f5fb', siderBg: '#ffffff', headerBg: '#ffffff' },
          Menu: { itemBg: '#ffffff', itemColor: '#66647b', itemHoverBg: '#f4f2ff', itemHoverColor: '#5148d8', itemSelectedBg: '#eeecff', itemSelectedColor: '#5b51e5', itemBorderRadius: 6 },
          Input: { activeBorderColor: '#665cf6', hoverBorderColor: '#8881f8' },
          Select: { activeBorderColor: '#665cf6', hoverBorderColor: '#8881f8' },
          DatePicker: { activeBorderColor: '#665cf6', hoverBorderColor: '#8881f8' },
        },
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)

