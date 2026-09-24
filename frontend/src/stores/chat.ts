/**
 * 聊天状态管理
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  getSessions,
  createSession as createSessionApi,
  deleteSession as deleteSessionApi,
  renameSession as renameSessionApi,
  getMessages,
  sendMessageStream,
  clearLastExchange
} from '@/api/chat'
import type { ChatSession, ChatMessage, ReferenceItem } from '@/api/chat'

export const useChatStore = defineStore('chat', () => {
  // 状态
  const sessions = ref<ChatSession[]>([])
  const currentSessionId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const streamingContent = ref('')
  const streamingReferences = ref<ReferenceItem[]>([])

  // 获取会话列表
  const fetchSessions = async () => {
    sessions.value = await getSessions()
  }

  // 创建新会话
  const createNewSession = async (title?: string) => {
    const session = await createSessionApi(title)
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    messages.value = []
    return session
  }

  // 选择会话
  const selectSession = async (sessionId: string) => {
    currentSessionId.value = sessionId
    messages.value = await getMessages(sessionId)
  }

  // 删除会话
  const deleteSession = async (sessionId: string) => {
    await deleteSessionApi(sessionId)
    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (currentSessionId.value === sessionId) {
      currentSessionId.value = sessions.value[0]?.id || null
      if (currentSessionId.value) {
        await selectSession(currentSessionId.value)
      } else {
        messages.value = []
      }
    }
  }

  // 重命名会话（P1）
  const renameSessionAction = async (sessionId: string, title: string) => {
    const updated = await renameSessionApi(sessionId, title)
    const idx = sessions.value.findIndex(s => s.id === sessionId)
    if (idx !== -1) {
      sessions.value[idx].title = updated.title
    }
  }

  // 重置状态（登出/切换账号时调用）
  const resetState = () => {
    sessions.value = []
    currentSessionId.value = null
    messages.value = []
    isLoading.value = false
    streamingContent.value = ''
    streamingReferences.value = []
  }

  // 发送消息
  const sendMessage = async (content: string) => {
    if (!currentSessionId.value) {
      await createNewSession()
    }

    // 添加用户消息到列表
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      references: [],
      created_at: new Date().toISOString()
    }
    messages.value.push(userMessage)

    // 开始流式响应
    isLoading.value = true
    streamingContent.value = ''
    streamingReferences.value = []

    // 添加空的AI消息
    const aiMessageIndex = messages.value.length
    messages.value.push({
      id: 'streaming',
      role: 'assistant',
      content: '',
      references: [],
      created_at: new Date().toISOString()
    })

    await sendMessageStream(
      currentSessionId.value,
      content,
      // onChunk
      (chunk) => {
        streamingContent.value += chunk
        messages.value[aiMessageIndex].content = streamingContent.value
      },
      // onReferences
      (references) => {
        streamingReferences.value = references
        messages.value[aiMessageIndex].references = references
      },
      // onDone：携带后端返回的 AI 消息 ID（供反馈按钮使用）
      (messageId) => {
        isLoading.value = false
        if (messageId) {
          messages.value[aiMessageIndex].id = messageId
        } else {
          messages.value[aiMessageIndex].id = Date.now().toString()
        }
        // 刷新会话列表以更新标题和时间
        fetchSessions()
      },
      // onError
      (error) => {
        isLoading.value = false
        messages.value[aiMessageIndex].content = `抱歉，发生错误: ${error}`
      }
    )

    // 兜底：若流式连接异常中断未触发任何回调，确保停止加载状态
    if (isLoading.value) {
      isLoading.value = false
      if (!messages.value[aiMessageIndex].content) {
        messages.value[aiMessageIndex].content = '抱歉，连接中断，请重试。'
      }
    }
  }

  // 重新生成最后一条回答（P2）：后端删除末尾问答对后，重新提交原问题
  const regenerateAnswer = async () => {
    if (!currentSessionId.value || isLoading.value) return
    const lastUser = [...messages.value].reverse().find(m => m.role === 'user')
    if (!lastUser) return
    // 后端会先删除末尾"问题+回答"，已评价的回答会拒绝（409）
    await clearLastExchange(currentSessionId.value)
    // 重新拉取消息列表（与后端一致），再重新提问
    messages.value = await getMessages(currentSessionId.value)
    await sendMessage(lastUser.content)
  }

  return {
    sessions,
    currentSessionId,
    messages,
    isLoading,
    streamingContent,
    streamingReferences,
    fetchSessions,
    createNewSession,
    selectSession,
    deleteSession,
    renameSessionAction,
    regenerateAnswer,
    sendMessage,
    resetState
  }
})
