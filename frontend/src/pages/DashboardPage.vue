<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  App,
  Alert as AAlert,
  Button as AButton,
  Descriptions as ADescriptions,
  DescriptionsItem as ADescriptionsItem,
  Empty as AEmpty,
  InputSearch as AInputSearch,
  RangePicker as ARangePicker,
  Select as ASelect,
  Space as ASpace,
  Table as ATable,
  TypographyTitle as ATypographyTitle,
  TypographyText as ATypographyText,
} from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  DatabaseOutlined,
  MailOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import { dataApi } from '../api/client'
import type { AuditEvent, DashboardPayload, ShipmentLine, User } from '../types'
import { formatChinaDateTime } from '../utils/date'
import { includesSearch, shipmentBalances, shipmentLabels, withinRange } from '../utils/shipments'
import type { DateRange } from '../utils/shipments'
import StatusTag from '../components/StatusTag.vue'
import ShipmentEditModal from '../components/ShipmentEditModal.vue'

const props = defineProps<{ user: User }>()
const emit = defineEmits<{ navigate: [resource: string] }>()
const { message } = App.useApp()
const payload = ref<DashboardPayload | null>(null)
const selectedId = ref<number | null>(null)
const loading = ref(true)
const loadError = ref('')
const submitting = ref(false)
const editing = ref(false)
const statusFilter = ref('all')
const dealerFilter = ref('all')
const dateRange = ref<DateRange>(null)
const search = ref('')
let loadVersion = 0
onUnmounted(() => {
  loadVersion++
})
async function load() {
  const version = ++loadVersion
  loading.value = true
  loadError.value = ''
  try {
    const data = await dataApi.dashboard()
    if (version !== loadVersion) return
    payload.value = data
    if (!data.lines.some((line) => line.id === selectedId.value)) selectedId.value = data.lines[0]?.id ?? null
  } catch (error) {
    if (version === loadVersion) {
      loadError.value = error instanceof Error ? error.message : '工作台加载失败'
      message.error(loadError.value)
    }
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
onMounted(load)
const selected = computed(() => payload.value?.lines.find((line) => line.id === selectedId.value) ?? null)
const stats = computed(() => payload.value?.stats)
const balances = computed(() => shipmentBalances(selected.value))
const dealerOptions = computed(() =>
  [...new Set((payload.value?.lines ?? []).map((line) => line.dealer_name))]
    .sort()
    .map((name) => ({ value: name, label: name })),
)
const statusOptions = [
  { value: 'all', label: '全部状态' },
  ...Object.entries(shipmentLabels).map(([value, label]) => ({ value, label })),
]
const filteredLines = computed(() =>
  (payload.value?.lines ?? []).filter(
    (line) =>
      (statusFilter.value === 'all' || line.status === statusFilter.value) &&
      (dealerFilter.value === 'all' || line.dealer_name === dealerFilter.value) &&
      withinRange(line.received_at, dateRange.value) &&
      includesSearch(
        [line.request_no, line.order_no, line.part_no, line.material_no, line.product_name, line.dealer_name],
        search.value,
      ),
  ),
)
const columns: TableColumnsType<ShipmentLine> = [
  { title: '申请编号', dataIndex: 'request_no', width: 168, ellipsis: true },
  { title: '来源邮箱', dataIndex: 'sender_email', width: 150, ellipsis: true },
  { title: '客户', dataIndex: 'dealer_name', width: 130, ellipsis: true },
  { title: '申请日期', dataIndex: 'received_at', width: 132 },
  { title: '订单号', dataIndex: 'order_no', width: 100 },
  { title: '零件号', dataIndex: 'part_no', width: 92 },
  { title: '申请数量', dataIndex: 'quantity', width: 82, align: 'right' },
  { title: '匹配状态', dataIndex: 'status', width: 92 },
  { title: '操作', key: 'actions', width: 64, fixed: 'right' },
]
const auditColumns: TableColumnsType<AuditEvent> = [
  { title: '时间', dataIndex: 'created_at', width: 150 },
  { title: '操作人', dataIndex: 'actor_name', width: 100 },
  { title: '操作类型', dataIndex: 'action', width: 110 },
  { title: '对象编号', dataIndex: 'object_id', width: 170 },
  { title: '操作内容', dataIndex: 'detail', ellipsis: true },
  { title: '结果', dataIndex: 'result', width: 70 },
]
function rowClass(line: ShipmentLine) {
  return line.id === selectedId.value ? 'selected-row' : ''
}
function customRow(line: ShipmentLine) {
  return {
    onClick: () => {
      selectedId.value = line.id
    },
  }
}
async function confirm() {
  if (!selected.value || selected.value.status !== 'PENDING' || props.user.role === 'DEALER' || submitting.value) return
  submitting.value = true
  try {
    await dataApi.confirmLines([selected.value.id])
    message.success('核销成功，供应商发货邮件已进入发送队列')
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '核销失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="dashboard-page">
    <div class="dashboard-heading">
      <a-typography-title :level="4">工作台</a-typography-title
      ><a-typography-text type="secondary">发货申请、订单匹配与核销进度概览</a-typography-text>
    </div>
    <a-alert
      v-if="loadError"
      class="page-alert"
      type="error"
      show-icon
      message="工作台加载失败"
      :description="loadError"
      ><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert
    >
    <div class="dashboard-summary-row">
      <section class="stat-strip" aria-label="今日核销概览">
        <div class="stat-item">
          <MailOutlined class="stat-icon blue" />
          <div>
            <span>待处理邮件</span><strong>{{ stats?.pending_emails ?? 0 }}</strong
            ><small>等待销售确认</small>
          </div>
        </div>
        <div class="stat-item">
          <WarningOutlined class="stat-icon amber" />
          <div>
            <span>匹配异常</span><strong>{{ stats?.match_exceptions ?? 0 }}</strong
            ><small>需要人工修正</small>
          </div>
        </div>
        <div class="stat-item">
          <CheckCircleOutlined class="stat-icon green" />
          <div>
            <span>今日已核销</span><strong>{{ stats?.reconciled_today ?? 0 }}</strong
            ><small>条发货明细</small>
          </div>
        </div>
        <div class="stat-item">
          <DatabaseOutlined class="stat-icon blue" />
          <div>
            <span>待发库存（可用）</span><strong>{{ (stats?.remaining_stock ?? 0).toLocaleString() }}</strong
            ><small>{{ stats?.material_count ?? 0 }} 个物料</small>
          </div>
        </div>
      </section>
      <aside class="dashboard-welcome" aria-label="今日工作提示">
        <div class="dashboard-welcome-copy">
          <h2>早安，{{ user.display_name }}</h2>
          <p>当前有 {{ stats?.pending_emails ?? 0 }} 封邮件和 {{ stats?.match_exceptions ?? 0 }} 条匹配异常待处理。</p>
        </div>
        <img src="/images/dashboard-team.webp" alt="团队成员协作处理订单与发货" />
      </aside>
    </div>
    <section class="workspace-grid">
      <div class="workspace-list surface">
        <div class="section-heading">
          <a-typography-title :level="5">待核销发货申请</a-typography-title
          ><a-button :loading="loading" @click="load"
            ><template #icon><ReloadOutlined /></template>刷新</a-button
          >
        </div>
        <a-space class="filter-row" wrap>
          <a-select v-model:value="statusFilter" :options="statusOptions" aria-label="状态筛选" />
          <a-select
            v-model:value="dealerFilter"
            :options="[{ value: 'all', label: '全部客户' }, ...dealerOptions]"
            aria-label="客户筛选"
          />
          <a-range-picker :value="dateRange ?? undefined" @update:value="(value) => (dateRange = value as DateRange)" />
          <a-input-search v-model:value="search" placeholder="搜索申请号/订单号/零件号" allow-clear />
        </a-space>
        <a-table
          row-key="id"
          size="small"
          :loading="loading"
          :columns="columns"
          :data-source="filteredLines"
          :scroll="{ x: 1030, y: 390 }"
          :pagination="{ pageSize: 8, showSizeChanger: false, showTotal: (total: number) => `共 ${total} 条` }"
          :row-class-name="rowClass"
          :custom-row="customRow"
        >
          <template #bodyCell="{ column, text, record }">
            <template v-if="column.dataIndex === 'received_at'">{{ formatChinaDateTime(text).slice(0, 16) }}</template>
            <template v-else-if="column.dataIndex === 'part_no'">{{ text || '-' }}</template>
            <StatusTag v-else-if="column.dataIndex === 'status'" :status="record.status" />
            <a-button v-else-if="column.key === 'actions'" type="link" size="small" @click="selectedId = record.id"
              >查看</a-button
            >
          </template>
        </a-table>
      </div>
      <aside class="request-detail surface" aria-label="申请详情">
        <template v-if="selected">
          <div class="section-heading">
            <a-typography-title :level="5"
              >申请详情 <small>{{ selected.request_no }}</small></a-typography-title
            ><StatusTag :status="selected.status" />
          </div>
          <h3>邮件摘要</h3>
          <a-descriptions size="small" :column="1" :colon="false">
            <a-descriptions-item label="来源邮箱">{{ selected.sender_email }}</a-descriptions-item
            ><a-descriptions-item label="期望发货日">{{ selected.requested_ship_date }}</a-descriptions-item>
            <a-descriptions-item label="客户">{{ selected.dealer_name }}</a-descriptions-item
            ><a-descriptions-item label="收货地址">{{ selected.address }}</a-descriptions-item
            ><a-descriptions-item label="备注">{{ selected.remark || '无' }}</a-descriptions-item>
          </a-descriptions>
          <h3>申请明细 <small>（系统解析结果，可编辑）</small></h3>
          <div class="detail-line">
            <div>
              <span>零件号</span><strong>{{ selected.part_no || '待匹配' }}</strong>
            </div>
            <div class="grow">
              <span>品名</span><strong>{{ selected.product_name }}</strong>
            </div>
            <div>
              <span>申请数量</span><strong>{{ selected.quantity }}</strong>
            </div>
          </div>
          <h3>匹配结果 <small>（以订单台账为准）</small></h3>
          <a-descriptions bordered size="small" :column="{ xs: 1, sm: 2 }">
            <a-descriptions-item label="订单号">{{ selected.order_no }}</a-descriptions-item
            ><a-descriptions-item label="订单数量">{{ selected.ordered_qty ?? '-' }}</a-descriptions-item>
            <a-descriptions-item label="已核销量">{{ selected.reconciled_qty ?? '-' }}</a-descriptions-item
            ><a-descriptions-item label="核销前余额"
              ><span class="text-success">{{ balances.before ?? '-' }}</span></a-descriptions-item
            >
            <a-descriptions-item label="本次申请">{{ selected.quantity }}</a-descriptions-item
            ><a-descriptions-item label="核销后余额">{{ balances.after ?? '-' }}</a-descriptions-item>
          </a-descriptions>
          <div class="match-message" :class="selected.status === 'EXCEPTION' ? 'error' : 'success'">
            {{
              selected.status === 'EXCEPTION'
                ? selected.exception_reason
                : selected.status === 'RECONCILED'
                  ? '核销完成：供应商发货指令已进入发送队列。'
                  : selected.status === 'REVERSED'
                    ? '该明细已冲销，订单余额已恢复。'
                    : '匹配成功：申请数量未超过剩余未发数量，可核销。'
            }}
          </div>
          <div class="detail-actions">
            <a-button
              v-if="user.role !== 'DEALER'"
              type="primary"
              :disabled="selected.status !== 'PENDING'"
              :loading="submitting"
              @click="confirm"
              >确认核销</a-button
            ><a-button
              :disabled="!['PENDING', 'EXCEPTION'].includes(selected.status) || submitting"
              @click="editing = true"
              >修改申请</a-button
            >
          </div>
        </template>
        <a-empty v-else description="请选择一条发货申请" />
      </aside>
    </section>
    <section class="audit-panel surface">
      <div class="section-heading">
        <a-typography-title :level="5">最近操作记录</a-typography-title
        ><a-button type="link" @click="emit('navigate', 'audit')">查看更多</a-button>
      </div>
      <a-table
        row-key="id"
        size="small"
        :columns="auditColumns"
        :data-source="payload?.audit_events ?? []"
        :pagination="false"
        :scroll="{ x: 900 }"
      >
        <template #bodyCell="{ column, text }"
          ><template v-if="column.dataIndex === 'created_at'">{{ formatChinaDateTime(text) }}</template
          ><span v-else-if="column.dataIndex === 'result'" :class="text === '成功' ? 'text-success' : 'text-warning'">{{
            text
          }}</span></template
        >
      </a-table>
    </section>
    <ShipmentEditModal
      v-model:open="editing"
      :line="selected"
      :quantity-min="1"
      :quantity-precision="0"
      @saved="load"
    />
  </div>
</template>
