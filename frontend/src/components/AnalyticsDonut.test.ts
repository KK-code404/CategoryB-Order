import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AnalyticsDonut from './AnalyticsDonut.vue'

describe('占比图', () => {
  it('exposes exact counts and percentages without a table', () => {
    const wrapper = mount(AnalyticsDonut, { props: { title: '发货占比', unit: '桶', segments: [{ label: '甲', value: 102, color: '#665cf6' }, { label: '乙', value: 38, color: '#208d8a' }] } })
    expect(wrapper.find('svg').attributes('aria-label')).toContain('甲 102 桶，72.9%')
    expect(wrapper.find('svg').attributes('aria-label')).toContain('乙 38 桶，27.1%')
    expect(wrapper.findAll('table')).toHaveLength(0)
  })
  it('does not invent shares for zero or negative quantities', () => {
    const empty = mount(AnalyticsDonut, { props: { title: '空值', unit: '桶', segments: [] } })
    expect(empty.text()).toContain('当前范围暂无数据')
    expect(empty.html()).not.toMatch(/NaN|Infinity/)
    const negative = mount(AnalyticsDonut, { props: { title: '冲销', unit: '桶', segments: [{ label: '甲', value: -10, color: '#665cf6' }] } })
    expect(negative.text()).toContain('占比不适用')
    expect(negative.find('svg').exists()).toBe(false)
  })
})
