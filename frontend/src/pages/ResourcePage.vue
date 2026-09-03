<script setup lang="ts">
// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 每日明细按需加载，保持现有订单列表和业务弹窗不变。
import { computed, defineAsyncComponent, onUnmounted, reactive, ref, watch } from 'vue'
import {
  App,
  Alert as AAlert,
  Button as AButton,
  Empty as AEmpty,
  Form as AForm,
  FormItem as AFormItem,
  InputSearch as AInputSearch,
  Modal as AModal,
  RangePicker as ARangePicker,
  Select as ASelect,
  Space as ASpace,
  Table as ATable,
  Tabs as ATabs,
  TabPane as ATabPane,
  Tag as ATag,
  Textarea as ATextarea,
  TypographyTitle as ATypographyTitle,
  TypographyText as ATypographyText,
} from 'ant-design-vue'
import type { FormInstance, TableColumnsType } from 'ant-design-vue'
import {
  CheckOutlined,
  EditOutlined,
  EyeOutlined,
  ReloadOutlined,
  RetweetOutlined,
  SendOutlined,
} from '@ant-design/icons-vue'
import { dataApi } from '../api/client'
import type { AuditEvent, OrderLine, OutboundMail, ShipmentLine, ShipmentRequest, User } from '../types'
import { formatChinaDateTime } from '../utils/date'
import {
  includesSearch,
  mailColors,
  mailLabels,
  shipmentLabels,
  shipmentRequestStatus,
  withinRange,
} from '../utils/shipments'
import type { DateRange } from '../utils/shipments'
import StatusTag from '../components/StatusTag.vue'
import ShipmentEditModal from '../components/ShipmentEditModal.vue'
import ShipmentDetailModal from '../components/ShipmentDetailModal.vue'

// CHANGE [2026-09-03 09:01 +08:00] [WH400]: 在订单台账内增加独立日历视图，默认仍展示原有汇总列表。
const OrderDailyShipments = defineAsyncComponent(() => import('../components/OrderDailyShipments.vue'))
const ordersView = ref('summary')

const props = defineProps<{ resource: string; user: User }>()
const { message } = App.useApp()
type ResourceRow = OrderLine | ShipmentLine | AuditEvent
const titles: Record<string, string> = {
  orders: '订单台账',
  shipments: '发货申请',
  inbox: '邮件收件箱',
  audit: '操作日志',
}
const rows = ref<ResourceRow[]>([])
const requests = ref<ShipmentRequest[]>([])
const mails = ref<OutboundMail[]>([])
const loading = ref(false)
const loadError = ref('')
const search = ref('')
const statusFilter = ref('all')
const dealerFilter = ref('all')
const dateRange = ref<DateRange>(null)
const inboxTab = ref('incoming')
const selectedLine = ref<ShipmentLine | null>(null)
const detailOpen = ref(false)
const editing = ref(false)
const reversing = ref(false)
const submitting = ref(false)
const reverseForm = reactive({ reason: '' })
const reverseFormRef = ref<FormInstance>()
let loadVersion = 0
onUnmounted(() => {
  loadVersion++
})
async function load() {
  const version = ++loadVersion
  const resource = props.resource
  loading.value = true
  loadError.value = ''
  try {
    if (resource === 'inbox') {
      const [incoming, outgoing] = await Promise.all([
        dataApi.shipmentRequests(),
        props.user.role === 'DEALER' ? Promise.resolve([]) : dataApi.outboundMails(),
      ])
      if (version !== loadVersion) return
      requests.value = incoming
      mails.value = outgoing
      rows.value = []
    } else {
      const data =
        resource === 'orders'
          ? await dataApi.orders()
          : resource === 'audit'
            ? await dataApi.auditEvents()
            : await dataApi.shipmentLines()
      if (version === loadVersion) rows.value = data
    }
  } catch (error) {
    if (version === loadVersion) {
      loadError.value = error instanceof Error ? error.message : '数据加载失败'
      message.error(loadError.value)
    }
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
watch(
  () => [props.resource, props.user.role],
  () => {
    search.value = ''
    statusFilter.value = 'all'
    dealerFilter.value = 'all'
    dateRange.value = null
    selectedLine.value = null
    detailOpen.value = false
    editing.value = false
    reversing.value = false
    rows.value = []
    requests.value = []
    mails.value = []
    inboxTab.value = 'incoming'
    void load()
  },
  { immediate: true },
)
watch(inboxTab, () => {
  statusFilter.value = 'all'
})
const dealerOptions = computed(() => {
  const names =
    props.resource === 'inbox'
      ? requests.value.map((row) => row.dealer_name)
      : rows.value.flatMap((row) => ('dealer_name' in row ? [row.dealer_name] : []))
  return [...new Set(names)].sort().map((name) => ({ value: name, label: name }))
})
const filteredRows = computed(() =>
  rows.value.filter((row) => {
    if (props.resource === 'orders') {
      const item = row as OrderLine
      return (
        (statusFilter.value === 'all' ||
          (statusFilter.value === 'open' ? Number(item.remaining_qty) > 0 : Number(item.remaining_qty) === 0)) &&
        (dealerFilter.value === 'all' || item.dealer_name === dealerFilter.value) &&
        includesSearch(
          [item.order_no, item.part_no, item.material_no, item.product_name, item.dealer_name],
          search.value,
        )
      )
    }
    if (props.resource === 'audit') {
      const item = row as AuditEvent
      return (
        (statusFilter.value === 'all' || item.action === statusFilter.value) &&
        withinRange(item.created_at, dateRange.value) &&
        includesSearch(
          [item.actor_name, item.action, item.object_type, item.object_id, item.detail, item.result],
          search.value,
        )
      )
    }
    const item = row as ShipmentLine
    return (
      (statusFilter.value === 'all' || item.status === statusFilter.value) &&
      (dealerFilter.value === 'all' || item.dealer_name === dealerFilter.value) &&
      withinRange(item.received_at, dateRange.value) &&
      includesSearch(
        [
          item.request_no,
          item.sender_email,
          item.dealer_name,
          item.order_no,
          item.material_no,
          item.part_no,
          item.product_name,
          item.receiver,
          item.phone,
        ],
        search.value,
      )
    )
  }),
)
const filteredRequests = computed(() =>
  requests.value.filter(
    (item) =>
      (statusFilter.value === 'all' || shipmentRequestStatus(item) === statusFilter.value) &&
      (dealerFilter.value === 'all' || item.dealer_name === dealerFilter.value) &&
      withinRange(item.received_at, dateRange.value) &&
      includesSearch(
        [item.request_no, item.sender_email, item.dealer_name, item.subject, item.batch_no, item.attachment_name],
        search.value,
      ),
  ),
)
const filteredMails = computed(() =>
  mails.value.filter(
    (item) =>
      (statusFilter.value === 'all' || item.status === statusFilter.value) &&
      withinRange(item.created_at, dateRange.value) &&
      includesSearch([item.recipient, item.subject, item.kind, item.last_error], search.value),
  ),
)
const statusOptions = computed(() => {
  if (props.resource === 'orders')
    return [
      { value: 'open', label: '仍有余额' },
      { value: 'closed', label: '已全部核销' },
    ]
  if (props.resource === 'audit')
    return [...new Set((rows.value as AuditEvent[]).map((row) => row.action))]
      .sort()
      .map((action) => ({ value: action, label: action }))
  return Object.entries(props.resource === 'inbox' && inboxTab.value === 'outgoing' ? mailLabels : shipmentLabels).map(
    ([value, label]) => ({ value, label }),
  )
})
const columns = computed<TableColumnsType<ResourceRow>>(() => {
  if (props.resource === 'orders')
    return [
      { title: '代理商', dataIndex: 'dealer_name', width: 150 },
      { title: '订单号', dataIndex: 'order_no', width: 120 },
      { title: '零件号', dataIndex: 'part_no', width: 110 },
      { title: '物料号', dataIndex: 'material_no', width: 120 },
      { title: '品名', dataIndex: 'product_name', width: 220, ellipsis: true },
      { title: '订单数量', dataIndex: 'ordered_qty', width: 100, align: 'right' },
      { title: '已核销', dataIndex: 'reconciled_qty', width: 90, align: 'right' },
      { title: '剩余未发', dataIndex: 'remaining_qty', width: 100, align: 'right' },
      { title: '单位', dataIndex: 'unit', width: 70 },
    ]
  if (props.resource === 'audit')
    return [
      { title: '时间', dataIndex: 'created_at', width: 168 },
      { title: '操作人', dataIndex: 'actor_name', width: 110 },
      { title: '操作类型', dataIndex: 'action', width: 120 },
      { title: '对象类型', dataIndex: 'object_type', width: 130 },
      { title: '对象编号', dataIndex: 'object_id', width: 170 },
      { title: '内容', dataIndex: 'detail', width: 260, ellipsis: true },
      { title: '结果', dataIndex: 'result', width: 90 },
    ]
  return [
    { title: '申请编号', dataIndex: 'request_no', width: 170 },
    { title: '代理商', dataIndex: 'dealer_name', width: 150 },
    { title: '订单号', dataIndex: 'order_no', width: 120 },
    { title: '物料号', dataIndex: 'material_no', width: 120 },
    { title: '零件号', dataIndex: 'part_no', width: 110 },
    { title: '数量', dataIndex: 'quantity', width: 80, align: 'right' },
    { title: '发货日', dataIndex: 'requested_ship_date', width: 110 },
    { title: '状态', dataIndex: 'status', width: 100 },
    { title: '操作', key: 'actions', fixed: 'right', width: 220 },
  ]
})
const incomingColumns: TableColumnsType<ShipmentRequest> = [
  { title: '接收时间', dataIndex: 'received_at', width: 168 },
  { title: '申请编号', dataIndex: 'request_no', width: 176 },
  { title: '代理商', dataIndex: 'dealer_name', width: 150 },
  { title: '发件邮箱', dataIndex: 'sender_email', width: 190, ellipsis: true },
  { title: '邮件主题', dataIndex: 'subject', width: 240, ellipsis: true },
  { title: '附件', dataIndex: 'attachment_name', width: 180, ellipsis: true },
  { title: '明细', dataIndex: 'line_count', width: 70, align: 'right' },
  { title: '解析状态', key: 'parsedStatus', width: 100 },
]
const outgoingColumns: TableColumnsType<OutboundMail> = [
  { title: '创建时间', dataIndex: 'created_at', width: 168 },
  { title: '类型', dataIndex: 'kind', width: 100 },
  { title: '收件人', dataIndex: 'recipient', width: 190, ellipsis: true },
  { title: '主题', dataIndex: 'subject', width: 260, ellipsis: true },
  { title: '状态', dataIndex: 'status', width: 100 },
  { title: '尝试次数', dataIndex: 'attempts', width: 90, align: 'right' },
  { title: '最近错误', dataIndex: 'last_error', width: 220, ellipsis: true },
  { title: '操作', key: 'retry', width: 100, fixed: 'right' },
]
const pagination = { pageSize: 12, showSizeChanger: false, showTotal: (total: number) => `共 ${total} 条` }
const mailPagination = { ...pagination, showTotal: (total: number) => `共 ${total} 封` }
const emptyDescription = computed(() =>
  search.value || statusFilter.value !== 'all' || dealerFilter.value !== 'all' || dateRange.value
    ? '没有符合条件的数据'
    : '暂无数据',
)
function viewLine(line: ShipmentLine) {
  selectedLine.value = line
  detailOpen.value = true
}
function openEdit(line: ShipmentLine) {
  selectedLine.value = line
  editing.value = true
}
function openReverse(line: ShipmentLine) {
  selectedLine.value = line
  reverseForm.reason = ''
  reverseFormRef.value?.clearValidate()
  reversing.value = true
}
async function confirmLine(line: ShipmentLine) {
  if (submitting.value || props.user.role === 'DEALER' || line.status !== 'PENDING') return
  submitting.value = true
  try {
    await dataApi.confirmLines([line.id])
    message.success('核销成功，供应商邮件已进入发送队列')
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '核销失败')
  } finally {
    submitting.value = false
  }
}
async function reverseLine() {
  if (!selectedLine.value || submitting.value || props.user.role === 'DEALER' || !reverseFormRef.value) return
  try {
    await reverseFormRef.value.validate()
  } catch {
    return
  }
  if (submitting.value || !reversing.value || !selectedLine.value) return
  submitting.value = true
  try {
    await dataApi.reverseLine(selectedLine.value.id, reverseForm.reason)
    message.success('冲销成功，订单余额已恢复')
    reversing.value = false
    selectedLine.value = null
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '冲销失败')
  } finally {
    submitting.value = false
  }
}
async function retryMail(mail: OutboundMail) {
  if (submitting.value || mail.status === 'SENT' || props.user.role === 'DEALER') return
  submitting.value = true
  try {
    await dataApi.retryMail(mail.id)
    message.success('邮件已重新加入发送队列')
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '重试失败')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="resource-page">
    <!-- CHANGE [2026-09-03 14:48 +08:00] [WH400]: 按台账、申请、邮箱和审计语义配置紧凑插画，避免新增大横幅挤占表格。 -->
    <div class="page-title-row">
      <div class="module-title-art">
        <!-- CHANGE [2026-09-03 15:20 +08:00] [WH400]: 邮件收件箱采用用户指定发布会插画，其余模块保持原映射。 -->
        <img :src="`/images/${resource === 'orders' ? 'forecast' : resource === 'shipments' ? 'feature-results' : resource === 'inbox' ? 'mail-announcement' : 'data-output'}.svg`" alt="" aria-hidden="true" width="88" height="72" decoding="async" />
        <div>
        <a-typography-title :level="4">{{ titles[resource] }}</a-typography-title
        ><a-typography-text type="secondary">{{
          resource === 'inbox' ? '原始邮件、解析结果与供应商发件统一留档' : '实时数据，以平台核销流水为准'
        }}</a-typography-text>
        </div>
      </div>
      <a-button v-if="resource !== 'orders' || ordersView === 'summary'" :loading="loading" @click="load"
        ><template #icon><ReloadOutlined /></template>刷新</a-button
      >
    </div>
    <!-- CHANGE [2026-09-03 09:01 +08:00] [WH400]: 以视图切换入口保留原列表，独立加载每日台账及其错误提示。 -->
    <div v-if="resource === 'orders'" class="order-view-tabs" role="tablist" aria-label="订单台账视图">
      <a-button role="tab" :aria-selected="ordersView === 'summary'" :type="ordersView === 'summary' ? 'primary' : 'default'" @click="ordersView = 'summary'">订单汇总</a-button>
      <a-button role="tab" :aria-selected="ordersView === 'daily'" :type="ordersView === 'daily' ? 'primary' : 'default'" @click="ordersView = 'daily'">每日发货明细</a-button>
    </div>
    <a-alert v-if="loadError && (resource !== 'orders' || ordersView === 'summary')" class="page-alert" type="error" show-icon message="数据加载失败" :description="loadError"
      ><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert
    >
    <OrderDailyShipments v-if="resource === 'orders' && ordersView === 'daily'" />
    <section v-else class="surface resource-table">
      <a-space class="filter-row" wrap>
        <a-input-search v-model:value="search" placeholder="搜索编号、物料、客户或内容" allow-clear />
        <a-select
          v-model:value="statusFilter"
          :options="[{ value: 'all', label: resource === 'audit' ? '全部操作' : '全部状态' }, ...statusOptions]"
          aria-label="状态筛选"
        />
        <a-select
          v-if="resource !== 'audit' && !(resource === 'inbox' && inboxTab === 'outgoing')"
          v-model:value="dealerFilter"
          :options="[{ value: 'all', label: '全部代理商' }, ...dealerOptions]"
          aria-label="代理商筛选"
        />
        <a-range-picker
          v-if="resource !== 'orders'"
          :value="dateRange ?? undefined"
          @update:value="(value) => (dateRange = value as DateRange)"
        />
      </a-space>
      <a-tabs v-if="resource === 'inbox'" v-model:active-key="inboxTab">
        <a-tab-pane key="incoming" :tab="`收件记录（${filteredRequests.length}）`">
          <a-table
            row-key="id"
            :loading="loading"
            :columns="incomingColumns"
            :data-source="filteredRequests"
            :scroll="{ x: 1250 }"
            :pagination="mailPagination"
          >
            <template #bodyCell="{ column, text, record }"
              ><template v-if="column.dataIndex === 'received_at'">{{ formatChinaDateTime(text) }}</template
              ><StatusTag
                v-else-if="column.key === 'parsedStatus'"
                :status="shipmentRequestStatus(record as ShipmentRequest)"
            /></template>
            <template #emptyText><a-empty :description="emptyDescription" /></template>
          </a-table>
        </a-tab-pane>
        <a-tab-pane v-if="user.role !== 'DEALER'" key="outgoing" :tab="`供应商发件（${filteredMails.length}）`">
          <a-table
            row-key="id"
            :loading="loading"
            :columns="outgoingColumns"
            :data-source="filteredMails"
            :scroll="{ x: 1250 }"
            :pagination="mailPagination"
          >
            <template #bodyCell="{ column, text, record }">
              <template v-if="column.dataIndex === 'created_at'">{{ formatChinaDateTime(text) }}</template
              ><template v-else-if="column.dataIndex === 'kind'">{{
                text === 'CORRECTION' ? '冲销更正' : '发货指令'
              }}</template>
              <a-tag
                v-else-if="column.dataIndex === 'status'"
                :color="mailColors[record.status as OutboundMail['status']]"
                >{{ mailLabels[record.status as OutboundMail['status']] }}</a-tag
              >
              <template v-else-if="column.dataIndex === 'last_error'">{{ text || '-' }}</template>
              <a-button
                v-else-if="column.key === 'retry'"
                type="link"
                size="small"
                :disabled="record.status === 'SENT' || submitting"
                @click="retryMail(record as OutboundMail)"
                ><template #icon><SendOutlined /></template>重新发送</a-button
              >
            </template>
            <template #emptyText><a-empty :description="emptyDescription" /></template>
          </a-table>
        </a-tab-pane>
      </a-tabs>
      <a-table
        v-else
        row-key="id"
        :loading="loading"
        :columns="columns"
        :data-source="filteredRows"
        :scroll="{ x: resource === 'shipments' ? 1250 : 1100 }"
        :pagination="pagination"
      >
        <template #bodyCell="{ column, text, record }">
          <template v-if="column.dataIndex === 'created_at'">{{ formatChinaDateTime(text) }}</template
          ><strong v-else-if="column.dataIndex === 'remaining_qty'" class="text-success">{{ text }}</strong>
          <template v-else-if="column.dataIndex === 'part_no'">{{ text || '-' }}</template
          ><StatusTag v-else-if="column.dataIndex === 'status'" :status="record.status" />
          <a-space v-else-if="column.key === 'actions'" :size="2">
            <a-button type="link" size="small" @click="viewLine(record as ShipmentLine)"
              ><template #icon><EyeOutlined /></template>查看</a-button
            >
            <a-button
              type="link"
              size="small"
              :disabled="!['PENDING', 'EXCEPTION'].includes(record.status) || submitting"
              @click="openEdit(record as ShipmentLine)"
              ><template #icon><EditOutlined /></template>修改</a-button
            >
            <a-button
              v-if="user.role !== 'DEALER' && record.status === 'PENDING'"
              type="link"
              size="small"
              :disabled="submitting"
              @click="confirmLine(record as ShipmentLine)"
              ><template #icon><CheckOutlined /></template>核销</a-button
            >
            <a-button
              v-if="user.role !== 'DEALER' && record.status === 'RECONCILED'"
              type="link"
              size="small"
              danger
              :disabled="submitting"
              @click="openReverse(record as ShipmentLine)"
              ><template #icon><RetweetOutlined /></template>冲销</a-button
            >
          </a-space>
        </template>
        <template #emptyText><a-empty :description="emptyDescription" /></template>
      </a-table>
    </section>
    <ShipmentDetailModal :open="detailOpen" :line="selectedLine" @close="detailOpen = false" />
    <ShipmentEditModal v-model:open="editing" :line="selectedLine" @saved="load" />
    <a-modal
      title="冲销已核销申请"
      :open="reversing"
      ok-text="确认冲销"
      :ok-button-props="{ danger: true }"
      :confirm-loading="submitting"
      :cancel-button-props="{ disabled: submitting }"
      :closable="!submitting"
      :mask-closable="!submitting"
      destroy-on-close
      @cancel="reversing = false"
      @ok="reverseLine"
    >
      <a-alert type="warning" show-icon message="冲销后将恢复订单余额，并向供应商生成更正邮件。" />
      <a-form ref="reverseFormRef" :model="reverseForm" layout="vertical" class="modal-form-spaced"
        ><a-form-item
          name="reason"
          label="冲销原因"
          :rules="[{ required: true, min: 3, message: '请填写至少 3 个字的冲销原因' }]"
          ><a-textarea v-model:value="reverseForm.reason" :rows="3" :maxlength="500" show-count /></a-form-item
      ></a-form>
    </a-modal>
  </div>
</template>
