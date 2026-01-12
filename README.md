# A股打板提示工具

个人自用盘中"选股/打板提示"工具，提供候选池筛选、触发提示、仓位建议和复盘功能。

## 功能特性

### 核心功能
- 📊 **市场情绪仪表盘**：涨停数、炸板率、跌停数、风险灯
- 📋 **候选池管理**：实时评分排序，支持筛选和自选
- 🔔 **提示卡系统**：可执行提示 + 条件解释 + 仓位建议
- 💼 **持仓与风控**：仓位控制、连亏停手、回撤控制
- 📈 **复盘系统**：历史回放、失败分析、参数建议

### 策略支持
- **回封主策略 (reseal_v1)**：追踪开板后快速回封的标的
- **首封保守策略 (firstseal_guard_v1)**：在良好环境下追踪首次封板

### 技术特点
- 响应式设计，支持桌面端和移动端
- WebSocket 实时推送
- 数据延迟自动降级
- 快照回放支持

## 技术架构

```
├── backend/          # FastAPI 后端
│   ├── adapters/     # 数据适配器 (adata)
│   ├── api/          # REST + WebSocket API
│   ├── core/         # 核心模块 (日历、QA、配置)
│   ├── features/     # 特征引擎
│   ├── journal/      # 日志、快照、复盘
│   ├── market/       # 市场情绪、热点
│   ├── risk/         # 风控引擎
│   ├── signals/      # 信号计划器
│   ├── storage/      # 数据库存储
│   └── strategies/   # 策略实现
├── frontend/         # Next.js 前端
│   ├── app/          # 页面
│   └── lib/          # 工具函数和 API
├── configs/          # 配置文件
│   ├── app.yaml      # 应用配置
│   └── strategies/   # 策略配置
└── data/             # SQLite 数据库
```

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 安装和启动

```bash
# 1. 克隆项目后进入目录
cd BigA

# 2. 创建 Python 虚拟环境并安装依赖
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r backend/requirements.txt

# 3. 安装前端依赖
cd frontend
npm install
cd ..

# 4. 启动服务（两种方式）

# 方式一：使用启动脚本（推荐）
chmod +x start.sh
./start.sh

# 方式二：分别启动
# 终端1 - 启动后端
python start_backend.py

# 终端2 - 启动前端
cd frontend && npm run dev
```

### 访问地址
- 前端页面: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 配置说明

### 应用配置 (`configs/app.yaml`)

```yaml
runtime:
  refresh_sec: 10          # 数据刷新间隔
  max_data_lag_sec: 20     # 最大数据延迟

market:
  pct_limit_up: 0.095      # 涨停判定阈值
  pct_near_limit_up: 0.092 # 接近涨停阈值

event_approx:
  limit_up_eps: 0.0005     # 涨停容差
  window_m: 30             # 统计窗口（分钟）
```

### 策略配置 (`configs/strategies/*.yaml`)

策略参数包括：
- `market_gate`: 市场门槛（风险灯、炸板率）
- `stock_filter`: 个股过滤（成交额、流动性）
- `scoring`: 评分权重
- `trigger`: 触发条件
- `plan`: 执行计划
- `risk`: 风控规则

## 使用流程

### 1. 开盘前 (9:00-9:30)
- 选择策略组（回封主 / 首封保守）
- 设置风险档位
- 关注的题材（可选）

### 2. 盘中
- 查看市场情绪仪表盘
- 关注候选池排序
- 处理提示卡（出现 ALLOW 时决策）
- 记录执行结果

### 3. 收盘后
- 查看复盘页面
- 标记提示卡结果（成功/失败/跳过）
- 分析失败模式
- 调整策略参数

## API 接口

### REST API
- `GET /api/market/dashboard` - 市场仪表盘
- `GET /api/candidates` - 候选池
- `GET /api/alerts` - 提示卡列表
- `PATCH /api/alerts/{id}/label` - 更新提示卡标签
- `GET /api/portfolio/positions` - 持仓列表
- `GET /api/risk/state` - 风控状态
- `GET /api/replay/snapshot/{id}` - 快照回放

### WebSocket
- `ws://localhost:8000/ws/stream` - 实时推送

## 注意事项

1. **数据源**: 默认使用 adata 库获取数据。如未安装 adata，将使用模拟数据。
2. **数据延迟**: 当数据延迟超过阈值时，系统会自动禁止 ALLOW 输出。
3. **非自动交易**: 本工具仅提供提示，不执行自动交易。
4. **风控优先**: 红灯环境下禁止任何 ALLOW 输出。

## 许可证

仅供个人学习使用。
