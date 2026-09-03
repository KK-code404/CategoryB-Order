<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import {
  App,
  Alert as AAlert,
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
  Modal as AModal,
  Result as AResult,
  Select as ASelect,
  Space as ASpace,
  Switch as ASwitch,
  Table as ATable,
  Tabs as ATabs,
  TabPane as ATabPane,
  Tag as ATag,
  TypographyTitle as ATypographyTitle,
  TypographyText as ATypographyText,
  UploadDragger as AUploadDragger,
} from 'ant-design-vue'
import type { FormInstance, TableColumnsType, UploadProps } from 'ant-design-vue'
import { DownloadOutlined, EditOutlined, InboxOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { dataApi } from '../api/client'
import type { AdminConfig, Role, User } from '../types'

const props = defineProps<{ user: User }>()
type ConfigKind = 'dealer' | 'supplier' | 'material' | 'user'
type ConfigRow =
  | AdminConfig['dealers'][number]
  | AdminConfig['suppliers'][number]
  | AdminConfig['materials'][number]
  | AdminConfig['users'][number]
const createTitles: Record<ConfigKind, string> = {
  dealer: '新增代理商',
  supplier: '新增供应商',
  material: '新增物料映射',
  user: '新增用户',
}
const editTitles: Record<ConfigKind, string> = {
  dealer: '编辑代理商',
  supplier: '编辑供应商',
  material: '编辑物料映射',
  user: '编辑用户',
}
const roleLabels: Record<Role, string> = { ADMIN: '管理员', SALES: '零件销售', DEALER: '代理商' }
const { message } = App.useApp()
const config = ref<AdminConfig | null>(null)
const loading = ref(true)
const loadError = ref('')
const importPreview = ref<Awaited<ReturnType<typeof dataApi.previewOrderImport>> | null>(null)
const importing = ref(false)
const saving = ref(false)
const dialogKind = ref<ConfigKind | null>(null)
const editId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const defaults = () => ({
  code: '',
  name: '',
  email: '',
  active: true,
  material_no: '',
  part_no: '',
  product_name: '',
  brand_code: '',
  supplier_code: undefined as string | undefined,
  display_name: '',
  password: '',
  role: 'SALES' as Role,
  dealer_code: undefined as string | undefined,
})
const form = reactive(defaults())
const editingSelf = computed(() => dialogKind.value === 'user' && editId.value === props.user.id)
const suppliers = computed(() =>
  (config.value?.suppliers ?? [])
    .filter((item) => item.active)
    .map((item) => ({ value: item.code, label: `${item.code} · ${item.name}` })),
)
const dealers = computed(() =>
  (config.value?.dealers ?? [])
    .filter((item) => item.active)
    .map((item) => ({ value: item.code, label: `${item.code} · ${item.name}` })),
)
let loadVersion = 0
onUnmounted(() => {
  loadVersion++
})
async function load() {
  if (props.user.role !== 'ADMIN') {
    loading.value = false
    return
  }
  const version = ++loadVersion
  loading.value = true
  loadError.value = ''
  try {
    const result = await dataApi.adminConfig()
    if (version === loadVersion) config.value = result
  } catch (error) {
    if (version === loadVersion) {
      loadError.value = error instanceof Error ? error.message : '配置加载失败'
      message.error(loadError.value)
    }
  } finally {
    if (version === loadVersion) loading.value = false
  }
}
onMounted(load)
const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  if (importing.value) return false
  if (!file.name.toLowerCase().endsWith('.xlsx') || file.size > 5 * 1024 * 1024) {
    message.error('请上传不超过 5 MB 的 .xlsx 文件')
    return false
  }
  importing.value = true
  void dataApi
    .previewOrderImport(file)
    .then((result) => {
      importPreview.value = result
      message.success('订单文件校验完成')
    })
    .catch((error) => message.error(error instanceof Error ? error.message : '订单文件校验失败'))
    .finally(() => {
      importing.value = false
    })
  return false
}
async function commitImport() {
  if (!importPreview.value || importPreview.value.error_count || importing.value) return
  importing.value = true
  try {
    const result = await dataApi.commitOrderImport(importPreview.value.token)
    message.success(`已导入 ${result.imported} 行订单`)
    importPreview.value = null
    await load()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '订单导入失败')
  } finally {
    importing.value = false
  }
}
async function openConfig(kind: ConfigKind, row?: ConfigRow) {
  Object.assign(form, defaults(), row ?? {})
  form.password = ''
  editId.value = row?.id ?? null
  dialogKind.value = kind
  await nextTick()
  formRef.value?.clearValidate()
}
async function submitConfig() {
  const kind = dialogKind.value
  if (!kind || saving.value || !formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (saving.value || dialogKind.value !== kind) return
  // Only send fields belonging to this dialog; never leak a previous form's data.
  let values: Record<string, unknown>
  if (kind === 'dealer' || kind === 'supplier')
    values = { code: form.code, name: form.name, email: form.email, ...(editId.value ? { active: form.active } : {}) }
  else if (kind === 'material')
    values = {
      material_no: form.material_no,
      part_no: form.part_no,
      product_name: form.product_name,
      brand_code: form.brand_code,
      supplier_code: form.supplier_code,
    }
  else
    values = {
      display_name: form.display_name,
      email: form.email,
      role: form.role,
      dealer_code: form.role === 'DEALER' ? form.dealer_code : null,
      ...(form.password ? { password: form.password } : {}),
      ...(editId.value ? { active: form.active } : {}),
    }
  const refreshSession = editingSelf.value
  saving.value = true
  try {
    const create = {
      dealer: dataApi.createDealer,
      supplier: dataApi.createSupplier,
      material: dataApi.createMaterial,
      user: dataApi.createUser,
    }
    const update = {
      dealer: dataApi.updateDealer,
      supplier: dataApi.updateSupplier,
      material: dataApi.updateMaterial,
      user: dataApi.updateUser,
    }
    if (editId.value) await update[kind](editId.value, values)
    else await create[kind](values)
    message.success(`${editId.value ? editTitles[kind] : createTitles[kind]}成功`)
    dialogKind.value = null
    await load()
    if (refreshSession) window.location.reload()
  } catch (error) {
    message.error(error instanceof Error ? error.message : '保存失败')
  } finally {
    saving.value = false
  }
}
const actions = { title: '操作', key: 'actions', width: 90, fixed: 'right' as const }
const columns: Record<ConfigKind, TableColumnsType<ConfigRow>> = {
  material: [
    { title: '物料号', dataIndex: 'material_no', width: 130 },
    { title: '零件号', dataIndex: 'part_no', width: 120 },
    { title: '品名', dataIndex: 'product_name', width: 240, ellipsis: true },
    { title: '品牌', dataIndex: 'brand_code', width: 100 },
    { title: '供应商', dataIndex: 'supplier_code', width: 110 },
    actions,
  ],
  dealer: [
    { title: '编码', dataIndex: 'code', width: 100 },
    { title: '名称', dataIndex: 'name', width: 180 },
    { title: '发件邮箱', dataIndex: 'email', width: 220 },
    { title: '状态', dataIndex: 'active', width: 80 },
    actions,
  ],
  supplier: [
    { title: '编码', dataIndex: 'code', width: 100 },
    { title: '名称', dataIndex: 'name', width: 180 },
    { title: '收件邮箱', dataIndex: 'email', width: 220 },
    { title: '状态', dataIndex: 'active', width: 80 },
    actions,
  ],
  user: [
    { title: '姓名', dataIndex: 'display_name', width: 140 },
    { title: '账号或邮箱', dataIndex: 'email', width: 200 },
    { title: '角色', dataIndex: 'role', width: 100 },
    { title: '代理商', dataIndex: 'dealer_code', width: 110 },
    { title: '状态', dataIndex: 'active', width: 80 },
    actions,
  ],
}
const tables = computed(() => [
  { kind: 'material' as const, label: '物料映射', rows: config.value?.materials ?? [], width: 850 },
  { kind: 'dealer' as const, label: '代理商', rows: config.value?.dealers ?? [], width: 720 },
  { kind: 'supplier' as const, label: '供应商', rows: config.value?.suppliers ?? [], width: 720 },
  { kind: 'user' as const, label: '用户', rows: config.value?.users ?? [], width: 820 },
])
</script>

<template>
  <a-result v-if="user.role !== 'ADMIN'" status="403" title="仅管理员可维护后台配置" />
  <div v-else class="resource-page">
    <!-- CHANGE [2026-09-03 14:48 +08:00] [WH400]: 用功能配置插画区分管理模块，保持刷新及配置表单原有交互。 -->
    <div class="page-title-row">
      <div class="module-title-art">
        <img src="/images/feature-results.svg" alt="" aria-hidden="true" width="88" height="72" decoding="async" />
        <div>
        <a-typography-title :level="4">后台配置</a-typography-title
        ><a-typography-text type="secondary">维护账号、邮件归属和供应商路由</a-typography-text>
        </div>
      </div>
      <a-button :loading="loading" @click="load"
        ><template #icon><ReloadOutlined /></template>刷新</a-button
      >
    </div>
    <a-alert v-if="loadError" class="page-alert" type="error" show-icon message="配置加载失败" :description="loadError"
      ><template #action><a-button size="small" @click="load">重试</a-button></template></a-alert
    >
    <div class="settings-grid">
      <section class="surface settings-section">
        <h3>订单批量导入</h3>
        <p>先校验 Excel，再确认写入；示例行请在正式上传前替换或删除。</p>
        <a-space class="template-links" wrap
          ><a-button href="/templates/销售订单导入模板.xlsx" download
            ><template #icon><DownloadOutlined /></template>下载订单模板</a-button
          ><a-button href="/templates/发货申请标准模板.xlsx" download
            ><template #icon><DownloadOutlined /></template>下载发货模板</a-button
          ></a-space
        ><a-upload-dragger
          accept=".xlsx"
          :max-count="1"
          :show-upload-list="false"
          :before-upload="beforeUpload"
          :disabled="importing"
          ><p class="ant-upload-drag-icon"><InboxOutlined /></p>
          <p>{{ importing ? '正在处理…' : '点击或拖放订单 Excel 到此处' }}</p>
          <p class="muted">仅支持无宏 .xlsx，单文件不超过 5 MB</p></a-upload-dragger
        >
      </section>
      <section class="surface settings-section">
        <h3>新增主数据</h3>
        <p>所有新增与修改动作都会写入操作日志。</p>
        <a-space direction="vertical" style="width: 100%"
          ><a-button v-for="(title, kind) in createTitles" :key="kind" block @click="openConfig(kind)"
            ><template #icon><PlusOutlined /></template>{{ title }}</a-button
          ></a-space
        >
        <dl>
          <dt>当前账号</dt>
          <dd>{{ user.display_name }} / 管理员</dd>
          <dt>邮件抓取</dt>
          <dd>IMAP 每分钟轮询</dd>
          <dt>供应商通知</dt>
          <dd>失败自动重试 5 次，也可手动重试</dd>
        </dl>
      </section>
    </div>
    <section class="surface config-tables">
      <a-tabs
        ><a-tab-pane v-for="table in tables" :key="table.kind" :tab="`${table.label}（${table.rows.length}）`"
          ><a-table
            row-key="id"
            size="small"
            :loading="loading"
            :data-source="table.rows"
            :columns="columns[table.kind]"
            :pagination="{ pageSize: 10, showSizeChanger: false }"
            :scroll="{ x: table.width }"
            ><template #bodyCell="{ column, text, record }"
              ><a-tag v-if="column.dataIndex === 'active'" :color="text ? 'success' : 'default'">{{
                text ? '启用' : '停用'
              }}</a-tag
              ><template v-else-if="column.dataIndex === 'role'">{{ roleLabels[text as Role] }}</template
              ><template v-else-if="column.dataIndex === 'dealer_code'">{{ text || '-' }}</template
              ><a-button
                v-else-if="column.key === 'actions'"
                type="link"
                size="small"
                @click="openConfig(table.kind, record as ConfigRow)"
                ><template #icon><EditOutlined /></template>编辑</a-button
              ></template
            ></a-table
          ></a-tab-pane
        ></a-tabs
      >
    </section>
    <a-modal
      :title="dialogKind ? (editId ? editTitles[dialogKind] : createTitles[dialogKind]) : ''"
      :open="Boolean(dialogKind)"
      ok-text="保存"
      :confirm-loading="saving"
      :closable="!saving"
      :mask-closable="!saving"
      :cancel-button-props="{ disabled: saving }"
      destroy-on-close
      @cancel="dialogKind = null"
      @ok="submitConfig"
    >
      <a-form ref="formRef" :model="form" layout="vertical">
        <template v-if="dialogKind === 'dealer' || dialogKind === 'supplier'">
          <a-form-item name="code" label="编码" :rules="[{ required: true }]"
            ><a-input v-model:value="form.code" :maxlength="50"
          /></a-form-item>
          <a-form-item name="name" label="名称" :rules="[{ required: true }]"
            ><a-input v-model:value="form.name" :maxlength="120"
          /></a-form-item>
          <a-form-item
            name="email"
            :label="dialogKind === 'dealer' ? '发件邮箱' : '供应商收件邮箱'"
            :rules="[{ required: true, type: 'email' }]"
            ><a-input v-model:value="form.email" :maxlength="255"
          /></a-form-item>
          <a-form-item v-if="editId" name="active" label="状态"
            ><a-switch v-model:checked="form.active" checked-children="启用" un-checked-children="停用"
          /></a-form-item>
        </template>
        <template v-if="dialogKind === 'material'">
          <a-form-item name="material_no" label="物料号" :rules="[{ required: true }]"
            ><a-input v-model:value="form.material_no" :maxlength="80"
          /></a-form-item>
          <a-form-item name="part_no" label="零件号" :rules="[{ required: true }]"
            ><a-input v-model:value="form.part_no" :maxlength="80"
          /></a-form-item>
          <a-form-item name="product_name" label="品名" :rules="[{ required: true }]"
            ><a-input v-model:value="form.product_name" :maxlength="255"
          /></a-form-item>
          <a-form-item name="brand_code" label="品牌编码" :rules="[{ required: true }]"
            ><a-input v-model:value="form.brand_code" :maxlength="50"
          /></a-form-item>
          <a-form-item name="supplier_code" label="供应商" :rules="[{ required: true }]"
            ><a-select v-model:value="form.supplier_code" :options="suppliers"
          /></a-form-item>
        </template>
        <template v-if="dialogKind === 'user'">
          <a-form-item name="display_name" label="姓名" :rules="[{ required: true }]"
            ><a-input v-model:value="form.display_name" :maxlength="80"
          /></a-form-item>
          <a-form-item name="email" label="账号或邮箱" :rules="[{ required: true, min: 3 }]"
            ><a-input v-model:value="form.email" :maxlength="255"
          /></a-form-item>
          <a-form-item
            name="password"
            :label="editId ? '重置密码（不修改请留空）' : '初始密码'"
            :rules="[{ required: !editId, min: 10 }]"
            ><a-input-password v-model:value="form.password" :maxlength="128" autocomplete="new-password"
          /></a-form-item>
          <a-form-item name="role" label="角色" :rules="[{ required: true }]"
            ><a-select
              v-model:value="form.role"
              :disabled="editingSelf"
              :options="Object.entries(roleLabels).map(([value, label]) => ({ value, label }))"
          /></a-form-item>
          <a-form-item v-if="form.role === 'DEALER'" name="dealer_code" label="绑定代理商" :rules="[{ required: true }]"
            ><a-select v-model:value="form.dealer_code" :options="dealers"
          /></a-form-item>
          <a-form-item v-if="editId" name="active" label="状态"
            ><a-switch
              v-model:checked="form.active"
              checked-children="启用"
              un-checked-children="停用"
              :disabled="editingSelf"
          /></a-form-item>
        </template>
      </a-form>
    </a-modal>
    <a-modal
      title="订单导入校验结果"
      :open="Boolean(importPreview)"
      ok-text="确认导入"
      :confirm-loading="importing"
      :ok-button-props="{ disabled: Boolean(importPreview?.error_count) }"
      :closable="!importing"
      :mask-closable="!importing"
      :cancel-button-props="{ disabled: importing }"
      @cancel="importPreview = null"
      @ok="commitImport"
      ><p>
        有效数据：<strong>{{ importPreview?.valid_count ?? 0 }}</strong> 行；错误：<strong
          :class="importPreview?.error_count ? 'text-warning' : 'text-success'"
          >{{ importPreview?.error_count ?? 0 }}</strong
        >
        行。
      </p>
      <div class="import-errors">
        <p v-for="error in importPreview?.errors" :key="`${error.row}-${error.message}`">
          第 {{ error.row }} 行：{{ error.message }}
        </p>
      </div></a-modal
    >
  </div>
</template>
