/**
 * 认证API
 */
import request from './request'

export interface LoginParams {
  username: string
  password: string
}

export interface RegisterParams {
  username: string
  email: string
  password: string
}

export interface UserInfo {
  id: string
  username: string
  email: string
  role: string
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

// 用户登录
export const login = (params: LoginParams): Promise<TokenResponse> => {
  const formData = new FormData()
  formData.append('username', params.username)
  formData.append('password', params.password)
  return request.post('/auth/login', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 用户注册
export const register = (params: RegisterParams): Promise<UserInfo> => {
  return request.post('/auth/register', params)
}

// 获取当前用户信息
export const getUserInfo = (): Promise<UserInfo> => {
  return request.get('/auth/me')
}

// 修改密码
export const changePassword = (params: { old_password: string; new_password: string }) => {
  return request.put('/auth/password', params)
}
