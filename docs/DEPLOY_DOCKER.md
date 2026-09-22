# 🐳 Docker 部署教程（小白版）

把整个系统装进"集装箱"，任何 Linux 服务器一条命令就能跑起来。

## 部署后长这样

```
你访问 http://服务器IP ──► nginx（装前端页面 + 转发请求）
                              │ /api 转发
                              ▼
                          后端 FastAPI ──► SQLite + ChromaDB（存数据卷里）
```

**两个容器**：`bankkb-frontend`（网页 + 转发）、`bankkb-backend`（AI 后端）。
**一个数据卷**：`bankkb-data`（你的数据库/知识库/上传文件，容器删了也不丢）。

---

## 第 1 步：准备一台服务器

需要一个 **Linux 服务器**（Ubuntu 22.04/24.04 推荐）。⚠️ 你的 Windows 本机暂时无法直接跑这套 Docker（本机没装 Docker）。

服务器最低配置：**2核 2G 内存** 即可，推荐 2核4G。

> 💡 在国内服务器（阿里云/腾讯云）上部署，访问阿里云百炼 API 更快。

## 第 2 步：服务器安装 Docker

用 SSH 登录服务器，粘贴执行：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

验证（能显示版本号就成功）：

```bash
docker --version && docker compose version
```

## 第 3 步：把代码复制到服务器

```bash
git clone https://github.com/wei1264610123/bank-knowledge-base-agent.git
cd bank-knowledge-base-agent
```

## 第 4 步：填写你的 API Key（关键！）

```bash
cp backend/.env.example backend/.env
```

然后编辑 `backend/.env`（推荐 `nano backend/.env`），必须改这两处：

```ini
DASHSCOPE_API_KEY=你的阿里云百炼API Key   # ← 必填！
JWT_SECRET_KEY=随便填一串很长的乱码       # ← 强烈建议改，否则 token 有被伪造风险
```

## 第 5 步：一条命令启动 🚀

```bash
cd deploy/docker
docker compose up -d --build
```

第一次运行会自动下载镜像 + 构建，**约 5~15 分钟**（取决于网速），以后启动只需几秒。

看构建进度：

```bash
docker compose logs -f
```

看到类似 `银行问答系统启动完成` 就说明 OK 了。按 `Ctrl+C` 退出日志查看。

## 第 6 步：访问系统 ✅

在浏览器打开：

| 地址 | 说明 |
|---|---|
| `http://服务器IP` | 系统主页（前端 + 问答，80 端口） |
| `http://服务器IP:8000/docs` | 后端 API 文档（可选） |

> 如果服务器有防火墙（阿里云/腾讯云安全组），记得放行 **80** 端口（和 8000，如果要用文档）。

---

## 日常运维（记这 4 条就够）

```bash
# 重启服务（改完代码重新构建后）          # 停服务
docker compose restart                    docker compose down
# 看日志（排查问题）                      # 完全删除（含数据卷！慎用）
docker compose logs -f -n 100              docker compose down -v
```

## 重新部署新版本（升级）

以后代码更新了，在服务器上：

```bash
git pull                          # 1. 拉取最新代码
cd deploy/docker
docker compose up -d --build      # 2. 重新构建并启动
```

数据都在卷里，升级**不会丢**你的知识库和用户数据。

## 备份与恢复

数据都在 Docker 卷 `bankkb-data` 里，备份：

```bash
# 备份（生成一个 tar 包）
docker run --rm -v bankkb-data:/data -v $PWD:/backup alpine tar czf /backup/bankkb-backup.tar.gz -C /data .
```

恢复：

```bash
docker run --rm -v bankkb-data:/data -v $PWD:/backup alpine tar xzf /backup/bankkb-backup.tar.gz -C /data
```

## 常见问题（FAQ）

**Q: 构建时报 `docker compose up` 找不到命令？**
A: 确认第 2 步装了 `docker-compose-plugin`。

**Q: 打开网页一直转圈/报请求失败？**
A: 八成是 `backend/.env` 里 `DASHSCOPE_API_KEY` 没填或填错。改好后 `docker compose restart backend`。

**Q: 登录报错？**
A: 确认 `.env` 里 `JWT_SECRET_KEY` 已修改且后端容器是最新构建（版本已在 requirements.txt 固定好，无需手动处理）。

**Q: 80 端口被占用？**
A: `docker compose down`，然后改 `deploy/docker/docker-compose.yml` 里 frontend 的 `"80:80"` 为别的端口如 `"8080:80"`，再 `up -d --build`。

**Q: 忘记服务器密码/数据没了？**
A: 备份命令（见上）定期执行一次，存到本地或对象存储最稳妥。

---

## 架构说明（为什么会这样设计）

- **双容器**：前端页面交给 Nginx（性能好、标准做法），后端独立运行，互不干扰
- **相对路径 `/api`**：前端请求 `/api/...`，Nginx 转发给后端，浏览器和服务器之间不跨域、不需要改前端代码
- **数据卷**：数据库、向量库、上传文件放卷里，容器随便重建都不丢
- **安全**：`.env`（含 API Key）不进镜像，运行期才注入；镜像里只含代码