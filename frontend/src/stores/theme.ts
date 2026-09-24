/**
 * 主题管理（P3：#12 深色模式）
 * 亮/暗主题切换，持久化到 localStorage，跟随系统偏好作为默认
 */
import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  const apply = (dark: boolean) => {
    isDark.value = dark
    document.documentElement.classList.toggle('dark', dark)
  }

  // 初始化：<手动选择> → <系统偏好> → 亮色
  const init = () => {
    const saved = localStorage.getItem('theme')
    if (saved === 'dark') {
      apply(true)
    } else if (saved === 'light') {
      apply(false)
    } else {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
      apply(prefersDark)
    }
  }

  const setDark = (dark: boolean) => {
    apply(dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }

  const toggle = () => setDark(!isDark.value)

  return { isDark, init, setDark, toggle }
})