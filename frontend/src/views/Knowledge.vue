<template>
  <div class="knowledge-container">
    <el-card class="knowledge-card">
      <template #header>
        <div class="card-header">
          <h3>📚 知识库管理</h3>
          <div class="header-actions">
            <el-button type="primary" @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon>
              上传文档
            </el-button>
          </div>
        </div>
      </template>

      <!-- 分类筛选 -->
      <div class="filter-bar">
        <el-select
          v-model="selectedCategory"
          placeholder="选择分类"
          clearable
          @change="handleFilterChange"
        >
          <el-option
            v-for="cat in categories"
            :key="cat.id"
            :label="cat.name"
            :value="cat.id"
          />
        </el-select>
      </div>

      <!-- 文档列表 -->
      <el-table
        :data="documents"
        v-loading="loading"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="filename" label="文件名" min-width="200" />
        <el-table-column prop="file_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="getStatusType(row.status)"
              size="small"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="120">
          <template #default="{ row }">
            {{ row.category_name || '未分类' }}
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" @click="handleViewDetail(row)">
              查看
            </el-button>
            <el-button
              text
              type="warning"
              :disabled="row.status === 'processing'"
              @click="handleReprocess(row)"
            >
              重新处理
            </el-button>
            <el-button text type="danger" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传文档"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item label="选择文件">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".pdf,.docx,.txt,.md"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
          >
            <el-icon class="el-icon--upload"><Upload /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 PDF、Word(.docx)、TXT、Markdown 格式，文件大小不超过 10MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item label="选择分类">
          <el-select v-model="uploadCategoryId" placeholder="选择分类（可选）" clearable>
            <el-option
              v-for="cat in categories"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 文档详情对话框 -->
    <el-dialog
      v-model="showDetailDialog"
      title="文档详情"
      width="800px"
    >
      <div v-if="currentDocument" class="document-detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件名">{{ currentDocument.filename }}</el-descriptions-item>
          <el-descriptions-item label="文件类型">{{ currentDocument.file_type }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ formatFileSize(currentDocument.file_size) }}</el-descriptions-item>
          <el-descriptions-item label="分块数">{{ currentDocument.chunk_count }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(currentDocument.status)">
              {{ getStatusText(currentDocument.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分类">{{ currentDocument.category_name || '未分类' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 20px 0 10px">文档内容分块</h4>
        <div class="chunks-list">
          <div v-for="chunk in currentDocument.chunks" :key="chunk.id" class="chunk-item">
            <div class="chunk-header">分块 #{{ chunk.chunk_index + 1 }}</div>
            <div class="chunk-content">{{ chunk.content }}</div>
          </div>
          <el-empty v-if="currentDocument.chunks?.length === 0" description="暂无分块内容" />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Upload } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadFile } from 'element-plus'
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  reprocessDocument,
  getDocument,
  getCategories
} from '@/api/knowledge'
import type { Document, DocumentDetail, Category } from '@/api/knowledge'

const documents = ref<Document[]>([])
const categories = ref<Category[]>([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const selectedCategory = ref<string>('')

// 上传相关
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadFile = ref<File | null>(null)
const uploadCategoryId = ref<string>('')

// 详情相关
const showDetailDialog = ref(false)
const currentDocument = ref<DocumentDetail | null>(null)

onMounted(async () => {
  await fetchDocuments()
  await fetchCategories()
})

const fetchDocuments = async () => {
  loading.value = true
  try {
    const response = await getDocuments(currentPage.value, pageSize.value, selectedCategory.value || undefined)
    documents.value = response.items
    total.value = response.total
  } finally {
    loading.value = false
  }
}

const fetchCategories = async () => {
  categories.value = await getCategories()
}

const handleFilterChange = () => {
  currentPage.value = 1
  fetchDocuments()
}

const handlePageChange = () => {
  fetchDocuments()
}

const handleSizeChange = () => {
  currentPage.value = 1
  fetchDocuments()
}

const handleFileChange = (file: UploadFile) => {
  uploadFile.value = file.raw
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个文件')
}

const handleUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    await uploadDocument(uploadFile.value, uploadCategoryId.value || undefined)
    ElMessage.success('文档上传成功')
    showUploadDialog.value = false
    uploadFile.value = null
    uploadCategoryId.value = ''
    await fetchDocuments()
  } finally {
    uploading.value = false
  }
}

const handleViewDetail = async (doc: Document) => {
  currentDocument.value = await getDocument(doc.id)
  showDetailDialog.value = true
}

const handleReprocess = async (doc: Document) => {
  await ElMessageBox.confirm('确定要重新处理该文档吗？', '提示', {
    type: 'warning'
  })
  
  await reprocessDocument(doc.id)
  ElMessage.success('文档已重新处理')
  await fetchDocuments()
}

const handleDelete = async (doc: Document) => {
  await ElMessageBox.confirm(`确定要删除文档"${doc.filename}"吗？此操作不可恢复。`, '警告', {
    type: 'warning'
  })
  
  await deleteDocument(doc.id)
  ElMessage.success('文档已删除')
  await fetchDocuments()
}

const formatFileSize = (size: number | null) => {
  if (!size) return '-'
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / 1024 / 1024).toFixed(1) + ' MB'
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getStatusType = (status: string) => {
  const types: Record<string, string> = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  }
  return texts[status] || status
}
</script>

<style scoped>
.knowledge-container {
  height: 100%;
}

.knowledge-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
}

.filter-bar {
  margin-bottom: 16px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.document-detail h4 {
  color: #303133;
}

.chunks-list {
  max-height: 400px;
  overflow-y: auto;
}

.chunk-item {
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 12px;
}

.chunk-header {
  font-weight: bold;
  color: #409eff;
  margin-bottom: 8px;
}

.chunk-content {
  color: #606266;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
