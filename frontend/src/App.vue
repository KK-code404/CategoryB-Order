<script setup lang="ts">
import { defineAsyncComponent, onMounted, onUnmounted, ref } from 'vue'
import { App as AApp, ConfigProvider as AConfigProvider, Spin as ASpin } from 'ant-design-vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import { authApi } from './api/client'
import type { User } from './types'
import { theme } from './theme'
import LoginPage from './pages/LoginPage.vue'
const AppShell = defineAsyncComponent(() => import('./components/AppShell.vue'))

dayjs.locale('zh-cn')
const user = ref<User | null>(null)
const loading = ref(true)
let disposed = false
let sessionVersion = 0
function expireSession() {
  sessionVersion++
  user.value = null
}
onMounted(async () => {
  window.addEventListener('auth-expired', expireSession)
  const version = sessionVersion
  try {
    const restored = await authApi.me()
    if (!disposed && version === sessionVersion) user.value = restored
  } catch {
    if (!disposed) user.value = null
  } finally {
    if (!disposed) loading.value = false
  }
})
onUnmounted(() => {
  disposed = true
  window.removeEventListener('auth-expired', expireSession)
})
</script>

<template>
  <a-config-provider :locale="zhCN" :theme="theme">
    <a-app>
      <div v-if="loading" class="app-loading" aria-label="正在载入核销平台"><a-spin size="large" /></div>
      <AppShell v-else-if="user" :user="user" @logout="expireSession" />
      <LoginPage v-else @success="user = $event" />
    </a-app>
  </a-config-provider>
</template>
