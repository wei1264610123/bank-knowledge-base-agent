/**
 * 知识库API
 */
import request from './request'

export interface Document {
  id: string
  filename: string
  file_type: string | null
  file_size: number | null
  status: string
  chunk_count: number
  category_id: string | null
  category_name: string | null
  created_at: string
  updated_at: string
}

export interface DocumentDetail extends Document {
  chunks: DocumentChunk[]
}

export interface DocumentChunk {
  id: string
  content: string
  chunk_index: number
  metadata: Record<string, any>
}

export interface Category {
  id: string
  name: string
  description: string | null
  created_at: string
  document_count: number
}

export interface DocumentListResponse {
  total: number
  items: Document[]
  page: number
  page_size: number
}

// 获取文档列表
export const getDocuments = (
  page: number = 1,
  pageSize: number = 20,
  categoryId?: string
): Promise<DocumentListResponse> => {
  const params: Record<string, any> = { page, page_size: pageSize }
  if (categoryId) params.category_id = categoryId
  return request.get('/knowledge/documents', { params })
}

// 上传文档
export const uploadDocument = (
  file: File,
  categoryId?: string
): Promise<Document> => {
  const formData = new FormData()
  formData.append('file', file)
  if (categoryId) {
    const params = new URLSearchParams()
    params.append('category_id', categoryId)
    return request.post(`/knowledge/documents?${params.toString()}`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
  return request.post('/knowledge/documents', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 获取文档详情
export const getDocument = (documentId: string): Promise<DocumentDetail> => {
  return request.get(`/knowledge/documents/${documentId}`)
}

// 删除文档
export const deleteDocument = (documentId: string) => {
  return request.delete(`/knowledge/documents/${documentId}`)
}

// 重新处理文档
export const reprocessDocument = (documentId: string): Promise<Document> => {
  return request.post(`/knowledge/documents/${documentId}/reprocess`)
}

// 获取分类列表
export const getCategories = (): Promise<Category[]> => {
  return request.get('/knowledge/categories')
}

// 创建分类
export const createCategory = (data: {
  name: string
  description?: string
}): Promise<Category> => {
  return request.post('/knowledge/categories', data)
}

// 删除分类
export const deleteCategory = (categoryId: string) => {
  return request.delete(`/knowledge/categories/${categoryId}`)
}
