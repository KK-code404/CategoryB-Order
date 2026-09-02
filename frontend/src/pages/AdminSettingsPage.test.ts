import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { Select } from 'ant-design-vue'
import { dataApi } from '../api/client'
import { admin, config, dealer } from '../test/fixtures'
import { button, dialogButton, fillDialog, mountPage } from '../test/helpers'
import AdminSettingsPage from './AdminSettingsPage.vue'

vi.mock('../api/client', () => ({
  dataApi: {
    adminConfig: vi.fn(),
    createDealer: vi.fn(),
    createSupplier: vi.fn(),
    createMaterial: vi.fn(),
    createUser: vi.fn(),
    updateDealer: vi.fn(),
    updateSupplier: vi.fn(),
    updateMaterial: vi.fn(),
    updateUser: vi.fn(),
    previewOrderImport: vi.fn(),
    commitOrderImport: vi.fn(),
  },
}))
beforeEach(() => {
  vi.mocked(dataApi.adminConfig).mockReset().mockResolvedValue(structuredClone(config))
  for (const method of [
    'createDealer',
    'createSupplier',
    'createMaterial',
    'createUser',
    'updateDealer',
    'updateSupplier',
    'updateMaterial',
    'updateUser',
  ] as const)
    vi.mocked(dataApi[method]).mockReset().mockResolvedValue({ id: 5 })
  vi.mocked(dataApi.previewOrderImport)
    .mockReset()
    .mockResolvedValue({ token: 'preview-test', valid_count: 1, error_count: 0, errors: [] })
  vi.mocked(dataApi.commitOrderImport).mockReset().mockResolvedValue({ imported: 1 })
})
describe('Vue admin settings', () => {
  it('lists all four master-data tables and keeps template downloads', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    expect(wrapper.findAll('[role="tab"]').map((item) => item.text())).toEqual([
      '物料映射（1）',
      '代理商（1）',
      '供应商（1）',
      '用户（2）',
    ])
    expect(wrapper.find('tbody').text()).toContain(config.materials[0].material_no)
    expect(wrapper.findAll('a[download]').map((item) => item.attributes('href'))).toEqual([
      '/templates/销售订单导入模板.xlsx',
      '/templates/发货申请标准模板.xlsx',
    ])
  })
  it.each([
    ['新增代理商', 'createDealer'],
    ['新增供应商', 'createSupplier'],
  ] as const)('validates and saves %s with only its own fields', async (label, method) => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    await button(wrapper, label).trigger('click')
    fillDialog('编码', 'NEW01')
    fillDialog('名称', '新增测试公司')
    fillDialog('邮箱', 'new@example.com')
    await flushPromises()
    dialogButton('保存').click()
    await vi.waitFor(() =>
      expect(dataApi[method]).toHaveBeenCalledWith({ code: 'NEW01', name: '新增测试公司', email: 'new@example.com' }),
    )
  })
  it('creates material mappings with the selected active supplier', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    await button(wrapper, '新增物料映射').trigger('click')
    fillDialog('物料号', 'NEW-MAT')
    fillDialog('零件号', 'NEW-PART')
    fillDialog('品名', '新测试品名')
    fillDialog('品牌编码', 'BR02')
    wrapper.findComponent(Select).vm.$emit('update:value', 'SP01')
    await flushPromises()
    dialogButton('保存').click()
    await vi.waitFor(() =>
      expect(dataApi.createMaterial).toHaveBeenCalledWith({
        material_no: 'NEW-MAT',
        part_no: 'NEW-PART',
        product_name: '新测试品名',
        brand_code: 'BR02',
        supplier_code: 'SP01',
      }),
    )
  })
  it('requires a bound dealer when creating a dealer account', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    await button(wrapper, '新增用户').trigger('click')
    fillDialog('姓名', '新测试用户')
    fillDialog('账号或邮箱', 'new-test')
    fillDialog('初始密码', 'test-only-password')
    wrapper.findComponent(Select).vm.$emit('update:value', 'DEALER')
    await flushPromises()
    dialogButton('保存').click()
    await flushPromises()
    expect(dataApi.createUser).not.toHaveBeenCalled()
    wrapper.findAllComponents(Select)[1].vm.$emit('update:value', 'DL01')
    await flushPromises()
    dialogButton('保存').click()
    await vi.waitFor(() =>
      expect(dataApi.createUser).toHaveBeenCalledWith({
        display_name: '新测试用户',
        email: 'new-test',
        password: 'test-only-password',
        role: 'DEALER',
        dealer_code: 'DL01',
      }),
    )
  })
  it.each([
    ['代理商', 'updateDealer'],
    ['供应商', 'updateSupplier'],
    ['物料映射', 'updateMaterial'],
  ] as const)('edits %s through its matching endpoint', async (tab, method) => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    await wrapper
      .findAll('[role="tab"]')
      .find((item) => item.text().startsWith(tab))!
      .trigger('click')
    await flushPromises()
    const edit = wrapper.findAll('.ant-tabs-tabpane-active button').find((item) => item.text().includes('编辑'))!
    await edit.trigger('click')
    await flushPromises()
    dialogButton('保存').click()
    await vi.waitFor(() => expect(dataApi[method]).toHaveBeenCalledWith(1, expect.any(Object)))
  })
  it('leaves an existing password unchanged when its reset field is blank', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    await wrapper
      .findAll('[role="tab"]')
      .find((item) => item.text().startsWith('用户'))!
      .trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.ant-tabs-tabpane-active button')
      .find((item) => item.text().includes('编辑'))!
      .trigger('click')
    fillDialog('姓名', '修改后的销售')
    await flushPromises()
    dialogButton('保存').click()
    await vi.waitFor(() =>
      expect(dataApi.updateUser).toHaveBeenCalledWith(3, {
        display_name: '修改后的销售',
        email: 'sales-test',
        role: 'SALES',
        dealer_code: null,
        active: true,
      }),
    )
  })
  it('prevents the current administrator from disabling or demoting themselves', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    await wrapper
      .findAll('[role="tab"]')
      .find((item) => item.text().startsWith('用户'))!
      .trigger('click')
    await flushPromises()
    const row = wrapper.findAll('.ant-tabs-tabpane-active tbody tr').find((item) => item.text().includes(admin.email))!
    await row.find('button').trigger('click')
    expect(document.querySelector('.ant-modal .ant-select-disabled')).not.toBeNull()
    expect(document.querySelector('.ant-modal .ant-switch-disabled')).not.toBeNull()
  })
  it('previews a selected Excel file before committing its import token', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    const upload = wrapper.find('input[type="file"]')
    Object.defineProperty(upload.element, 'files', {
      value: [new File(['test workbook'], 'orders.xlsx')],
      configurable: true,
    })
    await upload.trigger('change')
    await vi.waitFor(() => expect(dataApi.previewOrderImport).toHaveBeenCalled())
    await flushPromises()
    expect(dataApi.commitOrderImport).not.toHaveBeenCalled()
    expect(document.querySelector('.ant-modal-body')?.textContent).toContain('有效数据：1')
    dialogButton('确认导入').click()
    await vi.waitFor(() => expect(dataApi.commitOrderImport).toHaveBeenCalledWith('preview-test'))
  })
  it('blocks import confirmation for files with invalid rows', async () => {
    vi.mocked(dataApi.previewOrderImport).mockResolvedValue({
      token: 'invalid-test',
      valid_count: 0,
      error_count: 1,
      errors: [{ row: 2, message: '未知物料号' }],
    })
    const wrapper = mountPage(AdminSettingsPage, { user: admin })
    await flushPromises()
    const upload = wrapper.find('input[type="file"]')
    Object.defineProperty(upload.element, 'files', {
      value: [new File(['invalid'], 'orders.xlsx')],
      configurable: true,
    })
    await upload.trigger('change')
    await vi.waitFor(() => expect(document.body.textContent).toContain('未知物料号'))
    expect(dialogButton('确认导入').disabled).toBe(true)
    expect(dataApi.commitOrderImport).not.toHaveBeenCalled()
  })
  it('does not load privileged config for a dealer account', async () => {
    const wrapper = mountPage(AdminSettingsPage, { user: dealer })
    await flushPromises()
    expect(wrapper.text()).toContain('仅管理员可维护后台配置')
    expect(dataApi.adminConfig).not.toHaveBeenCalled()
  })
})
