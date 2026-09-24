<template>
  <div class="users-container">
    <el-card class="users-card">
      <template #header>
        <div class="card-header">
          <h3>🛠️ 管理后台</h3>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- Tab 1: 用户管理 -->
        <el-tab-pane label="👥 用户管理" name="users">
          <!-- 统计卡片 -->
          <el-row :gutter="20" class="stats-row">
            <el-col :span="6">
              <el-statistic title="总用户数" :value="stats.total_users">
                <template #prefix>
                  <el-icon style="color: #409eff"><User /></el-icon>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="总文档数" :value="stats.total_documents">
                <template #prefix>
                  <el-icon style="color: #67c23a"><Document /></el-icon>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="总会话数" :value="stats.total_sessions">
                <template #prefix>
                  <el-icon style="color: #e6a23c"><ChatDotRound /></el-icon>
                </template>
              </el-statistic>
            </el-col>
            <el-col :span="6">
              <el-statistic title="总消息数" :value="stats.total_messages">
                <template #prefix>
                  <el-icon style="color: #f56c6c"><ChatLineRound /></el-icon>
                </template>
              </el-statistic>
            </el-col>
          </el-row>

          <el-divider />

          <!-- 用户列表 -->
          <el-table
            :data="users"
            v-loading="loading"
            stripe
            style="width: 100%"
          >
            <el-table-column prop="username" label="用户名" width="150" />
            <el-table-column prop="email" label="邮箱" min-width="200" />
            <el-table-column prop="role" label="角色" width="100">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
                  {{ row.role === 'admin' ? '管理员' : '普通用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="100">
              <template #default="{ row }">
                <el-switch
                  v-model="row.is_active"
                  :disabled="row.username === 'admin'"
                  @change="handleStatusChange(row)"
                />
              </template>
            </el-table-column>
            <el-table-column label="注册时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="warning" text @click="openResetPassword(row)">重置密码</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- Tab 2: 数据面板 -->
        <el-tab-pane label="📊 数据面板" name="dashboard">
          <!-- 报表导出（P2）：时间范围 + 三种 CSV -->
          <div class="toolbar">
            <el-date-picker
              v-model="exportRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              style="width: 260px"
              clearable
            />
            <el-button size="small" type="primary" :loading="exporting" @click="handleExport('questions')">
              导出问答明细
            </el-button>
            <el-button size="small" type="primary" plain :loading="exporting" @click="handleExport('audit')">
              导出审计日志
            </el-button>
            <el-button size="small" type="primary" plain :loading="exporting" @click="handleExport('feedback')">
              导出反馈记录
            </el-button>
            <span class="toolbar-tip">CSV 文件可直接用 Excel 打开，方便银行留档（不选日期=全部）</span>
          </div>

          <el-row :gutter="20" class="stats-row">
            <el-col :span="4">
              <el-statistic title="今日问答" :value="dashboard.today_questions" />
            </el-col>
            <el-col :span="4">
              <el-statistic title="近7天问答" :value="dashboard.week_questions" />
            </el-col>
            <el-col :span="4">
              <el-statistic title="总问答量" :value="dashboard.total_questions" />
            </el-col>
            <el-col :span="4">
              <el-statistic title="👍 好评" :value="dashboard.up_feedback">
                <template #prefix><el-icon style="color: #67c23a"><ChatLineRound /></el-icon></template>
              </el-statistic>
            </el-col>
            <el-col :span="4">
              <el-statistic title="👎 差评" :value="dashboard.down_feedback">
                <template #prefix><el-icon style="color: #f56c6c"><ChatLineRound /></el-icon></template>
              </el-statistic>
            </el-col>
          </el-row>

          <el-divider />

          <el-row :gutter="20">
            <el-col :span="12">
              <div class="panel-title">🔥 热门问题 TOP10（用户最爱问）</div>
              <el-table :data="dashboard.hot_questions" v-loading="dashboardLoading" stripe size="small" :max-height="320">
                <el-table-column type="index" label="#" width="50" />
                <el-table-column prop="content" label="问题" min-width="200" />
                <el-table-column prop="count" label="次数" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag size="small" type="primary">{{ row.count }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="dashboard.hot_questions.length === 0" description="暂无问答数据" :image-size="60" />
            </el-col>
            <el-col :span="12">
              <div class="panel-title">📋 待补知识榜单（用户找不到答案）</div>
              <el-table :data="dashboard.unanswered_top" v-loading="dashboardLoading" stripe size="small" :max-height="320">
                <el-table-column type="index" label="#" width="50" />
                <el-table-column prop="content" label="问题" min-width="200" />
                <el-table-column prop="count" label="次数" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag size="small" type="warning">{{ row.count }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <el-empty v-if="dashboard.unanswered_top.length === 0" description="暂无未命中问题" :image-size="60" />
            </el-col>
          </el-row>
        </el-tab-pane>

        <!-- Tab 2: 待补知识（未解答问题收集） -->
        <el-tab-pane label="📋 待补知识" name="questions">
          <div class="toolbar">
            <el-radio-group v-model="questionFilter" size="small" @change="fetchQuestions">
              <el-radio-button label="">全部</el-radio-button>
              <el-radio-button label="open">待处理</el-radio-button>
              <el-radio-button label="solved">已解决</el-radio-button>
              <el-radio-button label="ignored">已忽略</el-radio-button>
            </el-radio-group>
            <span class="toolbar-tip">用户没找到答案时提交的问题，处理后补充到知识库形成闭环</span>
          </div>

          <el-table :data="questions" v-loading="questionsLoading" stripe style="width: 100%">
            <el-table-column label="用户" width="120">
              <template #default="{ row }">{{ row.username || '—' }}</template>
            </el-table-column>
            <el-table-column prop="content" label="问题内容" min-width="260" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="提交时间" width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="备注" min-width="150">
              <template #default="{ row }">{{ row.note || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'open'"
                  size="small"
                  type="primary"
                  text
                  @click="openHandleDialog(row)"
                >处理</el-button>
                <span v-else style="color: #c0c4cc; font-size: 12px">已处理</span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="questions.length === 0" description="暂无未解答问题" />
        </el-tab-pane>

        <!-- Tab 3: 审计日志 -->
        <el-tab-pane label="📜 审计日志" name="audit">
          <div class="toolbar">
            <el-select
              v-model="auditActionFilter"
              placeholder="全部操作"
              clearable
              size="small"
              style="width: 200px"
              @change="fetchAuditLogs"
            >
              <el-option v-for="(label, action) in ACTION_LABELS" :key="action" :label="label" :value="action" />
            </el-select>
            <el-button size="small" @click="fetchAuditLogs">刷新</el-button>
            <span class="toolbar-tip">登录 / 上传 / 删除 / 反馈等敏感操作留痕（银行合规要求）</span>
          </div>

          <el-table :data="auditLogs" v-loading="auditLoading" stripe style="width: 100%">
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="用户" width="120">
              <template #default="{ row }">{{ row.username || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="130">
              <template #default="{ row }">{{ ACTION_LABELS[row.action] || row.action }}</template>
            </el-table-column>
            <el-table-column label="详情" min-width="200">
              <template #default="{ row }">{{ row.detail || '—' }}</template>
            </el-table-column>
            <el-table-column prop="ip" label="IP" width="140">
              <template #default="{ row }">{{ row.ip || '—' }}</template>
            </el-table-column>
          </el-table>
          <el-empty v-if="auditLogs.length === 0" description="暂无审计日志" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 处理未解答问题弹窗 -->
    <el-dialog v-model="handleDialog.visible" title="处理问题" width="460px">
      <p class="dialog-tip">{{ handleDialog.content }}</p>
      <el-radio-group v-model="handleDialog.status">
        <el-radio label="solved">已解决（已补充知识库）</el-radio>
        <el-radio label="ignored">忽略（重复 / 无价值）</el-radio>
      </el-radio-group>
      <el-input
        v-model="handleDialog.note"
        type="textarea"
        :rows="3"
        maxlength="500"
        show-word-limit
        placeholder="处理备注（选填，如补充的文档名）"
        style="margin-top: 12px"
      />
      <template #footer>
        <el-button @click="handleDialog.visible = false">取消</el-button>
        <el-button type="primary" :disabled="!handleDialog.status" @click="submitHandleDialog">确认处理</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码弹窗（忘记密码场景） -->
    <el-dialog v-model="resetDialog.visible" title="重置密码" width="420px">
      <p class="dialog-tip">
        为用户 <b>{{ resetDialog.username }}</b> 设置新密码，重置后请告知其新密码。
      </p>
      <el-input
        v-model="resetDialog.newPassword"
        type="password"
        show-password
        placeholder="输入新密码（至少6个字符）"
        maxlength="100"
      />
      <template #footer>
        <el-button @click="resetDialog.visible = false">取消</el-button>
        <el-button type="primary" :disabled="resetDialog.newPassword.length < 6" @click="submitResetPassword">
          确认重置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { User, Document, ChatDotRound, ChatLineRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getUsers,
  updateUserStatus,
  getStats,
  getUnansweredRequests,
  updateUnansweredRequest,
  getAuditLogs,
  resetUserPassword,
  getDashboard,
  exportCsv,
  EXPORT_FILE_NAMES,
  ACTION_LABELS
} from '@/api/admin'
import type { UserInfo } from '@/api/auth'
import type { Stats, QuestionRequest, AuditLog, DashboardData, ExportType } from '@/api/admin'

const activeTab = ref('users')

// ---------- 用户管理 ----------
const users = ref<UserInfo[]>([])
const loading = ref(false)
const stats = reactive<Stats>({
  total_users: 0,
  total_documents: 0,
  completed_documents: 0,
  total_sessions: 0,
  total_messages: 0
})

// ---------- 重置密码（忘记密码场景） ----------
const resetDialog = reactive({
  visible: false,
  userId: '',
  username: '',
  newPassword: ''
})

const openResetPassword = (row: UserInfo) => {
  resetDialog.userId = row.id
  resetDialog.username = row.username
  resetDialog.newPassword = ''
  resetDialog.visible = true
}

const submitResetPassword = async () => {
  try {
    await resetUserPassword(resetDialog.userId, resetDialog.newPassword)
    resetDialog.visible = false
    ElMessage.success(`已为用户 ${resetDialog.username} 重置密码`)
  } catch (error) {
    ElMessage.error('重置失败，请稍后重试')
  }
}

// ---------- 数据面板 ----------
const dashboardLoading = ref(false)
const dashboard = reactive<DashboardData>({
  today_questions: 0,
  week_questions: 0,
  total_questions: 0,
  up_feedback: 0,
  down_feedback: 0,
  hot_questions: [],
  unanswered_top: []
})

const fetchDashboard = async () => {
  dashboardLoading.value = true
  try {
    const data = await getDashboard()
    Object.assign(dashboard, data)
  } finally {
    dashboardLoading.value = false
  }
}

// ---------- 报表导出（P2） ----------
const exportRange = ref<[string, string] | null>(null)
const exporting = ref(false)

const handleExport = async (type: ExportType) => {
  exporting.value = true
  try {
    const start = exportRange.value?.[0] || undefined
    const end = exportRange.value?.[1] || undefined
    const blob = await exportCsv(type, start, end)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = EXPORT_FILE_NAMES[type]
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出：${EXPORT_FILE_NAMES[type]}`)
  } catch (e) {
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

// ---------- 待补知识 ----------
const questions = ref<QuestionRequest[]>([])
const questionsLoading = ref(false)
const questionFilter = ref('')
const handleDialog = reactive({
  visible: false,
  id: '',
  content: '',
  status: '',
  note: ''
})

// ---------- 审计日志 ----------
const auditLogs = ref<AuditLog[]>([])
const auditLoading = ref(false)
const auditActionFilter = ref('')

onMounted(async () => {
  await fetchUsers()
  await fetchStats()
  await fetchQuestions()
  await fetchAuditLogs()
  await fetchDashboard()
})

const fetchUsers = async () => {
  loading.value = true
  try {
    users.value = await getUsers()
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  const data = await getStats()
  Object.assign(stats, data)
}

const handleStatusChange = async (user: UserInfo) => {
  try {
    await updateUserStatus(user.id, user.is_active)
    ElMessage.success(`用户已${user.is_active ? '启用' : '禁用'}`)
  } catch (error) {
    user.is_active = !user.is_active
  }
}

// ---------- 待补知识逻辑 ----------
const fetchQuestions = async () => {
  questionsLoading.value = true
  try {
    questions.value = await getUnansweredRequests(questionFilter.value || undefined)
  } finally {
    questionsLoading.value = false
  }
}

const statusLabel = (status: string) => {
  return { open: '待处理', solved: '已解决', ignored: '已忽略' }[status] || status
}

const statusTagType = (status: string) => {
  return { open: 'warning', solved: 'success', ignored: 'info' }[status] || 'info'
}

const openHandleDialog = (row: QuestionRequest) => {
  handleDialog.id = row.id
  handleDialog.content = row.content
  handleDialog.status = ''
  handleDialog.note = ''
  handleDialog.visible = true
}

const submitHandleDialog = async () => {
  try {
    await updateUnansweredRequest(handleDialog.id, {
      status: handleDialog.status,
      note: handleDialog.note.trim() || undefined
    })
    handleDialog.visible = false
    ElMessage.success('处理成功')
    await fetchQuestions()
  } catch (error) {
    ElMessage.error('处理失败，请稍后重试')
  }
}

// ---------- 审计日志逻辑 ----------
const fetchAuditLogs = async () => {
  auditLoading.value = true
  try {
    auditLogs.value = await getAuditLogs(auditActionFilter.value || undefined)
  } finally {
    auditLoading.value = false
  }
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<style scoped>
.users-container {
  height: 100%;
}

.users-card {
  height: 100%;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
}

.stats-row {
  margin-bottom: 20px;
}

.stats-row .el-col {
  text-align: center;
}

/* 工具栏 + 提示 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.toolbar-tip {
  color: #909399;
  font-size: 12px;
}

.dialog-tip {
  color: #606266;
  margin-bottom: 12px;
  line-height: 1.6;
  word-break: break-all;
}
</style>