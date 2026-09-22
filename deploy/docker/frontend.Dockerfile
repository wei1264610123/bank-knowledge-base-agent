# ============================================
# 银行问答系统 - 前端镜像（多阶段构建）
# 阶段1: Node 构建前端静态文件
# 阶段2: nginx 托管静态文件 + 反向代理 API
# ============================================
FROM node:20-alpine AS builder

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:alpine

# nginx 配置（静态托管 + /api 反向代理到后端容器）
COPY deploy/docker/nginx.conf /etc/nginx/conf.d/default.conf
# 前端构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80