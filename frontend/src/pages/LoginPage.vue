<script setup lang="ts">
import { reactive, ref } from 'vue'
import {
  App,
  Button as AButton,
  Form as AForm,
  FormItem as AFormItem,
  Input as AInput,
  InputPassword as AInputPassword,
} from 'ant-design-vue'
import { LockOutlined, SafetyCertificateOutlined, UserOutlined } from '@ant-design/icons-vue'
import { authApi } from '../api/client'
import type { User } from '../types'

const emit = defineEmits<{ success: [user: User] }>()
const { message } = App.useApp()
const form = reactive({ email: '', password: '' })
const submitting = ref(false)
async function login() {
  if (submitting.value) return
  submitting.value = true
  try {
    emit('success', await authApi.login(form.email, form.password))
  } catch (error) {
    message.error(error instanceof Error ? error.message : '登录失败，请检查账号和密码')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <main class="login-page">
    <div class="login-shell">
      <section class="login-visual" aria-label="平台介绍">
        <img
          class="login-visual-image"
          src="/images/login-operations-3d.webp?v=20260901-hd"
          alt="仓库、配送车辆、订单单据与业务节点组成的协同场景"
        />
      </section>
      <section class="login-panel" aria-labelledby="login-title">
        <span class="login-brand-mark" aria-hidden="true">K</span>
        <div class="login-heading">
          <h1 id="login-title">登录</h1>
          <p>欢迎登录油品订单协同平台</p>
        </div>
        <a-form class="login-form" :model="form" layout="vertical" size="large" :required-mark="false" @finish="login">
          <a-form-item name="email" :rules="[{ required: true, message: '请输入账号' }]">
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
              ><template #prefix><LockOutlined /></template
            ></a-input-password>
          </a-form-item>
          <a-button class="login-submit" type="primary" html-type="submit" :loading="submitting">立即登录</a-button>
        </a-form>
        <div class="login-security-note">
          <SafetyCertificateOutlined aria-hidden="true" /><span>仅限已授权账号访问，连接信息已加密保护</span>
        </div>
      </section>
    </div>
    <p class="login-copyright">© 2026 KK Hub · 油品订单协同平台</p>
  </main>
</template>
