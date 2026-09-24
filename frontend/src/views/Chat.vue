<template>
  <div class="chat-container">
    <!-- 移动端：会话列表工具栏（P3：#12） -->
    <div class="mobile-chat-bar">
      <el-button text size="small" aria-label="打开会话列表" @click="sidebarOpen = true">
        <el-icon><Menu /></el-icon><span>会话</span>
      </el-button>
      <el-button type="primary" size="small" @click="handleNewSession">
        <el-icon><Plus /></el-icon> 新建对话
      </el-button>
    </div>

    <!-- 移动端：会话侧栏遮罩（P3：#12） -->
    <div v-if="sidebarOpen" class="sidebar-mask" @click="sidebarOpen = false"></div>

    <!-- 左侧：会话列表 -->
    <div class="chat-sidebar" :class="{ 'sidebar-open': sidebarOpen }">
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
          <!-- 智能推荐问题（P2）：热门 + 未解答共性问题 -->
          <div class="quick-questions">
            <button
              v-for="q in suggestions"
              :key="q"
              class="quick-tag"
              @click="handleQuickQuestion(q)"
            >{{ q }}</button>
            <p v-if="suggestions.length === 0" class="no-sugg">暂无推荐问题，直接输入您的问题吧～</p>
          </div>
        </div>

        <div v-for="(message, index) in chatStore.messages" :key="message.id" class="message-wrapper">
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
                <div
                  v-for="(ref, refIndex) in message.references"
                  :key="refIndex"
                  class="reference-item"
                  @click="openPreview(ref)"
                >
                  <div class="reference-source">{{ ref.source }}</div>
                  <!-- P3：#10 引用片段：问题关键词高亮 -->
                  <div class="reference-content" v-html="renderHighlight(ref, highlightFor(index))"></div>
                  <div class="reference-meta">
                    <el-button
                      size="small"
                      text
                      type="primary"
                      :disabled="!ref.document_id"
                      @click.stop="openPreview(ref)"
                    >
                      {{ ref.document_id ? '📖 预览文档' : '无原文预览' }}
                    </el-button>
                  </div>
                </div>
              </div>

              <!-- 回答反馈 + 提交问题（P0）+ 复制/重新生成（P2） -->
              <div v-if="message.id && message.id !== 'streaming'" class="ai-actions">
                <el-button size="small" text type="info" @click="copyMessage(message.content)">
                  📋 复制
                </el-button>
                <el-button
                  size="small"
                  text
                  type="success"
                  :disabled="chatStore.isLoading"
                  @click="handleRegenerate"
                >
                  🔄 重新生成
                </el-button>
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
        <!-- 快速追问（P2）：刚回答完后一键深入 -->
        <div v-if="showQuickFollow" class="quick-follow">
          <span class="follow-label">💡 还想了解：</span>
          <el-button
            v-for="f in quickFollows"
            :key="f"
            size="small"
            text
            type="primary"
            :disabled="chatStore.isLoading"
            @click="handleQuickQuestion(f)"
          >{{ f }}</el-button>
        </div>

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
        <div v-for="(ref, index) in selectedReferences" :key="index" class="reference-detail" @click="openPreview(ref)">
          <div class="ref-source">{{ ref.source }}</div>
          <div class="ref-content" v-html="renderHighlight(ref, lastUserQuestion)"></div>
          <div class="reference-meta">
            <el-button size="small" text type="primary" :disabled="!ref.document_id" @click.stop="openPreview(ref)">
              {{ ref.document_id ? '📖 预览文档' : '无原文预览' }}
            </el-button>
          </div>
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
  <!-- 📖 文档原文预览（P3：#10） -->
    <el-dialog
      v-model="previewDialog.visible"
      :title="`📖 文档预览：${previewDialog.filename}`"
      class="preview-dialog"
      width="860px"
      top="6vh"
    >
      <div class="preview-toolbar">
        <el-input
          v-model="previewSearch"
          placeholder="在文档中搜索关键词..."
          clearable
          size="small"
          :prefix-icon="Search"
          style="width: 260px"
        />
        <el-tag v-if="previewDialog.loading" type="info" size="small">加载中...</el-tag>
        <el-tag v-if="previewDialog.truncated" type="warning" size="small">内容过长，仅预览前部分</el-tag>
        <el-tag v-if="previewDialog.error" type="danger" size="small">{{ previewDialog.error }}</el-tag>
      </div>
      <div class="preview-body">
        <template v-if="previewDialog.content">
          <p
            v-for="(p, pIndex) in previewFilteredParagraphs"
            :key="pIndex"
            class="preview-para"
            :class="{ 'anchor-para': pIndex === previewAnchorIndex }"
            v-html="previewRenderParagraph(p)"
          ></p>
        </template>
        <el-empty v-else-if="!previewDialog.loading" description="暂无内容" />
      </div>
      <template #footer>
        <span class="preview-footer-tip">“{{ previewDialog.anchorLabel }}” 相关段落已用颜色标记</span>
        <el-button @click="previewDialog.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import { Plus, Delete, ChatDotRound, Document, Promotion, Close, Search, EditPen, Download, Menu } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { submitFeedback, submitQuestionRequest, getMessages, suggestedQuestions as fetchSuggestedQuestions, previewDocument } from '@/api/chat'
import type { ReferenceItem } from '@/api/chat'
import { highlightQuote } from '@/utils/highlight'

const chatStore = useChatStore()

const inputMessage = ref('')
const messagesRef = ref<HTMLElement>()
const selectedReferences = ref<ReferenceItem[]>([])

// ---------- P3：#12 移动端会话侧栏 ----------
const sidebarOpen = ref(false)

// ---------- P3：#10 文档原文预览 ----------
const previewDialog = reactive({
  visible: false,
  loading: false,
  filename: '',
  content: '',
  truncated: false,
  error: '',
  anchorLabel: ''
})
const previewSearch = ref('')
const previewAnchorIndex = ref(-1)

// 全文按行切分为段落
const previewParagraphs = computed(() =>
  previewDialog.content ? previewDialog.content.split(/\n/) : []
)

// 搜索过滤后的段落
const previewFilteredParagraphs = computed(() => {
  const kw = previewSearch.value.trim().toLowerCase()
  if (!kw) return previewParagraphs.value
  return previewParagraphs.value.filter(p => p.toLowerCase().includes(kw))
})

// 段落渲染：未搜索时对引用锚点亮词高亮，搜索时对搜索词高亮
const previewRenderParagraph = (p: string) =>
  highlightQuote(p, previewSearch.value.trim() || previewDialog.anchorLabel)

// 引用卡片渲染：用该条回答对应的用户提问做关键词高亮
const renderHighlight = (refItem: ReferenceItem, question: string) =>
  highlightQuote(refItem.content, question)

// 找某条 AI 回答前面最近的一条用户提问
const highlightFor = (messageIndex: number) => {
  for (let i = messageIndex - 1; i >= 0; i--) {
    if (chatStore.messages[i].role === 'user') return chatStore.messages[i].content
  }
  return ''
}

// 对话框中最后一条用户提问（右侧引用面板高亮用）
const lastUserQuestion = computed(() => {
  const msgs = chatStore.messages
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === 'user') return msgs[i].content
  }
  return ''
})

const locateAnchor = (quote: string) => {
  const head = quote.replace(/\s+/g, '').slice(0, 40)
  const paras = previewParagraphs.value
  if (!head || paras.length === 0) {
    previewAnchorIndex.value = paras.length ? 0 : -1
    return
  }
  const idx = paras.findIndex(p => p.replace(/\s+/g, '').includes(head))
  previewAnchorIndex.value = idx >= 0 ? idx : 0
}

const openPreview = async (refItem: ReferenceItem) => {
  if (!refItem.document_id) {
    ElMessage.info('该引用暂无文档原文可预览')
    return
  }
  previewDialog.visible = true
  previewDialog.loading = true
  previewDialog.filename = refItem.source
  previewDialog.content = ''
  previewDialog.truncated = false
  previewDialog.error = ''
  previewSearch.value = ''
  previewDialog.anchorLabel = refItem.content.replace(/\s+/g, '').slice(0, 12)

  try {
    const data = await previewDocument(refItem.document_id)
    previewDialog.filename = data.filename
    previewDialog.content = data.content
    previewDialog.truncated = data.truncated
    await nextTick()
    locateAnchor(refItem.content)
  } catch (e) {
    previewDialog.error = '预览加载失败，请稍后重试'
    ElMessage.error('文档预览加载失败')
  } finally {
    previewDialog.loading = false
  }
}

// ---------- 推荐问题 / 快速追问 / 复制 / 重新生成（P2） ----------
const suggestions = ref<string[]>([])
const quickFollows = ['再详细解释一下', '举个具体例子', '用更简单的话说明']

const fetchSuggestions = async () => {
  try {
    suggestions.value = await fetchSuggestedQuestions()
  } catch (e) {
    suggestions.value = []
  }
}

const showQuickFollow = computed(() => {
  if (chatStore.isLoading || chatStore.messages.length === 0) return false
  const last = chatStore.messages[chatStore.messages.length - 1]
  return last.role === 'assistant'
})

const copyMessage = async (content: string) => {
  try {
    await navigator.clipboard.writeText(content)
  } catch (e) {
    // 降级复制（旧浏览器 / 非 HTTPS 环境）
    const ta = document.createElement('textarea')
    ta.value = content
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  ElMessage.success('已复制到剪贴板')
}

const handleRegenerate = async () => {
  try {
    await chatStore.regenerateAnswer()
  } catch (e) {
    const detail = (e as any)?.response?.data?.detail
    ElMessage.error(detail || '重新生成失败，请稍后重试')
    // 重新同步消息状态（后端可能已删除部分数据）
    if (chatStore.currentSessionId) {
      chatStore.selectSession(chatStore.currentSessionId)
    }
  }
}

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
  
  // 拉取推荐问题（P2）
  fetchSuggestions()
  
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
  // 移动端：选中会话后收起抽屉（P3：#12）
  sidebarOpen.value = false
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
  background: var(--bg-card);
  border-radius: 8px;
  overflow: hidden;
}

/* 移动端会话工具栏（P3：#12） */
.mobile-chat-bar {
  display: none;
}

/* 移动端会话侧栏遮罩 */
.sidebar-mask {
  display: none;
}

/* 左侧边栏 */
.chat-sidebar {
  width: 260px;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
}

.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header .el-button {
  width: 100%;
}

/* 会话搜索框 */
.search-box {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
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
  color: var(--text-regular);
}

.session-item:hover {
  background: var(--border-color);
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
  color: var(--text-secondary);
}

.session-actions .el-icon:hover {
  color: #409eff;
}

.no-sessions {
  text-align: center;
  color: var(--text-secondary);
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
  color: var(--text-primary);
}

.welcome-message p {
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
}

/* 推荐问题标签（P2） */
.quick-tag {
  border: 1px solid #d9ecff;
  background: #ecf5ff;
  color: #409eff;
  border-radius: 16px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-tag:hover {
  background: #409eff;
  color: #fff;
  border-color: #409eff;
}

.no-sugg {
  color: var(--text-secondary);
  font-size: 13px;
}

/* 快速追问（P2） */
.quick-follow {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 4px 8px;
  flex-wrap: wrap;
}

.follow-label {
  color: var(--text-secondary);
  font-size: 12px;
  margin-right: 4px;
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
  background: var(--bg-bubble-ai);
  color: var(--text-primary);
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
  background: var(--bg-ref);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.references-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.reference-item {
  padding: 8px 10px;
  background: var(--bg-ref-item);
  border-radius: 4px;
  margin-bottom: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s;
  border: 1px solid transparent;
}

.reference-item:hover {
  border-color: #409eff;
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
  color: var(--text-regular);
  font-size: 12px;
  line-height: 1.6;
}

/* 预览文档按钮行（P3：#10） */
.reference-meta {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.reference-meta .el-button {
  padding: 0 4px;
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
  color: var(--text-regular);
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
  background: var(--text-secondary);
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
  border-top: 1px solid var(--border-color);
  background: var(--bg-card);
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
  border-left: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background: var(--bg-ref);
}

.aside-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
}

.aside-header h4 {
  margin: 0;
  color: var(--text-primary);
}

.references-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.reference-detail {
  padding: 12px;
  background: var(--bg-ref-item);
  border-radius: 8px;
  margin-bottom: 12px;
  border: 1px solid var(--border-color);
  cursor: pointer;
  transition: border-color 0.2s;
}

.reference-detail:hover {
  border-color: #409eff;
}

.ref-source {
  font-weight: bold;
  color: #409eff;
  margin-bottom: 8px;
}

.ref-content {
  color: var(--text-regular);
  font-size: 13px;
  line-height: 1.6;
}

/* ---------- P3：#10 文档预览弹窗 ---------- */
.preview-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.preview-body {
  max-height: 60vh;
  overflow-y: auto;
  background: var(--bg-main);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.preview-para {
  margin-bottom: 12px;
  line-height: 1.8;
  color: var(--text-regular);
  white-space: pre-wrap;
  word-break: break-word;
}

.preview-para.anchor-para {
  background: var(--bg-ref-item);
  border-left: 3px solid #409eff;
  padding: 8px 10px;
  border-radius: 4px;
}

.preview-footer-tip {
  color: var(--text-secondary);
  font-size: 12px;
  margin-right: 12px;
}

/* ---------- P3：#12 移动端适配 ---------- */
@media (max-width: 768px) {
  .chat-container {
    height: calc(100vh - 88px);
    flex-direction: column;
  }

  /* 顶部工具栏 */
  .mobile-chat-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-card);
  }

  /* 会话侧栏：抽屉滑出 */
  .chat-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    z-index: 100;
    width: 78vw;
    max-width: 280px;
    transform: translateX(-100%);
    transition: transform 0.25s ease;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.2);
  }

  .chat-sidebar.sidebar-open {
    transform: translateX(0);
  }

  .sidebar-mask {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 99;
  }

  /* 右侧引用面板：全屏抽屉 */
  .chat-aside {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    z-index: 98;
    width: 85vw;
    max-width: 360px;
    box-shadow: -2px 0 12px rgba(0, 0, 0, 0.2);
  }

  .messages-container {
    padding: 12px;
  }

  .message-content {
    max-width: 85%;
  }

  /* 文档预览弹窗窄屏加宽 */
  .preview-dialog {
    width: 94vw !important;
  }
}
</style>
