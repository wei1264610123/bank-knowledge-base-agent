<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const authStore = useAuthStore()
const themeStore = useThemeStore()

onMounted(() => {
  // 页面刷新时重新获取用户信息
  authStore.fetchUserInfo()
  // 应用主题（深色模式，P3）
  themeStore.init()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif;
  background: var(--bg-main);
  color: var(--text-regular);
}

#app {
  width: 100%;
  height: 100vh;
}

/* ---------- P3：#12 深色模式 全局颜色变量 ---------- */
:root {
  --bg-main: #f5f7fa;        /* 页面主背景 */
  --bg-card: #ffffff;        /* 卡片 / 内容背景 */
  --bg-panel: #f5f7fa;       /* 侧栏 / 面板背景 */
  --bg-sidebar: #304156;     /* 左侧深色菜单 */
  --border-color: #e6e6e6;   /* 分隔线 / 边框 */
  --text-primary: #303133;   /* 主文字 */
  --text-regular: #606266;   /* 常规文字 */
  --text-secondary: #909399; /* 次要文字 */
  --bg-bubble-ai: #f5f7fa;   /* AI 气泡背景 */
  --bg-ref: #fafafa;         /* 引用区背景 */
  --bg-ref-item: #ffffff;    /* 引用条目背景 */
  --hl-bg: #fde68a;          /* 关键词高亮底色 */
  --hl-color: #1f2937;       /* 关键词高亮文字色 */
}

html.dark {
  --bg-main: #0f1419;
  --bg-card: #1d2129;
  --bg-panel: #171b22;
  --bg-sidebar: #16181d;
  --border-color: #323844;
  --text-primary: #e5eaf3;
  --text-regular: #cfd3dc;
  --text-secondary: #8a919f;
  --bg-bubble-ai: #23272f;
  --bg-ref: #171b22;
  --bg-ref-item: #1d2129;
  --hl-bg: #7f5df0;
  --hl-color: #ffffff;
}

/* 关键词高亮通用样式（引用片段） */
mark.kw-hl {
  background: var(--hl-bg);
  color: var(--hl-color);
  border-radius: 2px;
  padding: 0 1px;
}
</style>