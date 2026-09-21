<template>
  <div class="users-container">
    <el-card class="users-card">
      <template #header>
        <div class="card-header">
          <h3>👥 用户管理</h3>
        </div>
      </template>

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
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { User, Document, ChatDotRound, ChatLineRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getUsers, updateUserStatus, getStats } from '@/api/admin'
import type { UserInfo } from '@/api/auth'
import type { Stats } from '@/api/admin'

const users = ref<UserInfo[]>([])
const loading = ref(false)
const stats = reactive<Stats>({
  total_users: 0,
  total_documents: 0,
  completed_documents: 0,
  total_sessions: 0,
  total_messages: 0
})

onMounted(async () => {
  await fetchUsers()
  await fetchStats()
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
</style>
