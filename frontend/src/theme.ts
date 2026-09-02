import type { ThemeConfig } from 'ant-design-vue/es/config-provider/context'

export const theme: ThemeConfig = {
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
    controlHeight: 36,
  },
  components: {
    Menu: {
      colorItemBg: '#ffffff',
      colorItemText: '#66647b',
      colorItemBgHover: '#f4f2ff',
      colorItemTextHover: '#5148d8',
      colorItemBgSelected: '#eeecff',
      colorItemTextSelected: '#5b51e5',
      radiusItem: 6,
    },
    Input: { colorPrimary: '#665cf6', colorPrimaryHover: '#8881f8' },
    Select: { colorPrimary: '#665cf6' },
    DatePicker: { colorPrimary: '#665cf6' },
  },
}
