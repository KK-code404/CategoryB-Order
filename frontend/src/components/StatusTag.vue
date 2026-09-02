<script setup lang="ts">
import { Tag as ATag } from 'ant-design-vue'
import type { ShipmentStatus } from '../types'
import { shipmentColors, shipmentLabels } from '../utils/shipments'
defineProps<{ status: ShipmentStatus }>()
</script>
<template>
  <a-tag :color="shipmentColors[status]">{{ shipmentLabels[status] }}</a-tag>
</template>
