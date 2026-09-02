<script setup lang="ts">
import { nextTick, reactive, ref, watch } from 'vue'
import {
  App,
  DatePicker as ADatePicker,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputNumber as AInputNumber,
  Modal as AModal,
  Textarea as ATextarea,
} from 'ant-design-vue'
import type { FormInstance } from 'ant-design-vue'
import dayjs from 'dayjs'
import type { Dayjs } from 'dayjs'
import { dataApi } from '../api/client'
import type { ShipmentLine } from '../types'

const props = withDefaults(
  defineProps<{ open: boolean; line: ShipmentLine | null; quantityMin?: number; quantityPrecision?: number }>(),
  { quantityMin: 0.01, quantityPrecision: 2 },
)
const emit = defineEmits<{ 'update:open': [open: boolean]; saved: [] }>()
const { message } = App.useApp()
const formRef = ref<FormInstance>()
const saving = ref(false)
const form = reactive({
  order_no: '',
  material_no: '',
  quantity: 1 as number | undefined,
  requested_ship_date: undefined as Dayjs | undefined,
  receiver: '',
  phone: '',
  address: '',
  remark: '',
})
watch(
  () => [props.open, props.line] as const,
  async () => {
    if (!props.open || !props.line) return
    const line = props.line
    Object.assign(form, {
      order_no: line.order_no,
      material_no: line.material_no,
      quantity: Number(line.quantity),
      requested_ship_date: dayjs(line.requested_ship_date),
      receiver: line.receiver,
      phone: line.phone,
      address: line.address,
      remark: line.remark,
    })
    await nextTick()
    formRef.value?.clearValidate()
  },
  { immediate: true },
)
async function save() {
  if (!props.line || saving.value || !formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (saving.value || !props.open || !form.requested_ship_date || form.quantity == null) return
  saving.value = true
  try {
    await dataApi.updateLine(props.line.id, {
      ...form,
      quantity: form.quantity,
      requested_ship_date: form.requested_ship_date.format('YYYY-MM-DD'),
    })
    message.success('申请已更新并重新匹配')
    emit('update:open', false)
    emit('saved')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '修改失败')
  } finally {
    saving.value = false
  }
}
</script>
<template>
  <a-modal
    title="修改待处理申请"
    :open="open"
    :confirm-loading="saving"
    :closable="!saving"
    :mask-closable="!saving"
    :cancel-button-props="{ disabled: saving }"
    ok-text="保存并重新匹配"
    destroy-on-close
    @cancel="emit('update:open', false)"
    @ok="save"
  >
    <a-form ref="formRef" :model="form" layout="vertical">
      <a-form-item name="order_no" label="订单号" :rules="[{ required: true }]"
        ><a-input v-model:value="form.order_no" :maxlength="80"
      /></a-form-item>
      <a-form-item name="material_no" label="物料号" :rules="[{ required: true }]"
        ><a-input v-model:value="form.material_no" :maxlength="80"
      /></a-form-item>
      <a-form-item name="quantity" label="数量" :rules="[{ required: true }]"
        ><a-input-number
          v-model:value="form.quantity"
          :min="quantityMin"
          :precision="quantityPrecision"
          style="width: 100%"
      /></a-form-item>
      <a-form-item name="requested_ship_date" label="要求发货日期" :rules="[{ required: true }]"
        ><a-date-picker v-model:value="form.requested_ship_date" style="width: 100%"
      /></a-form-item>
      <a-form-item name="receiver" label="收货人" :rules="[{ required: true }]"
        ><a-input v-model:value="form.receiver" :maxlength="100"
      /></a-form-item>
      <a-form-item name="phone" label="联系电话" :rules="[{ required: true }]"
        ><a-input v-model:value="form.phone" :maxlength="50"
      /></a-form-item>
      <a-form-item name="address" label="收货地址" :rules="[{ required: true }]"
        ><a-textarea v-model:value="form.address" :rows="2" :maxlength="500" show-count
      /></a-form-item>
      <a-form-item name="remark" label="备注"
        ><a-textarea v-model:value="form.remark" :rows="2" :maxlength="1000" show-count
      /></a-form-item>
    </a-form>
  </a-modal>
</template>
