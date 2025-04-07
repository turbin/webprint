#!/bin/bash

# 检查 PID 文件是否存在
if [ -f "logs/backend.pid" ] && [ -f "logs/frontend.pid" ]; then
    # 读取 PID
    BACKEND_PID=$(cat logs/backend.pid)
    FRONTEND_PID=$(cat logs/frontend.pid)

    # 停止后端服务
    if ps -p $BACKEND_PID > /dev/null; then
        echo "正在停止后端服务..."
        kill $BACKEND_PID
    fi

    # 停止前端服务
    if ps -p $FRONTEND_PID > /dev/null; then
        echo "正在停止前端服务..."
        kill $FRONTEND_PID
    fi

    # 删除 PID 文件
    rm -f logs/backend.pid logs/frontend.pid
    echo "所有服务已停止"
else
    echo "未找到运行中的服务"
fi 