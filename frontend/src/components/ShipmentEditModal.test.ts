import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { dataApi } from '../api/client'
import { line } from '../test/fixtures'
import { dialogButton, mountPage } from '../test/helpers'
import ShipmentEditModal from './ShipmentEditModal.vue'

vi.mock('../api/client', () => ({ dataApi: { updateLine: vi.fn() } }))
beforeEach(() => {
  vi.mocked(dataApi.updateLine).mockReset().mockResolvedValue(line)
})
describe('shared Vue shipment editor', () => {
  it('does not submit twice while form validation and saving are pending', async () => {
    let resolve!: (value: typeof line) => void
    vi.mocked(dataApi.updateLine).mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    mountPage(ShipmentEditModal, { open: true, line })
    await flushPromises()
    dialogButton('保存并重新匹配').click()
    dialogButton('保存并重新匹配').click()
    await vi.waitFor(() => expect(dataApi.updateLine).toHaveBeenCalledTimes(1))
    resolve(line)
    await flushPromises()
    expect(dataApi.updateLine).toHaveBeenCalledTimes(1)
  })
  it('prefills editable fields and preserves the serialized date and decimal quantity', async () => {
    const wrapper = mountPage(ShipmentEditModal, { open: true, line: { ...line, quantity: 1.25 } })
    await flushPromises()
    expect([...document.querySelectorAll<HTMLInputElement>('.ant-modal input')].map((input) => input.value)).toContain(
      line.order_no,
    )
    dialogButton('保存并重新匹配').click()
    await vi.waitFor(() =>
      expect(dataApi.updateLine).toHaveBeenCalledWith(line.id, {
        order_no: line.order_no,
        material_no: line.material_no,
        quantity: 1.25,
        requested_ship_date: line.requested_ship_date,
        receiver: line.receiver,
        phone: line.phone,
        address: line.address,
        remark: line.remark,
      }),
    )
    await flushPromises()
    expect(wrapper.findComponent(ShipmentEditModal).emitted('saved')).toHaveLength(1)
    expect(wrapper.findComponent(ShipmentEditModal).emitted('update:open')).toEqual([[false]])
  })
  it('keeps the dialog and data available when the server rejects the edit', async () => {
    vi.mocked(dataApi.updateLine).mockRejectedValue(new Error('申请已核销，不能修改'))
    const wrapper = mountPage(ShipmentEditModal, { open: true, line })
    await flushPromises()
    dialogButton('保存并重新匹配').click()
    await vi.waitFor(() => expect(document.body.textContent).toContain('申请已核销，不能修改'))
    expect(wrapper.findComponent(ShipmentEditModal).emitted('saved')).toBeUndefined()
    expect(wrapper.findComponent(ShipmentEditModal).emitted('update:open')).toBeUndefined()
  })
})
