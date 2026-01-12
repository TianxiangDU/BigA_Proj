#!/bin/bash
# A股打板提示工具 - 启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  A股打板提示工具 - 启动脚本${NC}"
echo -e "${GREEN}================================================${NC}"

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# 创建必要的目录
mkdir -p data logs

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 Python3${NC}"
    exit 1
fi

# 检查 Node.js 环境
if ! command -v npm &> /dev/null; then
    echo -e "${RED}错误: 未找到 npm${NC}"
    exit 1
fi

# 启动模式
MODE=${1:-"all"}

start_backend() {
    echo -e "${YELLOW}启动后端服务...${NC}"
    
    # 检查依赖
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}创建 Python 虚拟环境...${NC}"
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    
    # 安装依赖
    pip install -q -r backend/requirements.txt
    
    # 启动后端
    python start_backend.py &
    BACKEND_PID=$!
    echo -e "${GREEN}后端服务已启动 (PID: $BACKEND_PID)${NC}"
}

start_frontend() {
    echo -e "${YELLOW}启动前端服务...${NC}"
    
    cd frontend
    
    # 安装依赖
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}安装前端依赖...${NC}"
        npm install
    fi
    
    # 启动前端
    npm run dev &
    FRONTEND_PID=$!
    echo -e "${GREEN}前端服务已启动 (PID: $FRONTEND_PID)${NC}"
    
    cd ..
}

case $MODE in
    "backend")
        start_backend
        wait
        ;;
    "frontend")
        start_frontend
        wait
        ;;
    "all")
        start_backend
        sleep 2
        start_frontend
        
        echo -e ""
        echo -e "${GREEN}================================================${NC}"
        echo -e "${GREEN}  服务已启动:${NC}"
        echo -e "${GREEN}  - 后端 API: http://localhost:8000${NC}"
        echo -e "${GREEN}  - 前端页面: http://localhost:3000${NC}"
        echo -e "${GREEN}  - API 文档: http://localhost:8000/docs${NC}"
        echo -e "${GREEN}================================================${NC}"
        echo -e ""
        echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
        
        wait
        ;;
    *)
        echo "用法: $0 [backend|frontend|all]"
        exit 1
        ;;
esac
