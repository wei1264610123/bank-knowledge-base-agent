<template>
  <div class="chat-container">
    <!-- 左侧：会话列表 -->
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <el-button type="primary" @click="handleNewSession">
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>
      </div>

      <!-- 会话搜索（P1） -->
      <div class="search-box">
        <el-input
          v-model="searchTerm"
          placeholder="搜索会话..."
          clearable
          size="small"
          :prefix-icon="Search"
        />
      </div>

      <div class="session-list">
        <div
          v-for="session in filteredSessions"
          :key="session.id"
          class="session-item"
          :class="{ active: chatStore.currentSessionId === session.id }"
          @click="handleSelectSession(session.id)"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span class="session-title">{{ session.title }}</span>
          <div class="session-actions" @click.stop>
            <el-icon class="action-btn" title="重命名会话" @click="handleRenameSession(session.id)">
              <EditPen />
            </el-icon>
            <el-icon class="action-btn" title="导出会话" @click="handleExportSession(session.id)">
              <Download />
            </el-icon>
            <el-icon class="delete-btn" title="删除会话" @click="handleDeleteSession(session.id)">
              <Delete />
            </el-icon>
          </div>
        </div>

        <div v-if="filteredSessions.length === 0" class="no-sessions">
          {{ searchTerm ? '没有匹配的会话' : '暂无会话，点击上方按钮开始' }}
        </div>
      </div>
    </div>

    <!-- 中间：对话区域 -->
    <div class="chat-main">
      <div class="messages-container" ref="messagesRef">
        <div v-if="chatStore.messages.length === 0" class="welcome-message">
          <h2>👋 您好，我是小银</h2>
          <p>我是银行智能客服助手，有什么关于银行业务的问题，都可以问我哦！</p>
          <div class="quick-questions">
            <el-button @click="handleQuickQuestion('如何办理信用卡？')">如何办理信用卡？</el-button>
            <el-button @click="handleQuickQuestion('转账限额是多少？')">转账限额是多少？</el-button>
            <el-button @click="handleQuickQuestion('如何修改密码？')">如何修改密码？</el-button>
          </div>
        </div>

        <div v-for="message in chatStore.messages" :key="message.id" class="message-wrapper">
          <!-- 用户消息 -->
          <div v-if="message.role === 'user'" class="message user-message">
            <div class="message-avatar">
              <el-avatar :size="40">U</el-avatar>
            </div>
            <div class="message-content">
              <div class="message-bubble user-bubble">{{ message.content }}</div>
            </div>
          </div>
          
          <!-- AI消息（无内容且无引用时不渲染，避免与"思考中"动画重复） -->
          <div v-else-if="message.content || (message.references && message.references.length > 0)" class="message ai-message">
            <div class="message-avatar">
              <el-avatar :size="40" class="ai-avatar">🤖</el-avatar>
            </div>
            <div class="message-content">
              <div v-if="message.content" class="message-bubble ai-bubble" v-html="formatMessage(message.content)"></div>
              
              <!-- 引用来源 -->
              <div v-if="message.references && message.references.length > 0" class="references">
                <div class="references-title">
                  <el-icon><Document /></el-icon>
                  参考来源
                </div>
                <div v-for="(ref, index) in message.references" :key="index" class="reference-item">
                  <div class="reference-source">{{ ref.source }}</div>
                  <div class="reference-content">{{ ref.content }}...</div>
                </div>
              </div>

              <!-- 回答反馈 + 提交问题（P0） -->
              <div v-if="message.id && message.id !== 'streaming'" class="ai-actions">
                <el-button
                  size="small"
                  text
                  :type="feedbackState[message.id] === 'up' ? 'success' : 'primary'"
                  :disabled="!!feedbackState[message.id]"
                  @click="handleFeedback(message.id, 'up')"
                >
                  {{ feedbackState[message.id] === 'up' ? '✅ 已评价有用' : '👍 有用' }}
                </el-button>
                <el-button
                  size="small"
                  text
                  :type="feedbackState[message.id] === 'down' ? 'danger' : 'primary'"
                  :disabled="!!feedbackState[message.id]"
                  @click="handleFeedback(message.id, 'down')"
                >
                  {{ feedbackState[message.id] === 'down' ? '⛔ 已评价没用' : '👎 没用' }}
                </el-button>
                <el-button size="small" text type="warning" @click="openQuestionDialog">
                  💡 没找到答案？提交问题
                </el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 加载中（无流式内容时显示） -->
        <div v-if="chatStore.isLoading && !chatStore.streamingContent" class="message ai-message">
          <div class="message-avatar">
            <el-avatar :size="40" class="ai-avatar">🤖</el-avatar>
          </div>
          <div class="message-content">
            <div class="message-bubble ai-bubble typing">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-container">
        <div class="input-wrapper">
          <el-input
            v-model="inputMessage"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            placeholder="输入您的问题... (Enter发送, Shift+Enter换行)"
            :disabled="chatStore.isLoading"
            @keydown.enter.exact.prevent="handleSend"
          />
          <el-button
            type="primary"
            :icon="Promotion"
            :disabled="!inputMessage.trim() || chatStore.isLoading"
            circle
            @click="handleSend"
          />
        </div>
      </div>
    </div>

    <!-- 右侧：引用详情（可选显示） -->
    <div v-if="selectedReferences.length > 0" class="chat-aside">
      <div class="aside-header">
        <h4>📚 引用详情</h4>
        <el-button text @click="selectedReferences = []">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <div class="references-list">
        <div v-for="(ref, index) in selectedReferences" :key="index" class="reference-detail">
          <div class="ref-source">{{ ref.source }}</div>
          <div class="ref-content">{{ ref.content }}</div>
        </div>
      </div>
    </div>

    <!-- 👎 反馈原因弹窗 -->
    <el-dialog v-model="feedbackDialog.visible" title="👎 反馈原因" width="440px">
      <p class="dialog-tip">这个问题回答得不太满意？请告诉我们原因（选填）：</p>
      <el-radio-group v-model="feedbackDialog.reason">
        <el-radio label="not_helpful">没帮到忙</el-radio>
        <el-radio label="wrong">信息有误</el-radio>
        <el-radio label="unclear">回答不清晰</el-radio>
        <el-radio label="incomplete">回答不完整</el-radio>
        <el-radio label="other">其他</el-radio>
      </el-radio-group>
      <el-input
        v-model="feedbackDialog.comment"
        type="textarea"
        :rows="3"
        maxlength="500"
        show-word-limit
        placeholder="补充意见（选填）"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="feedbackDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitDownFeedback">提交</el-button>
      </template>
    </el-dialog>

    <!-- 💡 提交问题弹窗 -->
    <el-dialog v-model="questionDialog.visible" title="💡 没找到答案？" width="440px">
      <p class="dialog-tip">别急，告诉我们您想问的问题，我们会尽快补充知识库：</p>
      <el-input
        v-model="questionDialog.content"
        type="textarea"
        :rows="3"
        maxlength="500"
        show-word-limit
        placeholder="请输入您的问题..."
      />
      <template #footer>
        <el-button @click="questionDialog.visible = false">取消</el-button>
        <el-button type="primary" :disabled="!questionDialog.content.trim()" @click="submitQuestion">
          提交问题
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { Plus, Delete, ChatDotRound, Document, Promotion, Close, Search, EditPen, Download } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { submitFeedback, submitQuestionRequest, getMessages } from '@/api/chat'
import type { ReferenceItem } from '@/api/chat'

const chatStore = useChatStore()

const inputMessage = ref('')
const messagesRef = ref<HTMLElement>()
const selectedReferences = ref<ReferenceItem[]>([])

// ---------- 会话搜索 / 重命名 / 导出（P1） ----------
const searchTerm = ref('')
const filteredSessions = computed(() => {
  const kw = searchTerm.value.trim().toLowerCase()
  if (!kw) return chatStore.sessions
  return chatStore.sessions.filter(s => s.title.toLowerCase().includes(kw))
})

const handleRenameSession = async (sessionId: string) => {
  const session = chatStore.sessions.find(s => s.id === sessionId)
  try {
    const { value } = await ElMessageBox.prompt('请输入新的会话名称', '重命名会话', {
      inputValue: session?.title || '',
      inputPlaceholder: '会话名称',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValidator: (v: string) => (v && v.trim() ? true : '名称不能为空')
    } as any)
    await chatStore.renameSessionAction(sessionId, value.trim())
    ElMessage.success('会话已重命名')
  } catch (e) {
    // 用户取消，忽略
  }
}

const handleExportSession = async (sessionId: string) => {
  const session = chatStore.sessions.find(s => s.id === sessionId)
  try {
    const msgs = await getMessages(sessionId)
    const lines: string[] = [
      `【对话导出】${session?.title || '会话'}`,
      `导出时间：${new Date().toLocaleString('zh-CN')}`,
      '='.repeat(40)
    ]
    msgs.forEach(m => {
      const who = m.role === 'user' ? '👤 用户' : '🤖 小银'
      lines.push(`[${who}] ${new Date(m.created_at).toLocaleString('zh-CN')}`)
      lines.push(m.content)
      if (m.references && m.references.length > 0) {
        lines.push('引用来源: ' + m.references.map(r => r.source).join('、'))
      }
      lines.push('')
    })
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${session?.title || '会话'}.txt`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('会话已导出')
  } catch (e) {
    ElMessage.error('导出失败，请稍后重试')
  }
}

// ---------- 回答反馈（P0） ----------
// 记录消息 ID -> 评价（'up' / 'down'），仅前端会话内生效
const feedbackState = reactive<Record<string, string>>({})

// 👎 反馈弹窗状态
const feedbackDialog = reactive({
  visible: false,
  messageId: '',
  reason: '',
  comment: ''
})

// 💡 提交问题弹窗状态
const questionDialog = reactive({
  visible: false,
  content: ''
})

const handleFeedback = (messageId: string, rating: 'up' | 'down') => {
  if (feedbackState[messageId]) {
    ElMessage.info('您已经评价过这条回答了')
    return
  }
  if (rating === 'down') {
    feedbackDialog.messageId = messageId
    feedbackDialog.reason = ''
    feedbackDialog.comment = ''
    feedbackDialog.visible = true
    return
  }
  submitFeedback({ message_id: messageId, rating: 'up' })
    .then(() => {
      feedbackState[messageId] = 'up'
      ElMessage.success('感谢您的反馈！')
    })
    .catch(() => ElMessage.error('反馈提交失败，请稍后重试'))
}

const submitDownFeedback = async () => {
  const { messageId, reason, comment } = feedbackDialog
  if (!messageId) return
  try {
    await submitFeedback({
      message_id: messageId,
      rating: 'down',
      reason: reason || undefined,
      comment: comment.trim() || undefined
    })
    feedbackState[messageId] = 'down'
    feedbackDialog.visible = false
    ElMessage.success('感谢您的反馈，我们会参考改进！')
  } catch (e) {
    ElMessage.error('反馈提交失败，请稍后重试')
  }
}

// ---------- 未解答问题收集（P0） ----------
const openQuestionDialog = () => {
  questionDialog.content = ''
  questionDialog.visible = true
}

const submitQuestion = async () => {
  const content = questionDialog.content.trim()
  if (!content) return
  try {
    await submitQuestionRequest(content)
    questionDialog.visible = false
    ElMessage.success('问题已提交，我们会尽快补充知识库！')
  } catch (e) {
    ElMessage.error('提交失败，请稍后重试')
  }
}

onMounted(async () => {
  await chatStore.fetchSessions()
  
  // 如果有会话，选择第一个
  if (chatStore.sessions.length > 0) {
    await chatStore.selectSession(chatStore.sessions[0].id)
  } else {
    // 无会话时兜底清空消息区，防止残留上个用户的数据
    chatStore.resetState()
  }
})

// 监听消息变化，自动滚动到底部
watch(
  () => chatStore.messages.length,
  () => {
    nextTick(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      }
    })
  }
)

// 监听流式内容变化
watch(
  () => chatStore.streamingContent,
  () => {
    nextTick(() => {
      if (messagesRef.value) {
        messagesRef.value.scrollTop = messagesRef.value.scrollHeight
      }
    })
  }
)

const handleNewSession = async () => {
  await chatStore.createNewSession()
}

const handleSelectSession = async (sessionId: string) => {
  await chatStore.selectSession(sessionId)
}

const handleDeleteSession = async (sessionId: string) => {
  await chatStore.deleteSession(sessionId)
}

const handleSend = async () => {
  const message = inputMessage.value.trim()
  if (!message || chatStore.isLoading) return
  
  inputMessage.value = ''
  await chatStore.sendMessage(message)
}

const handleQuickQuestion = (question: string) => {
  inputMessage.value = question
  handleSend()
}

const formatMessage = (content: string) => {
  // 简单的Markdown格式化
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\[(.*?)\]/g, '<span class="reference-tag">[$1]</span>')
}
</script>

<style scoped>
.chat-container {
  display: flex;
  height: calc(100vh - 120px);
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

/* 左侧边栏 */
.chat-sidebar {
  width: 260px;
  border-right: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid #e6e6e6;
}

.sidebar-header .el-button {
  width: 100%;
}

/* 会话搜索框 */
.search-box {
  padding: 10px 12px;
  border-bottom: 1px solid #e6e6e6;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  padding: 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.session-item:hover {
  background: #e6e6e6;
}

.session-item.active {
  background: #409eff;
  color: #fff;
}

.session-title {
  flex: 1;
  margin: 0 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 会话操作区（重命名/导出/删除，hover 显示） */
.session-actions {
  display: none;
  align-items: center;
  gap: 6px;
}

.session-item:hover .session-actions {
  display: flex;
}

.session-item.active .session-actions .el-icon {
  color: #fff;
}

.session-item:not(.active) .session-actions .el-icon {
  color: #909399;
}

.session-actions .el-icon:hover {
  color: #409eff;
}

.no-sessions {
  text-align: center;
  color: #909399;
  padding: 40px 20px;
}

/* 中间对话区 */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.welcome-message {
  text-align: center;
  padding: 60px 20px;
}

.welcome-message h2 {
  margin-bottom: 12px;
  color: #303133;
}

.welcome-message p {
  color: #909399;
  margin-bottom: 24px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}

.message-wrapper {
  margin-bottom: 24px;
}

.message {
  display: flex;
  gap: 12px;
}

.user-message {
  flex-direction: row-reverse;
}

.message-content {
  max-width: 70%;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-break: break-word;
}

.user-bubble {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai-bubble {
  background: #f5f7fa;
  color: #303133;
  border-bottom-left-radius: 4px;
}

.ai-avatar {
  background: #67c23a;
  font-size: 20px;
}

/* 引用来源 */
.references {
  margin-top: 12px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e6e6e6;
}

.references-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.reference-item {
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 13px;
}

.reference-item:last-child {
  margin-bottom: 0;
}

.reference-source {
  font-weight: bold;
  color: #409eff;
  margin-bottom: 4px;
}

.reference-content {
  color: #606266;
  font-size: 12px;
}

/* 回答反馈操作区 */
.ai-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.ai-actions .el-button {
  padding: 4px 8px;
}

/* 弹窗提示文字 */
.dialog-tip {
  color: #606266;
  margin-bottom: 12px;
  line-height: 1.6;
}

/* 打字动画 */
.typing {
  display: flex;
  gap: 4px;
  padding: 16px 20px;
}

.dot {
  width: 8px;
  height: 8px;
  background: #909399;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 输入区域 */
.input-container {
  padding: 16px 20px;
  border-top: 1px solid #e6e6e6;
  background: #fff;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.input-wrapper :deep(.el-textarea__inner) {
  resize: none;
  border-radius: 20px;
  padding: 10px 16px;
}

/* 右侧引用面板 */
.chat-aside {
  width: 300px;
  border-left: 1px solid #e6e6e6;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}

.aside-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e6e6e6;
}

.aside-header h4 {
  margin: 0;
}

.references-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.reference-detail {
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
  border: 1px solid #e6e6e6;
}

.ref-source {
  font-weight: bold;
  color: #409eff;
  margin-bottom: 8px;
}

.ref-content {
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}
</style>
