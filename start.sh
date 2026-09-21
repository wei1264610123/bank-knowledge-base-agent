#!/bin/bash

echo "========================================"
echo "  银行知识库智能问答系统 - 启动脚本"
echo "========================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3，请先安装Python 3.11+"
    exit 1
fi

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未找到Node.js，请先安装Node.js 18+"
    exit 1
fi

echo "[1/4] 检查Python依赖..."
cd backend
pip3 install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo "[错误] Python依赖安装失败"
    exit 1
fi

echo "[2/4] 启动后端服务..."
cd ..
cd backend && python3 run.py &
BACKEND_PID=$!

echo "[3/4] 等待后端服务启动..."
sleep 5

echo "[4/4] 启动前端服务..."
cd ../frontend
if [ ! -d "node_modules" ]; then
    echo "[信息] 首次运行，正在安装前端依赖..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  系统启动完成！"
echo "========================================"
echo ""
echo "  前端地址: http://localhost:5173"
echo "  后端地址: http://localhost:8000"
echo "  API文档:  http://localhost:8000/docs"
echo ""
echo "  默认管理员账号: admin / 123456"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "========================================"

# 等待用户中断
wait $BACKEND_PID $FRONTEND_PID
