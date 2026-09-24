/**
 * 聊天API
 */
import request from './request'

export interface ChatSession {
  id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export interface ReferenceItem {
  content: string
  source: string
  page?: string
  score?: number
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  references: ReferenceItem[]
  created_at: string
}

// 获取会话列表
export const getSessions = (): Promise<ChatSession[]> => {
  return request.get('/chat/sessions')
}

// 创建新会话
export const createSession = (title?: string): Promise<ChatSession> => {
  return request.post('/chat/sessions', { title })
}

// 删除会话
export const deleteSession = (sessionId: string) => {
  return request.delete(`/chat/sessions/${sessionId}`)
}

// 获取消息历史
export const getMessages = (sessionId: string): Promise<ChatMessage[]> => {
  return request.get(`/chat/sessions/${sessionId}/messages`)
}

// 发送消息（流式）
export const sendMessageStream = async (
  sessionId: string,
  message: string,
  onChunk: (content: string) => void,
  onReferences: (references: ReferenceItem[]) => void,
  onDone: (messageId: string) => void,
  onError: (error: string) => void
) => {
  const authStore = (await import('@/stores/auth')).useAuthStore()
  
  try {
    const response = await fetch('/api/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authStore.token}`
      },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        stream: true
      })
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('无法读取响应')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            
            if (data.type === 'content') {
              onChunk(data.content)
            } else if (data.type === 'references') {
              onReferences(data.references)
            } else if (data.type === 'done') {
              // done 事件携带后端保存的 AI 消息 ID，供反馈功能使用
              onDone(data.message_id || '')
            } else if (data.type === 'error') {
              onError(data.message)
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  } catch (error) {
    onError(error instanceof Error ? error.message : '发送消息失败')
  }
}

// ---------- 回答反馈（P0） ----------

export interface FeedbackPayload {
  message_id: string
  rating: 'up' | 'down'
  reason?: string
  comment?: string
}

// 提交回答反馈（👍/👎）
export const submitFeedback = (payload: FeedbackPayload) => {
  return request.post('/chat/feedback', payload)
}

// ---------- 未解答问题收集（P0） ----------

// 提交"没找到答案"的问题
export const submitQuestionRequest = (content: string) => {
  return request.post('/chat/unanswered-requests', { content })
}
