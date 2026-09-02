import { defineComponent, h } from 'vue'
import type { Component } from 'vue'
import { App, ConfigProvider } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'

export function mountPage(component: Component, props: Record<string, unknown> = {}) {
  return mount(
    defineComponent({
      setup: () => () =>
        h(ConfigProvider, { locale: zhCN }, { default: () => h(App, {}, { default: () => h(component, props) }) }),
    }),
    { attachTo: document.body },
  )
}
export function button(wrapper: VueWrapper, label: string) {
  const found = wrapper.findAll('button').find((item) => item.text().replace(/\s/g, '') === label.replace(/\s/g, ''))
  if (!found) throw new Error(`Missing button: ${label}`)
  return found
}
export function dialogButton(label: string) {
  const found = [...document.querySelectorAll<HTMLButtonElement>('.ant-modal button')].find(
    (item) => item.textContent?.replace(/\s/g, '') === label.replace(/\s/g, ''),
  )
  if (!found) throw new Error(`Missing dialog button: ${label}`)
  return found
}
export function fillDialog(label: string, value: string) {
  const field = [...document.querySelectorAll('.ant-modal .ant-form-item')].find((item) =>
    item.querySelector('label')?.textContent?.includes(label),
  )
  const input = field?.querySelector<HTMLInputElement | HTMLTextAreaElement>('input, textarea')
  if (!input) throw new Error(`Missing dialog input: ${label}`)
  input.value = value
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new Event('change', { bubbles: true }))
}
