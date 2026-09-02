import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { dataApi } from '../api/client'
import { admin, dashboard, dealer, line, mail, order, request } from '../test/fixtures'
import { button, dialogButton, mountPage } from '../test/helpers'
import ResourcePage from './ResourcePage.vue'

vi.mock('../api/client', () => ({
  dataApi: {
    orders: vi.fn(),
    shipmentLines: vi.fn(),
    shipmentRequests: vi.fn(),
    outboundMails: vi.fn(),
    auditEvents: vi.fn(),
    confirmLines: vi.fn(),
    reverseLine: vi.fn(),
    retryMail: vi.fn(),
  },
}))
beforeEach(() => {
  vi.mocked(dataApi.orders).mockReset().mockResolvedValue([order])
  vi.mocked(dataApi.shipmentLines).mockReset().mockResolvedValue([line])
  vi.mocked(dataApi.shipmentRequests).mockReset().mockResolvedValue([request])
  vi.mocked(dataApi.outboundMails).mockReset().mockResolvedValue([mail])
  vi.mocked(dataApi.auditEvents).mockReset().mockResolvedValue(dashboard.audit_events)
  vi.mocked(dataApi.confirmLines).mockReset().mockResolvedValue({ confirmed: 1, outbound_mails: 1 })
  vi.mocked(dataApi.reverseLine)
    .mockReset()
    .mockResolvedValue({ ...line, status: 'REVERSED' })
  vi.mocked(dataApi.retryMail).mockReset().mockResolvedValue(undefined)
})
describe('Vue resource pages', () => {
  it('renders and searches the order ledger without hiding normal table cells', async () => {
    const wrapper = mountPage(ResourcePage, { user: admin, resource: 'orders' })
    await flushPromises()
    expect(wrapper.find('tbody').text()).toContain(order.order_no)
    expect(wrapper.find('tbody').text()).toContain(order.product_name)
    expect(wrapper.find('tbody .text-success').text()).toBe('80')
    await wrapper.find('input[placeholder="搜索编号、物料、客户或内容"]').setValue('missing')
    expect(wrapper.text()).toContain('没有符合条件的数据')
  })
  it('opens full shipment details and reconciles pending rows', async () => {
    const wrapper = mountPage(ResourcePage, { user: admin, resource: 'shipments' })
    await flushPromises()
    await button(wrapper, '查看').trigger('click')
    expect(document.querySelector('.ant-modal-body')?.textContent).toContain(line.receiver)
    document.querySelector<HTMLButtonElement>('.ant-modal-close')!.click()
    await flushPromises()
    await button(wrapper, '核销').trigger('click')
    await vi.waitFor(() => expect(dataApi.confirmLines).toHaveBeenCalledWith([line.id]))
  })
  it('requires a reason before reversing a reconciled row', async () => {
    vi.mocked(dataApi.shipmentLines).mockResolvedValue([{ ...line, status: 'RECONCILED' }])
    const wrapper = mountPage(ResourcePage, { user: admin, resource: 'shipments' })
    await flushPromises()
    await button(wrapper, '冲销').trigger('click')
    dialogButton('确认冲销').click()
    await flushPromises()
    expect(dataApi.reverseLine).not.toHaveBeenCalled()
    const textarea = document.querySelector<HTMLTextAreaElement>('.ant-modal textarea')!
    textarea.value = '客户取消本次发货'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()
    dialogButton('确认冲销').click()
    await vi.waitFor(() => expect(dataApi.reverseLine).toHaveBeenCalledWith(line.id, '客户取消本次发货'))
  })
  it('retains incoming mail parsing status and retries failed supplier mail', async () => {
    const wrapper = mountPage(ResourcePage, { user: admin, resource: 'inbox' })
    await flushPromises()
    expect(wrapper.find('tbody').text()).toContain(request.subject)
    expect(wrapper.find('tbody').text()).toContain('待确认')
    const tab = wrapper.findAll('[role="tab"]').find((item) => item.text().includes('供应商发件'))!
    await tab.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain(mail.recipient)
    expect(wrapper.text()).toContain('发送失败')
    await button(wrapper, '重新发送').trigger('click')
    await vi.waitFor(() => expect(dataApi.retryMail).toHaveBeenCalledWith(mail.id))
  })
  it('does not request supplier mails or show restricted actions for dealers', async () => {
    const inbox = mountPage(ResourcePage, { user: dealer, resource: 'inbox' })
    const shipments = mountPage(ResourcePage, { user: dealer, resource: 'shipments' })
    await flushPromises()
    expect(dataApi.outboundMails).not.toHaveBeenCalled()
    expect(
      inbox
        .findAll('[role="tab"]')
        .map((item) => item.text())
        .join(''),
    ).not.toContain('供应商发件')
    expect(shipments.findAll('button').map((item) => item.text().replace(/\s/g, ''))).not.toContain('核销')
  })
  it('renders and filters audit events', async () => {
    const wrapper = mountPage(ResourcePage, { user: admin, resource: 'audit' })
    await flushPromises()
    expect(wrapper.find('tbody').text()).toContain('测试核销记录')
    await wrapper.find('input[placeholder="搜索编号、物料、客户或内容"]').setValue('not-found')
    expect(wrapper.text()).toContain('没有符合条件的数据')
  })
})
