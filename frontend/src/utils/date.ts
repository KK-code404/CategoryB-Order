// CHANGE [2026-08-30 12:58 +08:00] [WH400]: 强制按上海时区呈现审计和邮件时间，避免服务器或浏览器时区导致日期错位。
export function formatChinaDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(new Date(value)).replaceAll('/', '-')
}

