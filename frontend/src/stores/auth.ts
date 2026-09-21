/**
 * 认证状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, getUserInfo } from '@/api/auth'
import type { UserInfo } from '@/api/auth'

// 从localStorage恢复用户信息
function getSavedUser(): UserInfo | null {
  const saved = localStorage.getItem('user')
  if (!saved) return null
  try {
    return JSON.parse(saved)
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  // 状态 - 从localStorage恢复
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserInfo | null>(getSavedUser())

  // 计算属性
  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  // 登录
  const login = async (username: string, password: string) => {
    const response = await loginApi({ username, password })
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    return response
  }

  // 注册
  const register = async (username: string, email: string, password: string) => {
    return await registerApi({ username, email, password })
  }

  // 获取用户信息
  const fetchUserInfo = async () => {
    if (!token.value) return
    try {
      user.value = await getUserInfo()
      localStorage.setItem('user', JSON.stringify(user.value))
    } catch (error) {
      logout()
    }
  }

  // 登出
  const logout = async () => {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    // 清空聊天状态，防止切换账号后看到上个用户的数据
    const { useChatStore } = await import('@/stores/chat')
    useChatStore().resetState()
  }

  return {
    token,
    user,
    isAuthenticated,
    isAdmin,
    login,
    register,
    fetchUserInfo,
    logout
  }
})