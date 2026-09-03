<script setup lang="ts">
// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 在现有订单台账提供只读 Excel 式日历，支持月份、客户、订单切换且不改变核销数据。
import { computed, onUnmounted, ref, watch } from 'vue'
import { Alert as AAlert, Button as AButton, Empty as AEmpty, InputSearch as AInputSearch, MonthPicker as AMonthPicker, Select as ASelect, Spin as ASpin, Switch as ASwitch } from 'ant-design-vue'
import { LeftOutlined, ReloadOutlined, RightOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import type { DailyShipmentReport, DailyShipmentRow } from '../types'
import { dataApi } from '../api/client'

const month = ref(new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' }).slice(0, 7))
const report = ref<DailyShipmentReport | null>(null)
const loading = ref(false)
const error = ref('')
const search = ref('')
const dealer = ref<number | 'all'>('all')
const selectedOrder = ref('all')
const activeDatesOnly = ref(false)
let loadVersion = 0
onUnmounted(() => { loadVersion++ })

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 防止快速切月的旧响应覆盖新月份；失败时清除旧表格并提供重试。
async function load() {
  const version = ++loadVersion
  loading.value = true
  error.value = ''
  report.value = null
  try {
    const result = await dataApi.dailyShipments(month.value)
    if (version === loadVersion) report.value = result
  } catch (cause) {
    if (version === loadVersion) error.value = cause instanceof Error ? cause.message : '每日发货明细加载失败'
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
watch(month, load, { immediate: true })
watch([search, dealer], () => { selectedOrder.value = 'all' })

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 用代理商 ID 加订单号区分工作表，同号不同客户不会合并。
const orderKey = (row: DailyShipmentRow) => `${row.dealer_id}:${row.order_no}`
const dealers = computed(() => [...new Map((report.value?.rows ?? []).map(row => [row.dealer_id, { value: row.dealer_id, label: `${row.dealer_code} · ${row.dealer_name}` }])).values()])
const filteredRows = computed(() => (report.value?.rows ?? []).filter(row => {
  const needle = search.value.trim().toLowerCase()
  return (dealer.value === 'all' || row.dealer_id === dealer.value) &&
    `${row.order_no} ${row.part_no} ${row.material_no} ${row.product_name} ${row.dealer_code} ${row.dealer_name}`.toLowerCase().includes(needle)
}))
const orders = computed(() => [...new Map(filteredRows.value.map(row => [orderKey(row), { key: orderKey(row), label: `${row.order_no} · ${row.dealer_code}` }])).values()])
const rows = computed(() => filteredRows.value.filter(row => selectedOrder.value === 'all' || orderKey(row) === selectedOrder.value))
const dates = computed(() => (report.value?.dates ?? []).filter(date => !activeDatesOnly.value || rows.value.some(row => Number(row.daily[date] ?? 0) !== 0)))
const hasUndated = computed(() => rows.value.some(row => Number(row.undated_qty) !== 0))

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 数量以百分之一单位累加，且不同计量单位分别合计，避免字符串拼接及跨单位相加。
const sum = (items: DailyShipmentRow[], value: (row: DailyShipmentRow) => number | string) => items.reduce((total, row) => total + Math.round(Number(value(row)) * 100), 0) / 100
const totals = computed(() => [...new Set(rows.value.map(row => row.unit))].map(unit => {
  const items = rows.value.filter(row => row.unit === unit)
  return {
    unit, ordered: sum(items, r => r.ordered_qty), remaining: sum(items, r => r.remaining_qty),
    reconciled: sum(items, r => r.reconciled_qty), undated: sum(items, r => r.undated_qty), month: sum(items, r => r.month_qty),
    daily: Object.fromEntries(dates.value.map(date => [date, sum(items, r => r.daily[date] ?? 0)])),
  }
}))
const quantity = (value: number | string) => Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
const dailyQuantity = (value?: number | string) => Number(value ?? 0) === 0 ? '—' : quantity(value!)

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 月份选择与前后月按钮使用同一受限状态，保留服务端支持的日期范围。
function selectMonth(value: Dayjs | string | null) {
  const selected = typeof value === 'string' ? dayjs(value) : value
  if (selected?.isValid() && selected.year() >= 1900 && selected.year() <= 2100) month.value = selected.format('YYYY-MM')
}
function shiftMonth(amount: number) { selectMonth(dayjs(`${month.value}-01`).add(amount, 'month')) }
</script>

<template>
  <section class="surface daily-ledger" aria-label="每日发货明细">
    <div class="daily-ledger-heading">
      <div><h3>每日发货明细</h3><p>按订单、零件逐日查看通知发货数量</p></div>
      <a-button :loading="loading" @click="load"><template #icon><ReloadOutlined /></template>刷新明细</a-button>
    </div>
    <div class="daily-ledger-filters">
      <div class="daily-month-controls">
        <a-button aria-label="上个月" :disabled="month === '1900-01'" @click="shiftMonth(-1)"><LeftOutlined /></a-button>
        <a-month-picker :value="dayjs(`${month}-01`)" :allow-clear="false" format="YYYY年MM月" aria-label="发货月份" :disabled-date="date => date.year() < 1900 || date.year() > 2100" @change="selectMonth" />
        <a-button aria-label="下个月" :disabled="month === '2100-12'" @click="shiftMonth(1)"><RightOutlined /></a-button>
      </div>
      <a-select v-model:value="dealer" aria-label="每日明细代理商" :options="[{ value: 'all', label: '全部代理商' }, ...dealers]" />
      <a-input-search v-model:value="search" placeholder="搜索订单号、零件或客户" allow-clear />
      <label class="daily-date-toggle"><a-switch v-model:checked="activeDatesOnly" aria-label="只看有发货的日期" />只看有发货日期</label>
    </div>
    <p class="daily-ledger-basis">统计口径：已核销申请的要求发货日期；同日多批次合计，冲销抵减原日期。不是物流实发或签收数量，邮件发送状态请到收件箱核对。</p>
    <a-alert v-if="hasUndated && !error" class="daily-ledger-warning" type="warning" show-icon message="历史未分日数量没有对应日期流水，不计入本月日期列。剩余量与累计核销量均为全期数据，不随月份切换。" />
    <a-alert v-if="error" type="error" show-icon :message="error"><template #action><a-button @click="load">重试</a-button></template></a-alert>
    <a-spin :spinning="loading">
      <template v-if="report && !error">
        <div class="daily-ledger-caption"><strong>{{ report.month }} · 通知发货台账</strong><span>{{ orders.length }} 个订单 / 当前 {{ rows.length }} 行 · 横向滚动查看日期，合计在最右侧</span></div>
        <div v-if="rows.length" class="daily-grid-scroll" role="region" aria-label="每日通知发货数量表，可横向滚动" tabindex="0">
          <table class="daily-grid">
            <caption class="daily-visually-hidden">{{ report.month }} 每日通知发货明细；横列为日期，纵列为订单零件。</caption>
            <thead><tr>
              <th scope="col" class="daily-fixed-order">订单号 / 客户</th>
              <th scope="col" class="daily-fixed-part">零件号</th>
              <th scope="col" class="daily-fixed-ordered">订单数量</th>
              <th scope="col" class="daily-fixed-remaining">剩余未发数量</th>
              <th v-for="date in dates" :key="date" scope="col" class="daily-date-header" :title="date"><span>通知发货</span><strong>{{ date.slice(5) }}</strong></th>
              <th scope="col" class="daily-month-total">本月合计</th><th scope="col">历史未分日</th><th scope="col">累计核销量</th><th scope="col">单位</th>
            </tr></thead>
            <tbody><tr v-for="row in rows" :key="row.id" :data-order-line="row.id">
              <th scope="row" class="daily-fixed-order"><strong>{{ row.order_no }}</strong><small :title="row.dealer_name">{{ row.dealer_code }} · {{ row.dealer_name }}</small></th>
              <td class="daily-fixed-part" :title="`${row.material_no} · ${row.product_name}`">{{ row.part_no }}</td>
              <td class="daily-fixed-ordered">{{ quantity(row.ordered_qty) }}</td>
              <td class="daily-fixed-remaining">{{ quantity(row.remaining_qty) }}</td>
              <td v-for="date in dates" :key="date" :class="{ 'daily-has-quantity': Number(row.daily[date] ?? 0) !== 0 }" :data-date="date" :title="`${row.order_no} / ${row.part_no} / ${date}：${quantity(row.daily[date] ?? 0)} ${row.unit}`">{{ dailyQuantity(row.daily[date]) }}</td>
              <td class="daily-month-total">{{ quantity(row.month_qty) }}</td><td :class="{ 'daily-undated': Number(row.undated_qty) !== 0 }">{{ dailyQuantity(row.undated_qty) }}</td><td>{{ quantity(row.reconciled_qty) }}</td><td>{{ row.unit }}</td>
            </tr></tbody>
            <tfoot><tr v-for="total in totals" :key="total.unit">
              <th class="daily-fixed-order">合计（{{ total.unit }}）</th><td class="daily-fixed-part">—</td><td class="daily-fixed-ordered">{{ quantity(total.ordered) }}</td><td class="daily-fixed-remaining">{{ quantity(total.remaining) }}</td>
              <td v-for="date in dates" :key="date">{{ dailyQuantity(total.daily[date]) }}</td>
              <td class="daily-month-total">{{ quantity(total.month) }}</td><td>{{ dailyQuantity(total.undated) }}</td><td>{{ quantity(total.reconciled) }}</td><td>{{ total.unit }}</td>
            </tr></tfoot>
          </table>
        </div>
        <a-empty v-else description="没有符合条件的订单，试试其他搜索条件或先导入订单" />
        <p v-if="rows.length && activeDatesOnly && !dates.length" class="daily-ledger-basis">本月没有可显示的通知发货日期；关闭“只看有发货日期”可查看完整日历。</p>
        <div class="daily-order-tabs" role="tablist" aria-label="按订单切换工作表">
          <button type="button" role="tab" :aria-selected="selectedOrder === 'all'" @click="selectedOrder = 'all'">全部订单</button>
          <button v-for="order in orders" :key="order.key" type="button" role="tab" :aria-selected="selectedOrder === order.key" @click="selectedOrder = order.key">{{ order.label }}</button>
        </div>
      </template>
      <div v-else-if="loading" class="daily-loading-placeholder">正在读取每日核销流水…</div>
    </a-spin>
  </section>
</template>
