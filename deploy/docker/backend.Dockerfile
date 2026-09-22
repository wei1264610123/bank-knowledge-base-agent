# ============================================
# 银行问答系统 - 后端镜像
# 构建上下文: 项目根目录 (docker compose build 时自动处理)
# ============================================
FROM python:3.11-slim

WORKDIR /app

# chromadb 需要的系统库 (libgomp) 与最小化清理
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖清单，利用 Docker 层缓存加速重复构建
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 仅复制后端代码（.env 等敏感文件一律不进镜像，运行期通过 env_file 注入）
COPY backend/app ./app

# 数据目录：bankkb.db / chroma_data / uploads 由 docker-compose 的 volume 挂载到这里
RUN mkdir -p /app/data

EXPOSE 8000

# 生产模式：关闭 reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]