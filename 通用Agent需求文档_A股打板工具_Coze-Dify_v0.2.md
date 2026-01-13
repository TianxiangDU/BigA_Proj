# 通用 Agent 需求文档（Coze / Dify 等低代码平台）｜A股打板提示工具（v0.3）
日期：2026-01-13  
适用：Coze、Dify、灵搭等"工作流/智能体平台" + 任意大模型（如 DeepSeek）  
范围：个人自用"选股/打板提示"工具的 Agent 层（不自动交易）  
目标：给出一份可落地的 Agent 需求文档：**用法、功能、输入/输出、测试用例、接口与技术对接、验收标准**。

> 说明：本文档"平台无关"，以 **工作流节点 + HTTP 工具 + 结构化 JSON** 的方式描述，保证你在 Coze/Dify 都能复现。

---

## 📌 App 侧接口已实现（v1.1.0）

| 接口 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/agent/input_bundle` | GET | 获取 Agent 输入数据包 | ✅ 已实现 |
| `/api/agent/apply_output` | POST | 接收 Agent 输出并应用 | ✅ 已实现 |
| `/api/agent/test` | GET | 测试连通性 | ✅ 已实现 |
| `/api/market/sentiment` | GET | 获取市场情绪分析 | ✅ 新增 |
| `/api/trading/status` | GET | 获取交易状态 | ✅ 新增 |
| `/api/trading/execute` | POST | 执行交易（模拟/实盘） | ✅ 新增 |

**快速测试：**
```bash
# 测试连通性
curl http://localhost:8000/api/agent/test

# 获取输入数据包
curl "http://localhost:8000/api/agent/input_bundle?symbol=300xxx&strategy_id=reseal_v1"

# 提交 Agent 输出
curl -X POST http://localhost:8000/api/agent/apply_output \
  -H "Content-Type: application/json" \
  -d '{"type":"SignalExplain","payload":{...}}'
```

---

## 1. 背景与目标
### 1.1 背景
打板辅助系统的关键链路：市场情绪/题材 → 候选池 → 触发器（回封/首封）→ 仓位风控 → 复盘沉淀。  
Agent 的价值：把 App 计算出的“结构化数据”转成 **可解释的建议**（提示卡/风控建议/复盘归因），并能持续迭代提示词与规则。

### 1.2 Agent 层目标（MVP）
- 输出 **MarketState**：市场状态与风险灯解释，建议仓位上限
- 输出 **SignalExplain**：对某只票生成“可执行提示卡”（WATCH/ALLOW/BLOCK + plan + triggers）
- 支持 **可回放**：输出必须能与 snapshot_id 绑定（由 App 完成落库）
- 支持 **降级**：当数据缺失/延迟时宁可 WATCH/BLOCK

### 1.3 非目标（MVP不做）
- 不自动下单、不接券商
- 不做高频盘口队列级判断（先分钟级/特征级）
- 不做多用户协作（个人自用）

---

## 2. 系统边界与职责划分（非常重要）
### 2.1 App（你用 Cursor 开发）负责
- 数据接入（adata）、缓存、本地数据库
- 特征计算、候选池生成、策略硬条件判断
- 数据质量检测（延迟/缺失）与最终风控裁决
- 快照/提示卡写库、WebSocket 推送、回放/复盘页面

### 2.2 Agent（Coze/Dify 等）负责
- 读取 App 给的 **input_bundle**（结构化 JSON）
- 生成解释与建议（MarketState / SignalExplain / 可选 ThemeHeat / RiskCoach / ReviewAnalyst）
- 输出必须结构化（JSON），便于 App 落库与前端展示
- 不直接拉行情（避免数据源不一致）

---

## 3. Agent 组成与功能说明（模块化）
> 推荐做成多个独立 Agent（或多个 workflow）：便于迭代与 A/B。

### 3.1 MarketState Agent（必做）
**用途：**对市场状态、风险灯给出解释，建议当下总仓/单票仓位上限。  
**典型用法：**
- App 每 30~60 秒触发一次；或风险灯/炸板率变化时触发
- 输出写入 dashboard 面板

**输出要点：**
- mode：STRONG / DIVERGENCE / WEAK / CHAOS
- risk_light：GREEN / YELLOW / RED（如与 App 不一致，以 App 为准）
- suggested_risk：allow_new_trades、max_total_position、max_single_position
- reasons：必须解释“为什么是这个状态”（用数值对比阈值）

### 3.2 SignalExplain Agent（必做，核心）
**用途：**对某只候选股生成“提示卡”：动作 + 仓位建议 + 失败条件 + 可解释 triggers。  
**典型用法：**
- 由 App 在候选池出现 “NEAR/TRIGGERED” 时调用
- 或用户在前端手动点击“生成提示卡”

**输出要点：**
- action：WATCH / ALLOW / BLOCK（仅建议；最终由 App 风控裁决）
- triggers：PASS/FAIL/MISSING 列表（必须可回放审计）
- plan：max_single_position、entry_note、exit_rules（≥3条）
- warnings：数据降级/缺字段/低置信度都要写

### 3.3 ThemeHeat Agent（可选）
**用途：**对题材分层（主线/分支/退潮），给候选池筛选与提示卡解释提供上下文。  
**数据不足时降级：**themes 为空 → 输出 warnings 并返回空列表。

### 3.4 RiskCoach Agent（可选）
**用途：**结合 portfolio（持仓/连亏/回撤）给更保守的仓控建议。App 取 min。

### 3.5 ReviewAnalyst Agent（可选）
**用途：**收盘后对某条提示卡 outcome 做归因与参数建议，沉淀调参经验。

### 3.6 SentimentAnalysis Agent（新增，推荐）
**用途：**对市场情绪进行多维度分析，输出综合情绪评分和等级。

**App 已实现的情绪分析维度：**
- `sentiment_score`：0-100 综合情绪分数
- `sentiment_grade`：A/B/C/D/E 情绪等级
- `sentiment_text`：极强/偏强/中性/偏弱/极弱
- `risk_light`：GREEN/YELLOW/RED 风险灯
- `rise_fall_ratio`：涨跌家数比
- `sh_pct_change`：上证涨跌幅
- `cyb_pct_change`：创业板涨跌幅
- `total_amount`：总成交额（亿）
- `needs_agent_analysis`：是否需要 Agent 深度分析
- `agent_analysis_reasons`：建议 Agent 介入分析的原因列表

**Agent 介入时机（App 自动判断）：**
1. 情绪分数异常（<30 或 >80）
2. 炸板率突变（>40%）
3. 涨跌家数比极端（<0.5 或 >3）
4. 风险灯变化
5. 主力资金大幅流出

**典型用法：**
- 当 `needs_agent_analysis == true` 时，Agent 可被触发进行深度分析
- 输出更详细的市场状态解读和操作建议

---

## 4. 通用输入协议（App → Agent）
### 4.1 input_bundle（统一输入载体）
Agent 只依赖这个 JSON，不直接访问行情源。

#### 示例
```json
{
  "ts": "2026-01-12T10:05:00+08:00",
  "market": {
    "limit_up_count": 42,
    "touch_limit_up_count": 60,
    "bomb_rate": 0.22,
    "max_streak": 4,
    "down_limit_count": 3,
    "risk_light": "YELLOW",
    "regime_mode": "DIVERGENCE",
    "index_ret_15m": -0.002
  },
  "themes": [
    {"name":"AI应用","strength":0.78,"leaders":["000001","300xxx"],"notes":""}
  ],
  "candidates": [
    {
      "symbol":"300xxx",
      "name":"示例股",
      "tags":["AI应用","回封"],
      "features":{
        "slope_5m":0.63,
        "pullback_5m":0.12,
        "amt":120000000,
        "reseal_speed_sec":45,
        "reseal_stable_min":1,
        "open_count_30m":1,
        "vol_ratio_5m":1.9,
        "is_limit_up":true,
        "near_limit_up":true
      },
      "scores":{
        "total":82.4,
        "market":78.0,
        "stock":84.0,
        "quality":80.0,
        "risk_penalty":8.0
      }
    }
  ],
  "portfolio": {
    "positions":[{"symbol":"600xxx","qty":1000,"avg_cost":12.3}],
    "cash": 50000,
    "daily_pnl": 0.0,
    "consecutive_losses": 0
  },
  "strategy_context": {
    "strategy_id":"reseal_v1",
    "risk_profile":"balanced",
    "selected_themes":["AI应用"],
    "data_quality":{
      "data_lag_sec": 2,
      "is_degraded": false,
      "missing_fields":[]
    }
  }
}
```

### 4.2 输入关键约束（必须实现）
- `strategy_context.data_quality.is_degraded == true`：Agent 应倾向 WATCH/BLOCK，并在 warnings 写明。
- `market.risk_light == RED`：SignalExplain 必须 BLOCK（或至少不允许 ALLOW）。
- 缺字段允许，但 triggers 必须标 `MISSING` 并降级建议。

---

## 5. 通用输出协议（Agent → App）
### 5.1 Envelope（统一信封）
所有 Agent 输出都用该封装，便于 App 接收与落库：
```json
{
  "type": "MarketState|SignalExplain|ThemeHeat|RiskCoach|ReviewAnalyst",
  "payload": { }
}
```

### 5.2 结构化输出硬要求
- 必须是 **纯 JSON**（不得带 markdown/解释性文字）
- 必须包含：`agent, version, ts, confidence, warnings`
- SignalExplain 必须包含：`action, triggers[], plan{...}, one_liner, snapshot_hint`

---

## 6. 各 Agent 的输出 Schema（开发约束）
### 6.1 MarketState.payload
```json
{
  "agent":"MarketState",
  "version":"0.1.0",
  "ts":"",
  "mode":"STRONG|DIVERGENCE|WEAK|CHAOS",
  "risk_light":"GREEN|YELLOW|RED",
  "confidence":0.0,
  "reasons":[{"key":"","value":0,"rule":""}],
  "suggested_risk":{"allow_new_trades":true,"max_total_position":0.6,"max_single_position":0.15},
  "warnings":[]
}
```

### 6.2 SignalExplain.payload（核心）
```json
{
  "agent":"SignalExplain",
  "version":"0.1.0",
  "ts":"",
  "symbol":"",
  "strategy_id":"",
  "action":"WATCH|ALLOW|BLOCK",
  "confidence":0.0,
  "triggers":[{"name":"","status":"PASS|FAIL|MISSING","detail":""}],
  "plan":{
    "max_single_position":0.0,
    "entry_note":"",
    "exit_rules":["","",""]
  },
  "risks":["",""],
  "one_liner":"",
  "snapshot_hint":{"should_create_snapshot":true,"snapshot_tags":[""]},
  "warnings":[]
}
```

### 6.3 ThemeHeat.payload（可选）
```json
{
  "agent":"ThemeHeat",
  "version":"0.1.0",
  "ts":"",
  "top_themes":[{"name":"","tier":"MAIN|SUB","strength":0.0,"notes":"","leaders":[]}],
  "avoid_themes":[{"name":"","reason":""}],
  "confidence":0.0,
  "warnings":[]
}
```

### 6.4 RiskCoach.payload（可选）
```json
{
  "agent":"RiskCoach",
  "version":"0.1.0",
  "ts":"",
  "allow_new_trades":true,
  "max_total_position":0.0,
  "max_single_position":0.0,
  "stop_reason":null,
  "notes":[""],
  "confidence":0.0,
  "warnings":[]
}
```

### 6.5 ReviewAnalyst.payload（可选）
```json
{
  "agent":"ReviewAnalyst",
  "version":"0.1.0",
  "alert_id":"",
  "label":"SUCCESS|FAIL",
  "confidence":0.0,
  "root_causes":[{"factor":"","detail":""}],
  "suggestions":["",""],
  "summary":"",
  "warnings":[]
}
```

---

## 7. Agent 行为规则（必须实现）
### 7.1 降级规则（强约束）
- 数据降级（is_degraded=true 或 data_lag_sec 超阈值）：
  - SignalExplain：action 不得为 ALLOW；confidence < 0.6；warnings 必须说明。
- 市场红灯（risk_light=RED）：SignalExplain 必须 BLOCK。
- 低置信度：confidence < 0.6 时 action 不得为 ALLOW。

### 7.2 策略规则（用于 triggers 解释）
- reseal_v1（回封主）推荐 ALLOW 条件：
  - risk_light != RED
  - bomb_rate <= 0.30
  - reseal_speed_sec <= 60
  - reseal_stable_min >= 1
  - slope_5m >= 0.25
  - pullback_5m <= 0.18
  - amt >= 80,000,000
  - open_count_30m <= 3

- firstseal_guard_v1（首封保守）推荐 ALLOW 条件：
  - risk_light == GREEN
  - bomb_rate <= 0.25
  - is_limit_up == true
  - open_count_30m <= 1
  - vol_ratio_5m >= 1.8
  - pullback_5m <= 0.12
  - slope_5m >= 0.20
  - amt >= 120,000,000

### 7.3 计划输出规范（SignalExplain.plan）
- max_single_position：建议按 GREEN/YELLOW 折减（黄灯建议 *0.7）
- entry_note：1 句话说明“什么时候执行/不要追高”等
- exit_rules（至少 3 条）必须包含：
  1) 开板后 N 秒不回封（或首封开板）→ 放弃/减仓
  2) pullback_5m 超阈值 → 停止追/撤退
  3) risk_light 变 RED → 停止新增

---

## 8. 平台落地方式（Coze/Dify 通用）
### 8.1 工作流节点推荐模板
以 SignalExplain 为例：
1) HTTP GET：从 App 拉 input_bundle（建议 App 聚合好）
2) LLM：生成 payload（强制纯 JSON）
3) JSON 校验/修复（可选但强烈建议）
4) HTTP POST：回写 apply_output（Envelope）
5) End：返回“人话摘要”（可选）

### 8.2 模型参数建议（DeepSeek 等）
- temperature：0.1~0.3（输出稳定）
- top_p：0.8~1.0
- max_tokens：800~1500（SignalExplain 足够）
- 开启结构化/JSON 模式（若平台支持）

---

## 9. 技术与接口对接（App 侧必须支持）
### 9.1 推荐接口（最小闭环）
1) **拉取输入**（给 Agent 用）
- `GET /api/agent/input_bundle?symbol=xxxxxx&strategy_id=reseal_v1`
- 返回：input_bundle JSON

2) **回写输出**（Agent 写回 App）
- `POST /api/agent/apply_output`
- body：
```json
{"type":"SignalExplain","payload":{...}}
```

### 9.2 鉴权（建议）
- Header：`Authorization: Bearer <APP_API_KEY>`
- App 只信任白名单来源或加签名（可选）

### 9.3 落库建议（App 内部）
- SignalExplain：写入 `alerts` 表（card_json + snapshot_id）并 WS 推送
- MarketState：写入 `market_label` 或 `market_features` 的扩展字段并 WS 推送

---

## 10. 测试用例（必备）
### 10.1 用例 A：回封主策略正常 ALLOW（黄灯可小仓）
**输入（signal_explain_request）**
```json
{
  "symbol":"300xxx",
  "input_bundle": {
    "ts":"2026-01-12T10:05:00+08:00",
    "market":{"limit_up_count":42,"touch_limit_up_count":60,"bomb_rate":0.22,"max_streak":4,"down_limit_count":3,"risk_light":"YELLOW","regime_mode":"DIVERGENCE"},
    "themes":[{"name":"AI应用","strength":0.78,"leaders":["000001","300xxx"],"notes":""}],
    "candidates":[{"symbol":"300xxx","name":"示例股","tags":["AI应用","回封"],"features":{"slope_5m":0.63,"pullback_5m":0.12,"amt":120000000,"reseal_speed_sec":45,"reseal_stable_min":1,"open_count_30m":1,"vol_ratio_5m":1.9,"is_limit_up":true,"near_limit_up":true},"scores":{"total":82.4}}],
    "portfolio":{"positions":[],"cash":50000,"daily_pnl":0.0,"consecutive_losses":0},
    "strategy_context":{"strategy_id":"reseal_v1","risk_profile":"balanced","selected_themes":["AI应用"],"data_quality":{"data_lag_sec":2,"is_degraded":false,"missing_fields":[]}}
  }
}
```
**期望**
- action：ALLOW（或更保守 WATCH 也可，但必须自洽）
- triggers：至少包含环境、回封速度、稳定、强度、回撤、成交额、开板次数
- plan.max_single_position：黄灯建议 ≤0.10，并说明折减
- exit_rules：包含必备三条

### 10.2 用例 B：数据降级（必须禁 ALLOW）
```json
{
  "symbol":"300xxx",
  "input_bundle":{
    "ts":"2026-01-12T10:10:00+08:00",
    "market":{"risk_light":"GREEN","bomb_rate":0.12},
    "candidates":[{"symbol":"300xxx","features":{"reseal_speed_sec":30}}],
    "strategy_context":{"strategy_id":"reseal_v1","data_quality":{"is_degraded":true,"data_lag_sec":45,"missing_fields":["pullback_5m"]}}
  }
}
```
**期望**
- action：WATCH/BLOCK
- confidence < 0.6
- warnings 明确“数据延迟/缺字段降级”
- triggers 里 pullback_5m = MISSING

### 10.3 用例 C：红灯环境（必须 BLOCK）
```json
{
  "symbol":"300xxx",
  "input_bundle":{
    "ts":"2026-01-12T10:15:00+08:00",
    "market":{"risk_light":"RED","bomb_rate":0.48},
    "candidates":[{"symbol":"300xxx","features":{"reseal_speed_sec":20,"reseal_stable_min":2}}],
    "strategy_context":{"strategy_id":"reseal_v1","data_quality":{"is_degraded":false}}
  }
}
```
**期望**
- action：BLOCK
- triggers 环境门槛 FAIL

### 10.4 用例 D：首封保守策略（绿灯 ALLOW）
```json
{
  "symbol":"600yyy",
  "input_bundle":{
    "ts":"2026-01-12T10:20:00+08:00",
    "market":{"risk_light":"GREEN","bomb_rate":0.18,"limit_up_count":55,"down_limit_count":2},
    "candidates":[{"symbol":"600yyy","features":{"is_limit_up":true,"open_count_30m":0,"vol_ratio_5m":2.1,"pullback_5m":0.08,"slope_5m":0.25,"amt":250000000}}],
    "strategy_context":{"strategy_id":"firstseal_guard_v1","data_quality":{"is_degraded":false}}
  }
}
```
**期望**
- action：ALLOW
- plan.max_single_position ≤ 0.10
- exit_rules：首封开板即放弃等

### 10.5 用例 E：symbol 不在候选池（必须 BLOCK）
```json
{
  "symbol":"000000",
  "input_bundle":{
    "ts":"2026-01-12T10:25:00+08:00",
    "market":{"risk_light":"GREEN","bomb_rate":0.12},
    "candidates":[{"symbol":"300xxx","features":{}}],
    "strategy_context":{"strategy_id":"reseal_v1","data_quality":{"is_degraded":false}}
  }
}
```
**期望**
- action：BLOCK
- warnings：symbol not in candidates

---

## 11. 验收标准（MVP）
1) 输出都是纯 JSON，满足 schema。  
2) 降级生效：is_degraded 或 risk_light=RED 时不出现 ALLOW。  
3) triggers 至少 6 条，且包含阈值对比；exit_rules ≥ 3。  
4) 能走通“拉 input_bundle → LLM → 回写 apply_output”。  
5) App 能把输出落库并绑定 snapshot_id，前端能看到卡片。  

---

## 12. 交付物清单
### 12.1 平台 Agent 侧
- MarketState workflow（必做）
- SignalExplain workflow（必做）
- JSON 校验/修复节点（建议）
- Secrets：APP_BASE_URL、APP_API_KEY（可选）

### 12.2 App 侧
- `GET /api/agent/input_bundle` ✅ 已实现
- `POST /api/agent/apply_output` ✅ 已实现
- snapshot_id 绑定逻辑 ✅ 已实现（强制）
- WS 推送 ✅ 已实现

---

## 13. 详细实现指南（Coze/Dify 落地）

### 13.1 Coze 实现步骤

#### 步骤 1：创建 Bot
1. 登录 [Coze](https://www.coze.cn) 或 [Coze.com](https://www.coze.com)
2. 创建新 Bot，命名如 "A股打板助手-SignalExplain"
3. 选择模型（推荐 DeepSeek-V3 或 GPT-4o）

#### 步骤 2：配置插件（HTTP 工具）
创建两个 HTTP 插件：

**插件1: GetInputBundle**
```yaml
名称: GetInputBundle
方法: GET
URL: http://YOUR_APP_IP:8000/api/agent/input_bundle
参数:
  - symbol: string (可选)
  - strategy_id: string (可选)
```

**插件2: ApplyOutput**
```yaml
名称: ApplyOutput
方法: POST
URL: http://YOUR_APP_IP:8000/api/agent/apply_output
Headers:
  Content-Type: application/json
Body: JSON (由 LLM 生成)
```

#### 步骤 3：配置工作流

```
[开始] 
   ↓
[GetInputBundle] → 获取 input_bundle
   ↓
[LLM节点] → 生成 SignalExplain payload
   ↓
[JSON校验] → 确保输出格式正确
   ↓
[ApplyOutput] → 回写到 App
   ↓
[结束] → 返回摘要
```

#### 步骤 4：LLM 节点 Prompt 模板

```markdown
# 角色
你是一个 A股打板策略分析助手，负责根据市场数据和股票特征生成交易提示卡。

# 任务
分析输入数据，为指定股票生成 SignalExplain 输出。

# 输入数据
{{input_bundle}}

# 目标股票
{{symbol}}

# 策略规则 (reseal_v1 回封主策略)
ALLOW 条件（全部满足）：
- risk_light != RED
- bomb_rate <= 0.30
- reseal_speed_sec <= 60
- reseal_stable_min >= 1
- slope_5m >= 0.25
- pullback_5m <= 0.18
- amt >= 80,000,000
- open_count_30m <= 3

# 强制规则
1. 如果 data_quality.is_degraded == true，必须输出 WATCH 或 BLOCK
2. 如果 risk_light == RED，必须输出 BLOCK
3. confidence < 0.6 时不得输出 ALLOW

# 输出格式（严格 JSON，不要任何解释文字）
{
  "agent": "SignalExplain",
  "version": "0.1.0",
  "ts": "当前时间ISO格式",
  "symbol": "股票代码",
  "strategy_id": "reseal_v1",
  "action": "WATCH|ALLOW|BLOCK",
  "confidence": 0.0-1.0,
  "triggers": [
    {"name": "环境门槛", "status": "PASS|FAIL|MISSING", "detail": "具体说明"},
    {"name": "回封速度", "status": "PASS|FAIL|MISSING", "detail": "具体说明"},
    ...至少6条
  ],
  "plan": {
    "max_single_position": 0.0-0.15,
    "entry_note": "一句话入场说明",
    "exit_rules": ["退出条件1", "退出条件2", "退出条件3"]
  },
  "risks": ["风险点1", "风险点2"],
  "one_liner": "一句话总结",
  "snapshot_hint": {"should_create_snapshot": true, "snapshot_tags": ["标签"]},
  "warnings": []
}
```

### 13.2 Dify 实现步骤

#### 步骤 1：创建应用
1. 登录 [Dify](https://dify.ai)
2. 创建 "工作流" 类型应用
3. 命名如 "A股打板-SignalExplain"

#### 步骤 2：配置 HTTP 请求节点

**节点1: 获取输入**
- 类型: HTTP 请求
- 方法: GET
- URL: `http://YOUR_APP_IP:8000/api/agent/input_bundle?symbol={{symbol}}`

**节点2: LLM 处理**
- 类型: LLM
- 模型: DeepSeek / GPT-4
- System Prompt: 使用上述 Coze 的 Prompt 模板

**节点3: 回写输出**
- 类型: HTTP 请求
- 方法: POST
- URL: `http://YOUR_APP_IP:8000/api/agent/apply_output`
- Body: `{"type": "SignalExplain", "payload": {{llm_output}}}`

#### 步骤 3：配置变量
- `symbol`: 输入变量，股票代码
- `strategy_id`: 输入变量，策略ID（默认 reseal_v1）

### 13.3 本地测试（无需 Coze/Dify）

可以直接用 curl 测试完整流程：

```bash
# 1. 启动 App
cd /path/to/BigA
./start.sh

# 2. 获取输入数据
curl -s "http://localhost:8000/api/agent/input_bundle?symbol=300058" | jq .

# 3. 模拟 Agent 输出（手动构造）
curl -X POST http://localhost:8000/api/agent/apply_output \
  -H "Content-Type: application/json" \
  -d '{
    "type": "SignalExplain",
    "payload": {
      "agent": "SignalExplain",
      "version": "0.1.0",
      "ts": "2026-01-12T19:30:00+08:00",
      "symbol": "300058",
      "strategy_id": "reseal_v1",
      "action": "WATCH",
      "confidence": 0.72,
      "triggers": [
        {"name": "环境门槛", "status": "PASS", "detail": "YELLOW灯，炸板率0.22<=0.30"},
        {"name": "回封速度", "status": "PASS", "detail": "45s<=60s"},
        {"name": "稳定性", "status": "PASS", "detail": "稳定>=1min"},
        {"name": "强度", "status": "PASS", "detail": "slope_5m=0.63>=0.25"},
        {"name": "回撤", "status": "PASS", "detail": "pullback=0.12<=0.18"},
        {"name": "成交额", "status": "PASS", "detail": "amt=1.2亿>=0.8亿"}
      ],
      "plan": {
        "max_single_position": 0.10,
        "entry_note": "黄灯环境，小仓位观察，回封稳定后可介入",
        "exit_rules": [
          "开板30s不回封立即放弃",
          "回撤超过0.20停止追",
          "风险灯转红停止新增"
        ]
      },
      "risks": ["黄灯环境波动加大", "题材持续性待观察"],
      "one_liner": "回封质量达标，黄灯小仓位允许，严格执行失败条件",
      "snapshot_hint": {"should_create_snapshot": true, "snapshot_tags": ["reseal", "AI应用"]},
      "warnings": []
    }
  }'

# 4. 检查结果
curl -s http://localhost:8000/api/alerts?limit=1 | jq .
```

### 13.4 内网穿透（可选）

如果 Coze/Dify 在云端，需要穿透本地服务：

**方案1: ngrok**
```bash
ngrok http 8000
# 获取公网地址如 https://xxxx.ngrok.io
# 在 Coze/Dify 中使用该地址
```

**方案2: frp**
```bash
# 配置 frpc.ini
[biga]
type = http
local_port = 8000
custom_domains = biga.your-domain.com
```

**方案3: 云服务器部署**
```bash
# 直接部署到云服务器
scp -r BigA user@server:/opt/
ssh user@server "cd /opt/BigA && ./start.sh"
```

---

## 14. 常见问题

### Q1: Agent 输出不是纯 JSON 怎么办？
A: 在 LLM 节点后加 JSON 校验/修复节点，或使用模型的 JSON Mode。

### Q2: 如何处理超时？
A: App 侧接口超时默认 30s，可在 Coze/Dify 设置重试。

### Q3: 如何调试？
A: 
1. 先用 `/api/agent/test` 测试连通性
2. 用 `/api/agent/input_bundle` 查看输入数据
3. 手动构造 payload 测试 `/api/agent/apply_output`

### Q4: 安全考虑？
A: 生产环境建议：
1. 添加 API Key 鉴权
2. 使用 HTTPS
3. 限制 IP 白名单

### Q5: 如何让 Agent 执行交易？
A: App 提供了交易接口，Agent 可以调用：

```bash
# 获取当前交易状态
curl http://localhost:8000/api/trading/status

# 执行买入（模拟盘）
curl -X POST http://localhost:8000/api/trading/execute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "300058",
    "action": "BUY",
    "price": 15.50,
    "shares": 1000,
    "reason": "回封信号触发"
  }'

# 执行卖出
curl -X POST http://localhost:8000/api/trading/execute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "300058",
    "action": "SELL",
    "price": 16.20,
    "shares": 1000,
    "reason": "止盈"
  }'
```

**注意：**
- 默认为模拟盘模式，交易不会实际执行
- 实盘需要配置券商 API 并切换模式
- 建议 Agent 只在 SignalExplain.action == ALLOW 时才考虑执行

### Q6: 如何获取市场情绪数据？
A: 使用情绪分析接口：

```bash
curl http://localhost:8000/api/market/sentiment | jq .
```

返回示例：
```json
{
  "sentiment_score": 45,
  "sentiment_grade": "C",
  "sentiment_text": "中性",
  "risk_light": "YELLOW",
  "rise_fall_ratio": 1.2,
  "sh_pct_change": -0.64,
  "cyb_pct_change": -1.96,
  "total_amount": 8500,
  "needs_agent_analysis": false,
  "agent_analysis_reasons": []
}
```

---
