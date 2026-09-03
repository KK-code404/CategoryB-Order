<script setup lang="ts">
// CHANGE [2026-09-03 13:03 +08:00] [WH400]: 登录页按参考图改为开放式左表单布局，并增加只记账号和帮助指引，保留现有认证接口。
import { h, onMounted, reactive, ref, watch } from 'vue'
import {
  App,
  Button as AButton,
  Checkbox as ACheckbox,
  ConfigProvider as AConfigProvider,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
} from 'ant-design-vue'
import { EyeInvisibleOutlined, EyeOutlined, LockOutlined, UserOutlined } from '@ant-design/icons-vue'
import { authApi } from '../api/client'
import type { User } from '../types'

const emit = defineEmits<{ success: [user: User] }>()
const { message, modal } = App.useApp()
const form = reactive({ email: '', password: '' })
const submitting = ref(false)
const rememberAccount = ref(false)
const accountKey = 'categoryb.remembered-account'
// CHANGE [2026-09-03 13:03 +08:00] [WH400]: 显隐密码使用可聚焦按钮，让键盘用户也能触发组件原有切换逻辑。
function visibilityIcon(visible: boolean) {
  return h('button', { type: 'button', 'aria-label': visible ? '隐藏密码' : '显示密码', class: 'login-password-toggle' }, [h(visible ? EyeOutlined : EyeInvisibleOutlined)])
}
onMounted(() => {
  try {
    const saved = localStorage.getItem(accountKey)
    if (saved) { form.email = saved; rememberAccount.value = true }
  } catch { /* Browser storage may be disabled; authentication remains available. */ }
})
watch(rememberAccount, (remember) => {
  if (!remember) {
    try { localStorage.removeItem(accountKey) }
    catch { message.warning('浏览器禁止访问存储，请在浏览器设置中清除已保存的账号') }
  }
})
// CHANGE [2026-09-03 13:03 +08:00] [WH400]: 仅在成功登录且用户勾选时记住账号，绝不保存密码或延长会话。
async function login() {
  if (submitting.value) return
  submitting.value = true
  try {
    const user = await authApi.login(form.email.trim(), form.password)
    try {
      if (rememberAccount.value) localStorage.setItem(accountKey, form.email.trim())
      else localStorage.removeItem(accountKey)
    } catch { message.warning('登录成功，但浏览器无法保存账号偏好') }
    emit('success', user)
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登录失败，请检查账号和密码')
  } finally {
    submitting.value = false
  }
}
// CHANGE [2026-09-03 13:03 +08:00] [WH400]: 以真实管理员办理流程替代尚未接入的注册、短信登录和密码找回假链接。
function showHelp(kind: 'reset' | 'account' | 'help') {
  const content = {
    reset: ['忘记密码', '请联系平台管理员核验身份并重置密码。平台暂未开放自助密码找回，请勿通过邮件或聊天发送原密码。'],
    account: ['申请开通账号', '请向平台管理员提供公司名称、业务邮箱及所需角色。管理员审核后为您开通账号；代理商账号需绑定所属代理商。'],
    help: ['登录帮助', '请使用管理员分配的账号或邮箱登录。记住账号仅保存此设备上的账号，不保存密码；公共设备请勿勾选。若账号停用或无法登录，请联系平台管理员。'],
  }[kind]
  modal.info({ title: content[0], content: content[1], okText: '我知道了' })
}
</script>

<template>
  <a-config-provider :theme="{ token: { colorPrimary: '#0052d9', borderRadius: 4 } }">
  <main class="login-page">
    <div class="login-shell">
      <!-- CHANGE [2026-09-03 13:03 +08:00] [WH400]: 品牌与表单使用真实文字，插画仅作为不参与交互的背景资源。 -->
      <!-- CHANGE [2026-09-03 15:40 +08:00] [WH400]: 按用户要求恢复上一版品牌和科技配图，移除新增业务说明。 -->
      <header class="login-brand"><span class="login-brand-mark" aria-hidden="true">K</span><span>KK Hub</span></header>
      <!-- CHANGE [2026-09-03 16:32 +08:00] [WH400]: 使用新参考图提取的油品运输背景，表单保持真实可交互元素。 -->
      <section class="login-visual" aria-label="平台介绍">
        <img
          class="login-visual-image"
          src="/images/login-oil-logistics-20260903.png"
          alt="白色油罐车、透明油桶与蓝色数据面板组成的油品协同场景"
          fetchpriority="high"
        />
      </section>
      <section class="login-panel" aria-labelledby="login-title">
        <!-- CHANGE [2026-09-03 16:32 +08:00] [WH400]: 按要求取消“登录到”，只保留平台名称与原有简短辅助说明。 -->
        <div class="login-heading">
          <h1 id="login-title">油品订单协同平台</h1>
          <p>使用您的授权账号，开始高效协同</p>
        </div>
        <a-form class="login-form" :model="form" layout="vertical" size="large" :required-mark="false" @finish="login">
          <a-form-item name="email" :rules="[{ required: true, whitespace: true, message: '请输入账号' }]">
            <a-input
              v-model:value="form.email"
              placeholder="请输入账号或邮箱"
              aria-label="账号"
              autocomplete="username"
              autofocus
              ><template #prefix><UserOutlined /></template
            ></a-input>
          </a-form-item>
          <a-form-item name="password" :rules="[{ required: true, message: '请输入密码' }]">
            <a-input-password
              v-model:value="form.password"
              placeholder="请输入密码"
              aria-label="密码"
              autocomplete="current-password"
              :icon-render="visibilityIcon"
              ><template #prefix><LockOutlined /></template
            ></a-input-password>
          </a-form-item>
          <!-- CHANGE [2026-09-03 13:03 +08:00] [WH400]: 账号偏好为明确勾选，辅助入口可操作且不会触发提交。 -->
          <div class="login-options"><a-checkbox v-model:checked="rememberAccount">记住账号</a-checkbox><button type="button" class="login-text-button" @click="showHelp('reset')">忘记密码</button></div>
          <a-button class="login-submit" type="primary" html-type="submit" :loading="submitting">登录</a-button>
        </a-form>
        <nav class="login-help-links" aria-label="登录支持"><button type="button" class="login-text-button" @click="showHelp('account')">申请开通账号</button><span aria-hidden="true">|</span><button type="button" class="login-text-button" @click="showHelp('help')">登录帮助</button></nav>
      </section>
      <!-- CHANGE [2026-09-03 15:40 +08:00] [WH400]: 页脚恢复上一版简短署名。 -->
      <p class="login-copyright">© 2026 KK Hub · 油品订单协同平台</p>
    </div>
  </main>
  </a-config-provider>
</template>
