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

// ---------- 未解答问题管理（P0） ----------

export interface QuestionRequest {
  id: string
  user_id: string
  username?: string
  content: string
  status: 'open' | 'solved' | 'ignored'
  note?: string
  created_at: string
}

// 获取未解答问题列表
export const getUnansweredRequests = (status?: string, page: number = 1, pageSize: number = 20): Promise<QuestionRequest[]> => {
  return request.get('/admin/unanswered-requests', { params: { status, page, page_size: pageSize } })
}

// 处理未解答问题（标记状态 + 备注）
export const updateUnansweredRequest = (requestId: string, payload: { status?: string; note?: string }) => {
  return request.patch(`/admin/unanswered-requests/${requestId}`, payload)
}

// ---------- 审计日志（P0） ----------

export interface AuditLog {
  id: string
  user_id?: string
  username?: string
  action: string
  target_type?: string
  target_id?: string
  detail?: string
  ip?: string
  created_at: string
}

export const ACTION_LABELS: Record<string, string> = {
  login: '登录',
  login_failed: '登录失败',
  register: '注册',
  upload_document: '上传文档',
  delete_document: '删除文档',
  reprocess_document: '重新处理文档',
  delete_category: '删除分类',
  delete_session: '删除会话',
  submit_feedback: '提交反馈',
  submit_question: '提交问题',
  handle_question: '处理问题',
  update_user_status: '用户状态变更'
}

// 获取审计日志
export const getAuditLogs = (action?: string, page: number = 1, pageSize: number = 50): Promise<AuditLog[]> => {
  return request.get('/admin/audit-logs', { params: { action, page, page_size: pageSize } })
}
