/**
 * 管理员API
 */
import request from './request'
import type { UserInfo } from './auth'

export interface Stats {
  total_users: number
  total_documents: number
  completed_documents: number
  total_sessions: number
  total_messages: number
}

// 获取用户列表
export const getUsers = (page: number = 1, pageSize: number = 20): Promise<UserInfo[]> => {
  return request.get('/admin/users', { params: { page, page_size: pageSize } })
}

// 获取用户详情
export const getUser = (userId: string): Promise<UserInfo> => {
  return request.get(`/admin/users/${userId}`)
}

// 更新用户状态
export const updateUserStatus = (userId: string, isActive: boolean) => {
  return request.put(`/admin/users/${userId}/status`, null, {
    params: { is_active: isActive }
  })
}

// 获取统计数据
export const getStats = (): Promise<Stats> => {
  return request.get('/admin/stats')
}
