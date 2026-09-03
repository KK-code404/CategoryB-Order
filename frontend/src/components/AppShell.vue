<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import {
  App,
  Avatar as AAvatar,
  Button as AButton,
  Layout as ALayout,
  LayoutSider as ALayoutSider,
  LayoutHeader as ALayoutHeader,
  LayoutContent as ALayoutContent,
  Menu as AMenu,
  MenuItem as AMenuItem,
  Space as ASpace,
  TypographyText as ATypographyText,
} from 'ant-design-vue'
import {
  AuditOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  LogoutOutlined,
  MailOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SendOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import { authApi } from '../api/client'
import type { User } from '../types'
import DashboardPage from '../pages/DashboardPage.vue'
const ResourcePage = defineAsyncComponent(() => import('../pages/ResourcePage.vue'))
const AdminSettingsPage = defineAsyncComponent(() => import('../pages/AdminSettingsPage.vue'))
// CHANGE [2026-09-03 10:38 +08:00] [WH400]: 驾驶舱按需加载，避免增加原工作台首屏成本。
const OperationsPage = defineAsyncComponent(() => import('../pages/OperationsPage.vue'))

const props = defineProps<{ user: User }>()
const emit = defineEmits<{ logout: [] }>()
const { message } = App.useApp()
const active = ref('dashboard')
const collapsed = ref(false)
const mobile = ref(false)
const loggingOut = ref(false)
const roleLabel = computed(() => ({ ADMIN: '系统管理员', SALES: '零件销售', DEALER: '代理商' })[props.user.role])
const items = computed(() => [
  { key: 'dashboard', icon: DashboardOutlined, label: '工作台' },
  // CHANGE [2026-09-03 10:38 +08:00] [WH400]: 为规则风险与只读模拟提供统一入口，各角色沿用服务端数据范围。
  { key: 'operations', icon: DashboardOutlined, label: '业务驾驶舱' },
  { key: 'orders', icon: DatabaseOutlined, label: '订单台账' },
  { key: 'shipments', icon: SendOutlined, label: '发货申请' },
  { key: 'inbox', icon: MailOutlined, label: '邮件收件箱' },
  { key: 'audit', icon: AuditOutlined, label: '操作日志' },
  ...(props.user.role === 'ADMIN' ? [{ key: 'settings', icon: SettingOutlined, label: '后台配置' }] : []),
])
function navigate(key: string) {
  if (key === 'settings' && props.user.role !== 'ADMIN') return
  active.value = key
  if (mobile.value) collapsed.value = true
}
function breakpoint(broken: boolean) {
  mobile.value = broken
  collapsed.value = broken
}
async function logout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await authApi.logout()
    message.success('已安全退出')
    emit('logout')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '退出失败，请重试')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <a-layout class="app-shell">
    <button v-if="mobile && !collapsed" class="sider-backdrop" aria-label="关闭导航菜单" @click="collapsed = true" />
    <a-layout-sider
      v-model:collapsed="collapsed"
      class="app-sider"
      :class="{ 'is-mobile': mobile }"
      :width="216"
      :collapsed-width="mobile ? 0 : 72"
      collapsible
      :trigger="null"
      breakpoint="lg"
      @breakpoint="breakpoint"
    >
      <div class="sider-brand" aria-label="油品订单平台">
        <span class="header-drop" aria-hidden="true">滴</span><strong v-if="!collapsed">油品订单平台</strong>
      </div>
      <a-menu mode="inline" :selected-keys="[active]">
        <a-menu-item v-for="item in items" :key="item.key" @click="navigate(item.key)"
          ><template #icon><component :is="item.icon" /></template>{{ item.label }}</a-menu-item
        >
      </a-menu>
      <a-button
        class="sider-toggle"
        type="text"
        :aria-label="collapsed ? '展开导航菜单' : '收起导航菜单'"
        @click="collapsed = !collapsed"
        ><template #icon><MenuUnfoldOutlined v-if="collapsed" /><MenuFoldOutlined v-else /></template
        ><template v-if="!collapsed">收起菜单</template></a-button
      >
    </a-layout-sider>
    <a-layout class="app-main">
      <a-layout-header class="app-header">
        <a-button
          type="text"
          class="mobile-menu-button"
          :aria-label="collapsed ? '展开导航菜单' : '收起导航菜单'"
          @click="collapsed = !collapsed"
          ><template #icon><MenuUnfoldOutlined v-if="collapsed" /><MenuFoldOutlined v-else /></template
        ></a-button>
        <a-space :size="12" class="header-profile"
          ><a-avatar size="small">{{ user.display_name.slice(0, 1) }}</a-avatar
          ><span class="header-identity"
            ><a-typography-text class="header-user">{{ user.display_name }}</a-typography-text
            ><a-typography-text class="header-role">{{ roleLabel }}</a-typography-text></span
          ><a-button type="text" class="header-action" aria-label="退出登录" :loading="loggingOut" @click="logout"
            ><template #icon><LogoutOutlined /></template></a-button
        ></a-space>
      </a-layout-header>
      <a-layout-content class="app-content">
        <DashboardPage v-if="active === 'dashboard'" :user="user" @navigate="navigate" />
        <!-- CHANGE [2026-09-03 10:38 +08:00] [WH400]: 风险处理跳回既有业务流程，不在驾驶舱旁路核销权限。 -->
        <OperationsPage v-else-if="active === 'operations'" :user="user" @navigate="navigate" />
        <AdminSettingsPage v-else-if="active === 'settings' && user.role === 'ADMIN'" :user="user" />
        <ResourcePage v-else :key="active" :resource="active" :user="user" />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>
