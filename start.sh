#!/bin/bash

# 检查是否已激活 conda 环境
if [[ "$CONDA_DEFAULT_ENV" != "webprint" ]]; then
    echo "正在激活 webprint 环境..."
    eval "$(conda shell.bash hook)"
    conda activate webprint
fi

# 创建日志目录
mkdir -p logs

# 杀死可能存在的旧进程
if [ -f "logs/backend.pid" ]; then
    OLD_BACKEND_PID=$(cat logs/backend.pid)
    if ps -p $OLD_BACKEND_PID > /dev/null; then
        echo "正在停止旧的后端服务..."
        kill $OLD_BACKEND_PID
    fi
fi

if [ -f "logs/frontend.pid" ]; then
    OLD_FRONTEND_PID=$(cat logs/frontend.pid)
    if ps -p $OLD_FRONTEND_PID > /dev/null; then
        echo "正在停止旧的前端服务..."
        kill $OLD_FRONTEND_PID
    fi
fi

# 确保上传目录存在
echo "确保上传目录存在..."
mkdir -p backend/uploads

# 启动后端服务
echo "正在启动后端服务..."
cd backend
python app.py > ../logs/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# 等待后端服务启动
echo "等待后端服务启动..."
sleep 3

# 启动前端服务
echo "正在启动前端服务..."
cd frontend
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 保存进程 ID
echo $BACKEND_PID > logs/backend.pid
echo $FRONTEND_PID > logs/frontend.pid

echo "服务已启动！"
echo "后端服务 PID: $BACKEND_PID"
echo "前端服务 PID: $FRONTEND_PID"
echo "日志文件位置: ./logs/"
echo "前端地址: http://localhost:5173"
echo "后端地址: http://localhost:5001"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap "kill $BACKEND_PID $FRONTEND_PID; rm -f logs/*.pid; echo '服务已停止'; exit" INT
wait 