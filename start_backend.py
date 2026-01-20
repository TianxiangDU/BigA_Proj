#!/usr/bin/env python
"""
启动后端服务
"""
import os
import sys

# 设置时区为北京时间（必须在导入其他模块之前）
os.environ['TZ'] = 'Asia/Shanghai'
try:
    import time
    time.tzset()  # Unix 系统生效
except AttributeError:
    pass  # Windows 不支持 tzset

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
    
    # Railway 等云平台通过 PORT 环境变量指定端口
    port = int(os.environ.get("PORT", 8000))
    # 生产环境检测
    is_production = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PRODUCTION")
    
    logger.info("=" * 50)
    logger.info("A股打板提示工具 - 后端服务启动")
    logger.info(f"端口: {port}, 生产模式: {bool(is_production)}")
    logger.info("=" * 50)
    
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=not is_production,  # 生产环境禁用热重载
        log_level="info"
    )

if __name__ == "__main__":
    main()
