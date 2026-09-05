<script setup lang="ts">
// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 复用授权只读接口构建风险雷达、发货沙盘和业务简报，不触发核销或外部发送。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Alert as AAlert, Button as AButton, Spin as ASpin, App } from 'ant-design-vue'
import { dataApi } from '../api/client'
import type { DailyShipmentRow, OutboundMail, ShipmentLine, User } from '../types'
import { buildRisks, chinaDay, simulate } from '../utils/operations'
import ReconciliationAnalytics from '../components/ReconciliationAnalytics.vue'

const props = defineProps<{ user: User }>()
const emit = defineEmits<{ navigate: [key: string] }>()
const { message } = App.useApp()
const tab = ref('radar')
const filter = ref('全部')
const loading = ref(false)
const error = ref('')
const lines = ref<ShipmentLine[]>([])
const mails = ref<OutboundMail[]>([])
const orders = ref<DailyShipmentRow[]>([])
const loadedAt = ref('')
const today = ref('')
const drafts = ref<Record<number, string>>({})
const search = ref('')
let version = 0
onUnmounted(() => { version++ })
// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 按角色并行读取快照，刷新清空推演并抑制卸载后的迟到响应。
async function load() {
  const current = ++version
  loading.value = true
  error.value = ''
  drafts.value = {}
  try {
    const day = chinaDay()
    const [shipmentRows, report, outbound] = await Promise.all([
      dataApi.shipmentLines(), dataApi.dailyShipments(day.slice(0, 7)),
      props.user.role === 'DEALER' ? Promise.resolve([]) : dataApi.outboundMails(),
    ])
    if (current !== version) return
    lines.value = shipmentRows
    orders.value = report.rows
    mails.value = outbound
    today.value = day
    loadedAt.value = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
  } catch (cause) {
    if (current === version) error.value = cause instanceof Error ? cause.message : '数据加载失败'
  } finally { if (current === version) loading.value = false }
}
onMounted(load)
const risks = computed(() => buildRisks(lines.value, mails.value, today.value))
const visibleRisks = computed(() => risks.value.filter(item => filter.value === '全部' || item.category === filter.value))
const pending = computed(() => lines.value.filter(line => ['PENDING', 'EXCEPTION'].includes(line.status)))
const candidates = computed(() => orders.value.filter(row => `${row.order_no} ${row.part_no} ${row.dealer_name}`.toLowerCase().includes(search.value.toLowerCase())))
const basket = computed(() => orders.value.filter(row => (drafts.value[row.id] ?? '') !== '').map(row => ({ row, result: simulate(row, drafts.value[row.id]) })))
const blocked = computed(() => basket.value.filter(item => !item.result.valid || Number(item.result.shortage) > 0))
const brief = computed(() => [
  `油品业务简报｜${today.value}（上海时间）`,
  `数据快照：${loadedAt.value}；仅当前账号可见范围。`,
  `待处理申请行：${pending.value.length}；匹配异常：${lines.value.filter(line => line.status === 'EXCEPTION').length}。`,
  `逾期待处理：${risks.value.filter(item => item.category === '逾期待处理').length} 行（要求发货日早于今天且未核销）。`,
  props.user.role === 'DEALER' ? '供应商邮件：代理商视角不提供。' : `最近 500 封供应商邮件中失败 ${mails.value.filter(mail => mail.status === 'FAILED').length} 封、待发送 ${mails.value.filter(mail => mail.status === 'PENDING').length} 封。`,
  `可见订单行 ${orders.value.length}；存在历史未分日数量的订单行 ${orders.value.filter(row => Number(row.undated_qty) !== 0).length}。`,
  '建议顺序：先核实逾期需求及失败发信，再处理匹配异常，确认前复核实时余额。',
  '口径：规则生成，非 AI 预测；核销不代表物流实发/签收。风险项可重叠，不可相加当作申请数。',
].join('\n'))
// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 只由明确点击复制无个人收货信息的摘要，浏览器拒绝时允许手动复制。
async function copyBrief() {
  try { await navigator.clipboard.writeText(brief.value); message.success('简报已复制') }
  catch { message.warning('剪贴板不可用，请选择下方简报文字手动复制') }
}
</script>

<template>
  <div class="operations-page">
    <!-- CHANGE [2026-09-03 14:48 +08:00] [WH400]: 将去水印协同图放在驾驶舱标题旁，不覆盖风险与沙盘数据。 -->
    <header class="operations-heading operations-illustrated">
      <div><span class="operations-eyebrow">OPERATIONS LAB · 规则辅助</span><h1>业务驾驶舱</h1><p>从被动核对，走向主动发现。先看风险，再做推演，最后形成行动摘要。</p></div>
      <!-- CHANGE [2026-09-03 15:20 +08:00] [WH400]: 驾驶舱换用指定新品宣导插画，保留原有布局及只读功能。 -->
      <img class="operations-platform-art" src="/images/operations-introduction.svg" alt="业务信息展示与协作插画" width="144" height="144" decoding="async" />
      <a-button :loading="loading" @click="load">刷新数据并重置沙盘</a-button>
    </header>
    <nav class="order-view-tabs" aria-label="驾驶舱模块">
      <button v-for="item in [{ id: 'analytics', label: '核销看板' }, { id: 'radar', label: '风险雷达' }, { id: 'sandbox', label: '发货沙盘' }, { id: 'brief', label: '业务简报' }]" :key="item.id" :class="{ active: tab === item.id }" :aria-pressed="tab === item.id" @click="tab = item.id">{{ item.label }}</button>
    </nav>
    <ReconciliationAnalytics v-if="tab === 'analytics'" @navigate="key => emit('navigate', key)" />
    <a-alert v-else-if="error" type="error" show-icon :message="error" description="本次加载失败，旧快照已隐藏。请刷新重试。" />
    <a-spin v-else-if="loading" aria-label="加载驾驶舱" />
    <template v-else-if="loadedAt">
      <p class="operations-snapshot">上海时间 {{ loadedAt }} · 只读快照，刷新会清空沙盘输入 · {{ user.role === 'DEALER' ? '仅本人代理商数据，不含供应商邮件' : '授权业务数据；供应商邮件仅最近 500 封' }}</p>
      <section v-if="tab === 'radar'" aria-label="风险雷达">
        <div class="operations-metrics">
          <button v-for="category in ['逾期待处理', '匹配异常', '邮件失败']" :key="category" :disabled="category === '邮件失败' && user.role === 'DEALER'" :aria-pressed="filter === category" @click="filter = category"><span>{{ category }}</span><strong>{{ category === '邮件失败' && user.role === 'DEALER' ? '—' : risks.filter(item => item.category === category).length }}</strong><small>{{ category === '邮件失败' ? '供应商通知链路' : '申请明细行' }}</small></button>
        </div>
        <div class="operations-panel">
          <div class="operations-panel-title"><h2>优先处理清单</h2><a-button @click="filter = '全部'">显示全部风险</a-button></div>
          <p>当前：{{ filter }} · {{ visibleRisks.length }} 项。异常与逾期可能指向同一申请；逾期不代表物流延误。</p>
          <div v-for="item in visibleRisks" :key="item.id" class="operations-risk"><span class="operations-risk-label">{{ item.category }}</span><div><strong>{{ item.title }}</strong><p>{{ item.reason }}</p></div><a-button @click="emit('navigate', item.destination)">打开{{ item.destination === 'inbox' ? '邮件收件箱' : '发货申请' }}</a-button></div>
          <p v-if="!visibleRisks.length" class="operations-empty">当前范围未命中该规则。请同时关注尚未进入平台的需求。</p>
        </div>
      </section>
      <section v-else-if="tab === 'sandbox'" class="operations-panel" aria-label="发货沙盘">
        <div class="operations-panel-title"><h2>如果现在安排这批货？</h2><a-button @click="drafts = {}">清空模拟</a-button></div>
        <p>按订单行输入拟发数量，立即预览余额。每行仅一笔模拟，互不合并单位；不占用库存、不发邮件，不计入其他待处理申请。</p>
        <label class="operations-search">查找订单 / 零件 / 客户<input v-model="search" placeholder="输入订单、零件或客户" /></label>
        <div class="operations-table-wrap"><table class="operations-table"><thead><tr><th>客户 / 订单</th><th>零件</th><th>当前剩余</th><th>拟发数量</th><th>模拟后剩余</th><th>判断</th></tr></thead><tbody>
          <tr v-for="row in candidates" :key="row.id"><td>{{ row.dealer_name }}<br /><strong>{{ row.order_no }}</strong></td><td>{{ row.part_no }}</td><td>{{ row.remaining_qty }} {{ row.unit }}</td><td><input v-model="drafts[row.id]" :aria-label="`订单行 ${row.id} 拟发数量`" inputmode="decimal" placeholder="不模拟" /></td><td>{{ drafts[row.id] ? simulate(row, drafts[row.id]).after ?? '—' : '—' }} {{ row.unit }}</td><td><span v-if="drafts[row.id]" :class="simulate(row, drafts[row.id]).valid && !simulate(row, drafts[row.id]).shortage ? 'operations-ok' : 'operations-warning'">{{ !simulate(row, drafts[row.id]).valid ? '请输入正数，最多两位小数' : simulate(row, drafts[row.id]).shortage ? `缺口 ${simulate(row, drafts[row.id]).shortage} ${row.unit}` : '快照余额充足' }}</span><span v-else>未模拟</span></td></tr>
        </tbody></table></div>
        <p v-if="!candidates.length" class="operations-empty">没有匹配的订单行。</p>
        <a-alert :type="blocked.length ? 'warning' : 'info'" :message="`全沙盘 ${basket.length} 行（含搜索隐藏行），${blocked.length} 行需要调整`" description="本结果不是核销许可。实际确认仍需后台校验、事务锁定及最新余额检查。" show-icon />
      </section>
      <section v-else class="operations-panel" aria-label="业务简报">
        <div class="operations-panel-title"><h2>一分钟业务简报</h2><a-button @click="copyBrief">复制简报</a-button></div>
        <p>自动整理当前快照的统计口径与行动顺序。仅含汇总，不含收货姓名、电话或地址；复制后请按公司规定分享。</p>
        <pre class="operations-brief">{{ brief }}</pre>
      </section>
    </template>
  </div>
</template>
