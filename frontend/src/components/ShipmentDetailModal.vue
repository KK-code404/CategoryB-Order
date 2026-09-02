<script setup lang="ts">
import { computed } from 'vue'
import {
  Descriptions as ADescriptions,
  DescriptionsItem as ADescriptionsItem,
  Grid,
  Modal as AModal,
} from 'ant-design-vue'
import type { ShipmentLine } from '../types'
import StatusTag from './StatusTag.vue'
defineProps<{ open: boolean; line: ShipmentLine | null }>()
const emit = defineEmits<{ close: [] }>()
const screens = Grid.useBreakpoint()
const detailColumns = computed(() => (screens.value.sm ? 2 : 1))
</script>
<template>
  <a-modal title="发货申请详情" :open="open" :footer="null" :width="720" @cancel="emit('close')">
    <a-descriptions v-if="line" bordered size="small" :column="detailColumns">
      <a-descriptions-item label="申请编号">{{ line.request_no }}</a-descriptions-item
      ><a-descriptions-item label="状态"><StatusTag :status="line.status" /></a-descriptions-item>
      <a-descriptions-item label="代理商">{{ line.dealer_name }}</a-descriptions-item
      ><a-descriptions-item label="来源邮箱">{{ line.sender_email }}</a-descriptions-item>
      <a-descriptions-item label="订单号">{{ line.order_no }}</a-descriptions-item
      ><a-descriptions-item label="物料/零件"
        >{{ line.material_no }} / {{ line.part_no || '待匹配' }}</a-descriptions-item
      >
      <a-descriptions-item label="申请数量">{{ line.quantity }}</a-descriptions-item
      ><a-descriptions-item label="剩余未发">{{ line.remaining_qty ?? '-' }}</a-descriptions-item>
      <a-descriptions-item label="收货人">{{ line.receiver }} · {{ line.phone }}</a-descriptions-item
      ><a-descriptions-item label="要求发货日">{{ line.requested_ship_date }}</a-descriptions-item>
      <a-descriptions-item label="收货地址" :span="detailColumns">{{ line.address }}</a-descriptions-item
      ><a-descriptions-item label="备注" :span="detailColumns">{{ line.remark || '无' }}</a-descriptions-item>
      <a-descriptions-item label="匹配说明" :span="detailColumns">{{
        line.exception_reason || '匹配正常'
      }}</a-descriptions-item>
    </a-descriptions>
  </a-modal>
</template>
