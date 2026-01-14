# 华泰证券接入指南（Mac 用户）

## 方案一：云服务器 + QMT（推荐 ⭐⭐⭐⭐⭐）

### 优点
- 7x24 小时运行，不影响本地电脑
- 稳定可靠
- 可远程管理

### 成本
- 阿里云/腾讯云 Windows 服务器：¥50-100/月
- 配置建议：2核4G、40G SSD

### 配置步骤

#### 1. 购买云服务器

**阿里云 ECS：**
```
地域：上海/杭州（延迟低）
镜像：Windows Server 2019 数据中心版
规格：ecs.t6-c1m2.large（2核4G）
带宽：按流量计费，1Mbps 起
```

**腾讯云 CVM：**
```
地域：上海
镜像：Windows Server 2019
规格：S5.MEDIUM4（2核4G）
```

#### 2. 连接服务器

Mac 上使用 Microsoft Remote Desktop：
```bash
# 安装
brew install --cask microsoft-remote-desktop

# 或从 App Store 下载
```

#### 3. 在服务器上安装 QMT

1. 联系华泰客户经理开通 QMT 权限
2. 下载安装 QMT 客户端
3. 登录并保持运行

#### 4. 安装 Python 环境

```powershell
# 下载 Python 3.10
# https://www.python.org/downloads/

# 安装 xtquant SDK
pip install xtquant
```

#### 5. 部署本项目

```powershell
# 克隆项目
git clone https://github.com/TianxiangDU/BigA_Proj.git
cd BigA_Proj

# 安装依赖
pip install -r backend/requirements.txt

# 配置华泰
# 编辑 configs/broker_huatai.yaml

# 启动后端
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000
```

#### 6. 本地连接

在 Mac 上修改前端配置，连接云服务器：

```typescript
// frontend/lib/api.ts
const API_BASE = 'http://你的服务器IP:8000'
```

---

## 方案二：聚宽/掘金量化平台（⭐⭐⭐⭐）

使用第三方量化平台，它们已经对接好了华泰证券。

### 聚宽（JoinQuant）

**官网：** https://www.joinquant.com

**特点：**
- 支持华泰证券实盘
- 有免费额度
- 提供 API 接口

**对接方式：**
1. 在聚宽创建策略
2. 通过 Webhook 接收本项目的信号
3. 聚宽执行实际交易

```python
# 聚宽策略示例
def handle_data(context, data):
    # 接收外部信号
    signals = get_external_signals()
    
    for signal in signals:
        if signal['action'] == 'BUY':
            order(signal['symbol'], signal['shares'])
```

### 掘金量化（Myquant）

**官网：** https://www.myquant.cn

**特点：**
- 支持多家券商（含华泰）
- 本地化部署
- API 功能强大

---

## 方案三：Webhook + 手动下单（⭐⭐⭐）

最简单的方案：App 发送提醒，你手动在涨乐财富通下单。

### 配置

1. **添加企业微信/钉钉机器人**

```python
# backend/notifications/webhook.py
import requests

def send_alert(symbol: str, action: str, price: float, reason: str):
    """发送交易提醒到手机"""
    webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
    
    message = f"""
    🚨 打板信号
    
    股票：{symbol}
    动作：{action}
    价格：{price}
    原因：{reason}
    
    请在涨乐财富通手动操作
    """
    
    requests.post(webhook_url, json={
        "msgtype": "text",
        "text": {"content": message}
    })
```

2. **在涨乐财富通设置条件单**

利用华泰的条件单功能，预设好触发条件。

---

## 方案四：Parallels 虚拟机（⭐⭐⭐）

在 Mac 上运行 Windows 虚拟机。

### 要求
- Apple Silicon Mac：Parallels Desktop（¥600+）
- Intel Mac：可用免费的 VirtualBox

### 注意
- 占用本机资源
- 需要保持电脑开机

---

## 方案五：华泰 MATIC API（机构用户）

如果你是机构用户或私募，可以申请华泰的 MATIC 程序化交易接口。

**要求：**
- 机构资质
- 一定的资产规模

**优势：**
- 官方 API，稳定可靠
- 支持 Linux/Mac

---

## 推荐方案

### 个人用户
1. **首选**：云服务器 + QMT（¥50/月，稳定可靠）
2. **次选**：Webhook 提醒 + 手动下单（免费，半自动）

### 有编程基础
- 聚宽/掘金平台（学习曲线适中）

### 资金量大（>100万）
- 联系华泰开通 QMT 或 MATIC

---

## QMT 开通条件

华泰证券 QMT 开通要求（可能有变化，以客户经理为准）：

1. 账户资产 >= 50万 或
2. 近 20 个交易日日均资产 >= 50万 或
3. 期权交易权限

联系你的客户经理咨询具体要求。

---

## 常见问题

### Q: 云服务器安全吗？
A: 
- 使用安全组限制 IP 访问
- 定期更换密码
- 开启云盾防护

### Q: QMT 需要一直开着吗？
A: 是的，QMT 需要保持登录状态才能接收行情和执行交易。

### Q: 延迟会影响打板吗？
A: 云服务器选择上海/杭州地域，延迟在 10ms 以内，对打板影响很小。

### Q: 如果云服务器宕机怎么办？
A: 
- 设置云监控告警
- 配置自动重启
- 关键时段保持监控
