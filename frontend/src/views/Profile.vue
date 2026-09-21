<template>
  <div class="profile-container">
    <el-card class="profile-card">
      <template #header>
        <div class="card-header">
          <h3>个人中心</h3>
        </div>
      </template>

      <div class="profile-content">
        <!-- 用户信息 -->
        <div class="user-info-section">
          <div class="avatar-section">
            <el-avatar :size="80" class="user-avatar">
              {{ authStore.user?.username?.charAt(0).toUpperCase() }}
            </el-avatar>
            <div class="user-meta">
              <h4>{{ authStore.user?.username }}</h4>
              <p>{{ authStore.user?.email }}</p>
              <el-tag :type="authStore.isAdmin ? 'danger' : 'info'">
                {{ authStore.isAdmin ? '管理员' : '普通用户' }}
              </el-tag>
            </div>
          </div>
        </div>

        <el-divider />

        <!-- 修改密码 -->
        <div class="password-section">
          <h4>修改密码</h4>
          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="100px"
            class="password-form"
          >
            <el-form-item label="旧密码" prop="old_password">
              <el-input
                v-model="form.old_password"
                type="password"
                placeholder="请输入旧密码"
                show-password
              />
            </el-form-item>

            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="form.new_password"
                type="password"
                placeholder="请输入新密码（至少6个字符）"
                show-password
              />
            </el-form-item>

            <el-form-item label="确认密码" prop="confirm_password">
              <el-input
                v-model="form.confirm_password"
                type="password"
                placeholder="请确认新密码"
                show-password
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="loading" @click="handleChangePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage, type FormInstance } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { changePassword } from '@/api/auth'

const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

const validateConfirmPassword = (rule: any, value: string, callback: any) => {
  if (value !== form.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleChangePassword = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await changePassword({
      old_password: form.old_password,
      new_password: form.new_password
    })
    ElMessage.success('密码修改成功')
    formRef.value?.resetFields()
  } catch (error) {
    // 错误已在拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.profile-container {
  max-width: 600px;
  margin: 0 auto;
}

.profile-card {
  border-radius: 8px;
}

.card-header h3 {
  margin: 0;
  color: #303133;
}

.user-info-section {
  padding: 20px 0;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 24px;
}

.user-avatar {
  background: #409eff;
  color: #fff;
  font-size: 32px;
}

.user-meta h4 {
  margin: 0 0 8px 0;
  color: #303133;
}

.user-meta p {
  margin: 0 0 12px 0;
  color: #909399;
}

.password-section h4 {
  margin: 0 0 20px 0;
  color: #303133;
}

.password-form {
  max-width: 400px;
}
</style>
