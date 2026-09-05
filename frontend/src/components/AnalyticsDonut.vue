<script setup lang="ts">
import { computed } from 'vue'
import { formatQty as qty } from '../utils/reconciliationAnalytics'
const props = defineProps<{ title: string; segments: Array<{ label: string; value: number; color: string }>; unit: string; empty?: string }>()
const total = computed(() => props.segments.reduce((sum, s) => sum + Math.round(s.value * 100), 0) / 100)
const valid = computed(() => props.segments.every(s => Number.isFinite(s.value) && s.value >= 0))
const arcs = computed(() => {
  let offset = 0
  return props.segments.map(s => { const share = total.value > 0 ? s.value / total.value * 100 : 0; const result = { ...s, share, offset }; offset += share; return result })
})
const description = computed(() => `${props.title}：${arcs.value.map(s => `${s.label} ${qty(s.value)} ${props.unit}，${s.share.toFixed(1)}%`).join('；')}`)
</script>
<template>
  <div class="analytics-donut">
    <p v-if="!valid" class="donut-empty">含负向或异常数据，占比不适用，请查看柱状图。</p>
    <template v-else>
      <svg viewBox="0 0 220 220" role="img" :aria-label="description">
        <circle cx="110" cy="110" r="78" fill="none" stroke="var(--border, #e7e8f2)" stroke-width="22" />
        <circle v-for="arc in arcs.filter(a => a.value > 0)" :key="arc.label" cx="110" cy="110" r="78" pathLength="100" fill="none" :stroke="arc.color" stroke-width="22" :stroke-dasharray="`${arc.share} ${100 - arc.share}`" :stroke-dashoffset="-arc.offset" transform="rotate(-90 110 110)"><title>{{ arc.label }}：{{ qty(arc.value) }} {{ unit }}（{{ arc.share.toFixed(1) }}%）</title></circle>
        <text x="110" y="109" text-anchor="middle" class="donut-total">{{ qty(total) }}</text><text x="110" y="133" text-anchor="middle" class="donut-unit">{{ unit }}</text>
      </svg>
      <p v-if="total === 0" class="donut-empty">{{ empty || '当前范围暂无数据' }}</p>
      <ul v-else class="donut-legend"><li v-for="arc in arcs" :key="arc.label"><span><i :style="{ backgroundColor: arc.color }" />{{ arc.label }}</span><strong>{{ qty(arc.value) }}<small>{{ arc.share.toFixed(1) }}%</small></strong></li></ul>
    </template>
  </div>
</template>
<style scoped>
.analytics-donut svg { display: block; width: min(100%, 210px); margin: 0 auto; }
.donut-total { fill: var(--text); font: 650 29px 'Segoe UI', 'Microsoft YaHei', sans-serif; font-variant-numeric: tabular-nums; }
.donut-unit { fill: var(--text-secondary); font: 12px 'Segoe UI', 'Microsoft YaHei', sans-serif; }
.donut-legend { list-style: none; padding: 0; margin: 8px 0 0; display: grid; gap: 10px; }
.donut-legend li, .donut-legend li > span { display: flex; align-items: center; gap: 8px; }
.donut-legend li { justify-content: space-between; font-size: 12px; color: var(--text-secondary); }
.donut-legend i { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }
.donut-legend strong { color: var(--text); font-weight: 600; white-space: nowrap; }
.donut-legend small { display: inline-block; min-width: 52px; margin-left: 8px; text-align: right; color: var(--text-secondary); font-weight: 400; }
.donut-empty { color: var(--text-secondary); font-size: 13px; line-height: 1.7; text-align: center; padding: 16px 0; }
</style>
