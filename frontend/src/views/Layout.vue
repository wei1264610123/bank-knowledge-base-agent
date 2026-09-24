<template>
  <el-container class="layout-container">
    <!-- 侧边栏（桌面端显示） -->
    <el-aside v-if="!isMobile" width="200px" class="layout-aside">
      <div class="logo">
        <h3>🏦 银行问答系统</h3>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="aside-menu"
      >
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>

        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>

        <el-menu-item v-if="authStore.isAdmin" index="/admin/knowledge">
          <el-icon><Document /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>

        <el-menu-item v-if="authStore.isAdmin" index="/admin/users">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="layout-header">
        <div class="header-left">
          <!-- 移动端：菜单按钮（P3） -->
          <el-button v-if="isMobile" text class="menu-btn" aria-label="打开菜单" @click="menuOpen = true">
            <el-icon :size="20"><Menu /></el-icon>
          </el-button>
          <span class="page-title">{{ pageTitle }}</span>
        </div>

        <div class="header-right">
          <!-- 深色模式切换（P3：#12） -->
          <el-tooltip :content="themeStore.isDark ? '切换到浅色模式' : '切换到深色模式'" placement="bottom">
            <el-button text circle class="theme-btn" aria-label="切换主题" @click="themeStore.toggle()">
              <el-icon :size="18"><Moon v-if="!themeStore.isDark" /><Sunny v-else /></el-icon>
            </el-button>
          </el-tooltip>

          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" class="user-avatar">
                {{ authStore.user?.username?.charAt(0).toUpperCase() }}
              </el-avatar>
              <span class="username">{{ authStore.user?.username }}</span>
              <el-tag v-if="authStore.isAdmin" size="small" type="danger">管理员</el-tag>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人中心
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 移动端菜单抽屉（P3） -->
    <el-drawer v-model="menuOpen" direction="ltr" size="200px" :with-header="false" class="mobile-menu-drawer">
      <div class="logo">
        <h3>🏦 银行问答系统</h3>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="aside-menu"
        @select="menuOpen = false"
      >
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>智能问答</span>
        </el-menu-item>

        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>

        <el-menu-item v-if="authStore.isAdmin" index="/admin/knowledge">
          <el-icon><Document /></el-icon>
          <span>知识库管理</span>
        </el-menu-item>

        <el-menu-item v-if="authStore.isAdmin" index="/admin/users">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChatDotRound, User, Document, UserFilled, ArrowDown, SwitchButton,
  Moon, Sunny, Menu
} from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const themeStore = useThemeStore()

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/chat': '智能问答',
    '/profile': '个人中心',
    '/admin/knowledge': '知识库管理',
    '/admin/users': '用户管理'
  }
  return titles[route.path] || '银行问答系统'
})

const handleCommand = (command: string) => {
  if (command === 'profile') {
    router.push('/profile')
  } else if (command === 'logout') {
    ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(async () => {
      await authStore.logout()
      router.push('/login')
    }).catch(() => {})
  }
}

// ---------- 移动端适配（P3：#12） ----------
const isMobile = ref(false)
const menuOpen = ref(false)
let mql: MediaQueryList | null = null

const onMqlChange = (e: MediaQueryList | MediaQueryListEvent) => {
  isMobile.value = e.matches
}

onMounted(() => {
  mql = window.matchMedia('(max-width: 768px)')
  onMqlChange(mql)
  mql.addEventListener('change', onMqlChange)
})

onBeforeUnmount(() => {
  mql?.removeEventListener('change', onMqlChange)
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-aside {
  background-color: var(--bg-sidebar, #304156);
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid var(--border-color);
}

.logo h3 {
  color: #fff;
  margin: 0;
  font-size: 18px;
}

.aside-menu {
  border-right: none;
  background-color: var(--bg-sidebar, #304156);
}

.aside-menu .el-menu-item {
  color: #bfcbd9;
}

.aside-menu .el-menu-item:hover {
  background-color: #263445;
}

.aside-menu .el-menu-item.is-active {
  background-color: #409eff;
  color: #fff;
}

.layout-header {
  background-color: var(--bg-card);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.menu-btn {
  color: var(--text-regular);
}

.header-left .page-title {
  font-size: 18px;
  font-weight: bold;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.theme-btn {
  color: var(--text-regular);
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  gap: 8px;
}

.user-avatar {
  background-color: #409eff;
  color: #fff;
}

.username {
  color: var(--text-regular);
  font-size: 14px;
}

.layout-main {
  background-color: var(--bg-main);
  padding: 20px;
}

/* 移动端菜单抽屉 */
.mobile-menu-drawer {
  --el-drawer-bg-color: var(--bg-sidebar, #304156);
}

.mobile-menu-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.mobile-menu-drawer .aside-menu {
  background-color: transparent;
}

@media (max-width: 768px) {
  .layout-header {
    padding: 0 12px;
  }

  .layout-main {
    padding: 12px;
  }

  /* 移动端隐藏用户名文字，节省空间 */
  .username {
    max-width: 80px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .page-title {
    font-size: 16px;
  }
}
</style>