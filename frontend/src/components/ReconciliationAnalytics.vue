<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Alert as AAlert, Button as AButton, Empty as AEmpty, Skeleton as ASkeleton, App } from 'ant-design-vue'
import { FullscreenExitOutlined, FullscreenOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { dataApi } from '../api/client'
import { chartColors, dashboardRanges, formatQty as qty, groupOrders, summarize, sumQty } from '../utils/reconciliationAnalytics'
import type { AnalyticsReport } from '../utils/reconciliationAnalytics'
import { chinaDay } from '../utils/operations'
import AnalyticsDonut from './AnalyticsDonut.vue'

const emit = defineEmits<{ navigate: [key: string] }>()
const { message } = App.useApp()
const root = ref<HTMLElement>()
const report = ref<AnalyticsReport | null>(null)
const range = ref('batch')
const dealer = ref<number | 'all'>('all')
const unit = ref('桶')
const loading = ref(false)
const error = ref('')
const full = ref(false)
const selectedDay = ref('')
const ranges = ref(dashboardRanges(chinaDay()))
let version = 0

async function load() {
  const requestVersion = ++version
  ranges.value = dashboardRanges(chinaDay())
  const period = ranges.value.find(r => r.id === range.value)!
  report.value = null
  error.value = ''
  selectedDay.value = ''
  loading.value = true
  try {
    const result = await dataApi.reconciliationAnalytics(period.start, period.end)
    if (requestVersion === version) report.value = result
  } catch (cause) {
    if (requestVersion === version) error.value = cause instanceof Error ? cause.message : '看板数据暂时无法加载'
  } finally { if (requestVersion === version) loading.value = false }
}
function chooseRange(value: string) { range.value = value; void load() }
function fullscreenChanged() { full.value = document.fullscreenElement === root.value }
async function toggleFull() {
  try {
    if (document.fullscreenElement === root.value) await document.exitFullscreen()
    else if (root.value?.requestFullscreen) await root.value.requestFullscreen()
    else message.warning('当前浏览器不支持全屏，可使用 F11。')
  } catch { message.warning('浏览器未允许全屏，请使用 F11 或稍后重试。') }
}
onMounted(() => { void load(); document.addEventListener('fullscreenchange', fullscreenChanged) })
onUnmounted(() => { version++; document.removeEventListener('fullscreenchange', fullscreenChanged) })
const sourceRows = computed(() => report.value?.actual ?? [])
const dealers = computed(() => [...new Map(sourceRows.value.map(r => [r.dealer_id, { id: r.dealer_id, name: r.dealer_name }])).values()])
const units = computed(() => [...new Set(sourceRows.value.map(r => r.unit))])
watch(sourceRows, rows => {
  if (rows.length && !rows.some(r => r.unit === unit.value)) unit.value = rows[0]!.unit
  if (rows.length && dealer.value !== 'all' && !rows.some(r => r.dealer_id === dealer.value)) dealer.value = 'all'
})
const rows = computed(() => sourceRows.value.filter(r => (dealer.value === 'all' || r.dealer_id === dealer.value) && r.unit === unit.value))
const summary = computed(() => summarize(rows.value, report.value?.dates ?? []))
const orderGroups = computed(() => groupOrders(rows.value))
const dealerStats = computed(() => dealers.value.filter(d => dealer.value === 'all' || d.id === dealer.value).map(d => {
  const items = rows.value.filter(r => r.dealer_id === d.id)
  const stats = summarize(items, report.value?.dates ?? [])
  const ordered = sumQty(items, r => r.ordered_qty)
  return { ...d, ...stats, ordered, reconciled: Math.round((ordered - stats.closing) * 100) / 100,
    color: chartColors[dealers.value.findIndex(item => item.id === d.id) % chartColors.length]! }
}).filter(d => d.lines > 0))
const totalOrdered = computed(() => sumQty(rows.value, r => r.ordered_qty))
const totalReconciled = computed(() => Math.round((totalOrdered.value - summary.value.closing) * 100) / 100)
const statusSegments = computed(() => ['已核销完', '部分核销', '未核销', '待核查'].map((label, index) => ({
  label, value: orderGroups.value.filter(o => o.status === label).length,
  color: ['#208d8a', '#665cf6', '#b8bccd', '#c73a43'][index]!,
})).filter(s => s.value > 0))
const dealerSegments = computed(() => dealerStats.value.map(d => ({ label: d.name, value: d.quantity, color: d.color })))
const remainingRanks = computed(() => orderGroups.value.filter(o => o.remaining > 0).sort((a, b) => b.remaining - a.remaining).slice(0, 6))
const rankMax = computed(() => Math.max(1, ...remainingRanks.value.map(o => o.remaining)))
const dealerMax = computed(() => Math.max(1, ...dealerStats.value.map(d => d.ordered)))
const undated = computed(() => rows.value.filter(r => Number(r.undated_qty) !== 0).length)
const updated = computed(() => report.value ? new Date(report.value.generated_at).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '')
const selectedSummary = computed(() => summary.value.daily.find(d => d.date === selectedDay.value))
const dailyDetail = computed(() => dealerStats.value.map(d => d.name + ' ' + qty(d.daily.find(day => day.date === selectedDay.value)?.quantity ?? 0) + ' ' + unit.value).join('，'))

// Positive and negative movements are stacked separately around zero.
const dailyChart = computed(() => {
  const dates = report.value?.dates ?? []
  const groups = dates.map(date => ({ date, values: dealerStats.value.map(d => ({ label: d.name, color: d.color, value: d.daily.find(day => day.date === date)?.quantity ?? 0 })) }))
  const positive = Math.max(0, ...groups.map(g => g.values.reduce((s, d) => s + Math.max(d.value, 0), 0)))
  const negative = Math.min(0, ...groups.map(g => g.values.reduce((s, d) => s + Math.min(d.value, 0), 0)))
  const max = Math.max(1, positive), min = negative
  const y = (value: number) => 220 - (value - min) / (max - min) * 180
  const step = 610 / Math.max(1, dates.length)
  return { max, min, y, zero: y(0), groups: groups.map((g, i) => {
    let up = 0, down = 0
    return { date: g.date, x: 60 + step * (i + .5), label: i % Math.max(1, Math.ceil(dates.length / 8)) === 0 || i === dates.length - 1,
      total: g.values.reduce((s, d) => s + Math.round(d.value * 100), 0) / 100,
      bars: g.values.map(d => {
        const from = d.value >= 0 ? up : down, to = from + d.value
        if (d.value >= 0) up = to; else down = to
        return { ...d, y: Math.min(y(from), y(to)), height: Math.abs(y(to) - y(from)), width: Math.min(34, step * .58) }
      }) }
  }) }
})
const balanceChart = computed(() => {
  const values = [summary.value.opening, ...summary.value.daily.map(d => d.balance)]
  const max = Math.max(1, ...values), min = Math.min(0, ...values)
  const y = (value: number) => 208 - (value - min) / (max - min) * 160
  const x = (i: number) => 65 + i / Math.max(1, values.length - 1) * 600
  const points = values.map((v, i) => x(i) + ',' + y(v)).join(' ')
  return { max, min, y, x, values, points, area: '65,' + y(0) + ' ' + points + ' 665,' + y(0) }
})
</script>

<template>
  <section ref="root" class="reconciliation-board" aria-label="订单核销看板">
    <header class="board-heading"><div><h2>订单核销看板</h2><p>发货节奏、核销进度与剩余订单，一眼掌握。</p></div><div class="board-actions"><a-button :loading="loading" @click="load"><ReloadOutlined />刷新看板</a-button><a-button @click="toggleFull"><FullscreenExitOutlined v-if="full" /><FullscreenOutlined v-else />{{ full ? '退出全屏' : '全屏展示' }}</a-button></div></header>
    <nav class="board-filters" aria-label="看板范围">
      <div class="board-segments" role="group" aria-label="日期范围"><button v-for="item in ranges" :key="item.id" :aria-pressed="range === item.id" @click="chooseRange(item.id)">{{ item.label }}</button></div>
      <div class="board-dealers" role="group" aria-label="代理商范围"><button :aria-pressed="dealer === 'all'" @click="dealer = 'all'">全部代理商</button><button v-for="item in dealers" :key="item.id" :aria-pressed="dealer === item.id" @click="dealer = item.id">{{ item.name }}</button></div>
      <div v-if="units.length > 1" class="board-dealers" role="group" aria-label="计量单位"><button v-for="item in units" :key="item" :aria-pressed="unit === item" @click="unit = item">{{ item }}</button></div>
    </nav>
    <a-alert v-if="error" type="error" show-icon :message="error" description="旧结果已隐藏，请点击刷新看板重试。" />
    <div v-else-if="loading" class="board-loading" aria-label="正在加载核销看板"><a-skeleton active :paragraph="{ rows: 8 }" /></div>
    <template v-else-if="report">
      <div class="board-scope"><span>{{ report.start }} — {{ report.end }} · 正式核销台账 · 单位：{{ unit }}</span><span>{{ updated }} 更新（上海时间）</span></div>
      <a-empty v-if="!rows.length" description="当前范围没有订单，请切换代理商或先导入订单。" />
      <template v-else>
        <dl class="board-summary"><div><dt>覆盖订单</dt><dd>{{ summary.orders }}<small>单</small></dd><span>{{ summary.lines }} 条订单行</span></div><div><dt>区间净核销</dt><dd>{{ qty(summary.quantity) }}<small>{{ unit }}</small></dd><span>{{ summary.activeDays }} 天有发货变化</span></div><div><dt>期末剩余</dt><dd>{{ qty(summary.closing) }}<small>{{ unit }}</small></dd><span>期初 {{ qty(summary.opening) }} {{ unit }}</span></div><div><dt>累计已核销</dt><dd>{{ qty(totalReconciled) }}<small>{{ unit }}</small></dd><span>订单总量 {{ qty(totalOrdered) }} {{ unit }}</span></div></dl>
        <div class="board-chart-grid">
          <section class="board-panel board-wide" aria-label="每日发货柱状图"><header><div><h3>每日发货</h3><p>按代理商分色，按申请发货日归集净核销数量</p></div><div class="board-legend"><span v-for="item in dealerStats" :key="item.id"><i :style="{ backgroundColor: item.color }" />{{ item.name }}</span></div></header>
            <svg class="board-svg" viewBox="0 0 720 270" role="group" :aria-label="'每日发货柱状图，区间净核销 ' + qty(summary.quantity) + unit">
              <g v-for="tick in [dailyChart.max, (dailyChart.max + dailyChart.min) / 2, dailyChart.min]" :key="tick"><line x1="60" x2="670" :y1="dailyChart.y(tick)" :y2="dailyChart.y(tick)" class="board-gridline" /><text x="50" :y="dailyChart.y(tick) + 4" text-anchor="end">{{ qty(tick) }}</text></g><line x1="60" x2="670" :y1="dailyChart.zero" :y2="dailyChart.zero" class="board-axis" />
              <g v-for="day in dailyChart.groups" :key="day.date" tabindex="0" role="button" :aria-label="day.date + ' 净核销 ' + qty(day.total) + unit + '，查看当日数据'" @click="selectedDay = day.date" @focus="selectedDay = day.date" @pointerenter="selectedDay = day.date" @keydown.enter="selectedDay = day.date" @keydown.space.prevent="selectedDay = day.date"><rect :x="day.x - 16" y="32" width="32" height="197" fill="transparent" /><rect v-for="bar in day.bars" :key="bar.label" :x="day.x - bar.width / 2" :y="bar.y" :width="bar.width" :height="bar.height" :fill="bar.color" rx="2"><title>{{ day.date }} {{ bar.label }}：{{ qty(bar.value) }} {{ unit }}</title></rect><text v-if="day.label" :x="day.x" y="248" text-anchor="middle">{{ day.date.slice(5).replace('-', '/') }}</text><text v-if="dailyChart.groups.length <= 16 && day.total > 0" :x="day.x" :y="Math.min(...day.bars.map(b => b.y)) - 9" text-anchor="middle" class="board-value">{{ qty(day.total) }}</text></g>
            </svg>
            <p class="board-chart-detail" aria-live="polite">{{ selectedSummary ? selectedSummary.date + ' · ' + dailyDetail : summary.activeDays ? '点击或聚焦柱形，查看当日各代理商数量。' : '这段时间暂无已入账的数量变化。' }}</p>
          </section>
          <section class="board-panel" aria-label="订单核销状态环形图"><header><div><h3>订单核销状态</h3><p>按订单统计，不按发货明细重复计数</p></div></header><AnalyticsDonut title="订单核销状态" :segments="statusSegments" unit="单" /></section>
          <section class="board-panel board-wide" aria-label="订单余额趋势图"><header><div><h3>订单余额走势</h3><p>同一批订单的每日剩余数量</p></div><strong class="board-end-balance">{{ qty(summary.closing) }} <small>{{ unit }}</small></strong></header>
            <svg class="board-svg" viewBox="0 0 720 250" role="img" :aria-label="'余额从 ' + qty(summary.opening) + ' 变为 ' + qty(summary.closing) + unit"><g v-for="tick in [balanceChart.max, (balanceChart.max + balanceChart.min) / 2, balanceChart.min]" :key="tick"><line x1="65" x2="665" :y1="balanceChart.y(tick)" :y2="balanceChart.y(tick)" class="board-gridline" /><text x="55" :y="balanceChart.y(tick) + 4" text-anchor="end">{{ qty(tick) }}</text></g><polygon :points="balanceChart.area" fill="var(--brand-050)" /><polyline :points="balanceChart.points" fill="none" stroke="var(--brand-600)" stroke-width="3" /><g v-for="(value, i) in balanceChart.values" :key="i"><circle :cx="balanceChart.x(i)" :cy="balanceChart.y(value)" r="3" fill="var(--brand-600)"><title>{{ i === 0 ? '期初' : report.dates[i - 1] }}：{{ qty(value) }} {{ unit }}</title></circle></g><text x="65" y="238">期初 {{ qty(summary.opening) }}</text><text x="665" y="238" text-anchor="end">期末 {{ qty(summary.closing) }}</text></svg>
            <p class="board-chart-detail">{{ summary.quantity >= 0 ? '区间净减少' : '区间净恢复' }} {{ qty(Math.abs(summary.quantity)) }} {{ unit }} · 纵轴从零起算，不放大波动</p>
          </section>
          <section class="board-panel" aria-label="代理商发货占比环形图"><header><div><h3>代理商发货占比</h3><p>区间净核销数量的构成</p></div></header><AnalyticsDonut title="代理商发货占比" :segments="dealerSegments" :unit="unit" empty="当前区间暂无净核销数量" /></section>
        </div>
        <div class="board-bottom-grid">
          <section class="board-panel" aria-label="订单余额排名柱状图"><header><div><h3>订单余额排名</h3><p>剩余量最多的 6 单 · 当前单位视角</p></div><a-button type="link" @click="emit('navigate', 'orders')">查看订单台账</a-button></header><a-empty v-if="!remainingRanks.length" description="当前订单已无正向剩余量" /><ol v-else class="board-rank"><li v-for="item in remainingRanks" :key="item.key"><div class="board-rank-label"><span><strong>{{ item.order }}</strong><small>{{ item.dealer }}</small></span><b>{{ qty(item.remaining) }} <small>{{ unit }}</small></b></div><div class="board-rank-track" role="img" :aria-label="item.dealer + '订单' + item.order + '剩余' + qty(item.remaining) + unit"><span :style="{ width: item.remaining / rankMax * 100 + '%' }" /></div></li></ol></section>
          <section class="board-panel" aria-label="代理商核销结构堆叠柱状图"><header><div><h3>代理商核销结构</h3><p>对比已核销和剩余数量，柱长按同一尺度绘制</p></div></header><div class="board-legend"><span><i class="reconciled-color" />累计已核销</span><span><i class="remaining-color" />期末剩余</span></div><div class="board-dealer-bars"><div v-for="item in dealerStats" :key="item.id"><div class="board-rank-label"><strong>{{ item.name }}</strong><span>{{ item.orders }} 单</span></div><p v-if="item.reconciled < 0 || item.closing < 0">余额异常，请在订单台账核查。</p><template v-else><div class="board-stacked" role="img" :aria-label="item.name + '已核销' + qty(item.reconciled) + unit + '，剩余' + qty(item.closing) + unit"><i class="reconciled-color" :style="{ width: item.reconciled / dealerMax * 100 + '%' }" /><i class="remaining-color" :style="{ width: item.closing / dealerMax * 100 + '%' }" /></div><div class="board-stack-labels"><span>已核销 {{ qty(item.reconciled) }}</span><span>剩余 {{ qty(item.closing) }} {{ unit }}</span></div></template></div></div><a-button type="link" @click="emit('navigate', 'shipments')">查看发货明细</a-button></section>
        </div>
        <footer class="board-footnote"><p>核销不等于物流实发或签收。余额按现有订单池回溯，冲销抵减原申请日，不还原订单历次新增、修改。</p><p v-if="report.simulation.imported">8.27—9.3 批次已按用户确认纳入正式核销，来源与批准记录保留在操作日志中，不再重复展示模拟量。</p><p v-if="undated">{{ undated }} 条订单行含未分日历史数量，已保留在余额中。</p></footer>
      </template>
    </template>
  </section>
</template>

<style scoped>
.reconciliation-board { color: var(--text); font-variant-numeric: tabular-nums; }
.reconciliation-board:fullscreen { padding: 28px; background: var(--canvas); overflow: auto; }
.board-heading, .board-actions, .board-scope, .board-panel > header, .board-rank-label, .board-stack-labels { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.board-heading { margin: 8px 0 20px; }
h2 { font-size: 21px; font-weight: 650; margin: 0 0 6px; } h3 { font-size: 15px; font-weight: 650; margin: 0 0 6px; }
p { color: var(--text-secondary); line-height: 1.65; margin: 0; }
.board-actions { gap: 8px; flex-wrap: wrap; }
.board-filters { display: flex; flex-wrap: wrap; gap: 12px 24px; margin-bottom: 16px; }
.board-segments, .board-dealers { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }
.board-segments { background: var(--surface); border-radius: 8px; padding: 3px; }
.board-filters button { border: 0; background: transparent; color: var(--text-secondary); padding: 10px 14px; min-height: 40px; font: inherit; cursor: pointer; border-radius: 6px; }
.board-filters button:hover { background: var(--brand-050); color: var(--brand-800); }
.board-segments button[aria-pressed='true'] { background: var(--brand-600); color: white; }
.board-dealers button[aria-pressed='true'] { background: var(--brand-050); color: var(--brand-800); font-weight: 600; }
button:focus-visible, svg [tabindex]:focus-visible { outline: 2px solid var(--brand-800); outline-offset: 3px; }
.board-scope { color: var(--text-secondary); font-size: 12px; line-height: 1.6; margin-bottom: 16px; flex-wrap: wrap; gap: 6px; }
.board-loading { padding: 24px; background: var(--surface); }
.board-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); padding: 22px 0; border-radius: 10px; background: var(--surface); margin: 0 0 20px; }
.board-summary > div { padding: 0 24px; border-right: 1px solid var(--border); }
.board-summary > div:last-child { border-right: 0; }
.board-summary dt, .board-summary span { color: var(--text-secondary); font-size: 12px; }
.board-summary dd { font-size: 29px; font-weight: 650; line-height: 1.25; margin: 8px 0; overflow-wrap: anywhere; }
.board-summary small { color: var(--text-secondary); font-size: 12px; font-weight: 400; margin-left: 6px; }
.board-chart-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; margin-bottom: 20px; }
.board-wide { grid-column: span 2; }
.board-panel { background: var(--surface); border-radius: 10px; padding: 22px; min-width: 0; }
.board-panel > header { align-items: flex-start; flex-wrap: wrap; margin-bottom: 16px; }
.board-panel header p, .board-chart-detail, .board-footnote { font-size: 12px; }
.board-legend { display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--text-secondary); }
.board-legend span { display: inline-flex; align-items: center; gap: 7px; }
.board-legend i { width: 9px; height: 9px; border-radius: 2px; }
.board-svg { display: block; width: 100%; min-height: 180px; }
.board-svg text { font: 12px 'Segoe UI', 'Microsoft YaHei', sans-serif; fill: var(--text-secondary); }
.board-svg .board-value { fill: var(--text); font-weight: 600; }
.board-svg g[role='button'] { cursor: pointer; }
.board-gridline { stroke: var(--border); stroke-dasharray: 4 5; }
.board-axis { stroke: var(--border); }
.board-chart-detail { min-height: 20px; margin-top: 10px; }
.board-end-balance { color: var(--brand-800); font-size: 22px; font-weight: 650; }
.board-end-balance small { font-size: 12px; font-weight: 400; }
.board-bottom-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 20px; }
.board-rank { list-style: none; margin: 0; padding: 0; display: grid; gap: 18px; }
.board-rank-label { font-size: 13px; margin-bottom: 8px; flex-wrap: wrap; gap: 4px 12px; }
.board-rank-label strong, .board-rank-label b { font-weight: 550; }
.board-rank-label small { color: var(--text-secondary); font-weight: 400; font-size: 12px; margin-left: 10px; }
.board-rank-track { height: 10px; border-radius: 3px; background: var(--surface-subtle); }
.board-rank-track span { display: block; height: 100%; background: var(--brand-600); border-radius: 3px; }
.board-dealer-bars { display: grid; gap: 32px; margin: 32px 0; }
.board-stacked { display: flex; height: 28px; border-radius: 4px; overflow: hidden; }
.board-stacked i { display: block; height: 100%; }
.reconciled-color { background: var(--brand-600); }
.remaining-color { background: #bec3dd; }
.board-stack-labels { margin-top: 10px; font-size: 12px; color: var(--text-secondary); flex-wrap: wrap; gap: 6px; }
.board-footnote { margin-top: 18px; line-height: 1.8; }
.board-footnote p + p { margin-top: 4px; }
::selection { background: var(--brand-050); color: var(--brand-900); }
@media (min-width: 1800px) { .reconciliation-board:fullscreen { padding: 32px 48px; } .board-svg { max-height: 330px; } }
@media (max-width: 1100px) { .board-chart-grid { grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); } .board-wide { grid-column: auto; } .board-bottom-grid { grid-template-columns: 1fr; } .board-summary > div { padding: 0 16px; } }
@media (max-width: 760px) { .board-chart-grid { grid-template-columns: 1fr; } .board-heading { align-items: flex-start; flex-direction: column; } .board-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 24px; } .board-summary > div:nth-child(2) { border-right: 0; } .board-summary dd { font-size: 25px; } .board-panel { padding: 18px; } .board-svg { min-height: 130px; } .board-filters { gap: 10px; } .board-filters button { padding: 10px 12px; } .reconciliation-board:fullscreen { padding: 16px; } }
</style>
