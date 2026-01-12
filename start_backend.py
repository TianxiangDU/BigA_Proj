#!/usr/bin/env python
"""
启动后端服务
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from loguru import logger

# 配置日志
logger.add(
    "logs/backend_{time}.log",
    rotation="1 day",
    retention="7 days",
    level="INFO"
)

def main():
    """启动服务"""
    # 确保目录存在
    os.makedirs("data", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    logger.info("=" * 50)
    logger.info("A股打板提示工具 - 后端服务启动")
    logger.info("=" * 50)
    
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
