"""
Webhook 通知模块
支持企业微信、钉钉、飞书、Bark等
"""
import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import httpx
from loguru import logger


class WebhookNotifier:
    """
    Webhook 通知器
    
    支持多个通知渠道
    """
    
    def __init__(self):
        self.channels: Dict[str, Dict] = {}
        self._load_from_env()
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 企业微信机器人
        if os.getenv('WECOM_WEBHOOK'):
            self.add_channel('wecom', {
                'type': 'wecom',
                'webhook': os.getenv('WECOM_WEBHOOK')
            })
        
        # 钉钉机器人
        if os.getenv('DINGTALK_WEBHOOK'):
            self.add_channel('dingtalk', {
                'type': 'dingtalk',
                'webhook': os.getenv('DINGTALK_WEBHOOK'),
                'secret': os.getenv('DINGTALK_SECRET')  # 可选，签名密钥
            })
        
        # 飞书机器人
        if os.getenv('FEISHU_WEBHOOK'):
            self.add_channel('feishu', {
                'type': 'feishu',
                'webhook': os.getenv('FEISHU_WEBHOOK')
            })
        
        # Bark (iOS)
        if os.getenv('BARK_URL'):
            self.add_channel('bark', {
                'type': 'bark',
                'url': os.getenv('BARK_URL')
            })
        
        # Telegram
        if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
            self.add_channel('telegram', {
                'type': 'telegram',
                'token': os.getenv('TELEGRAM_BOT_TOKEN'),
                'chat_id': os.getenv('TELEGRAM_CHAT_ID')
            })
    
    def add_channel(self, name: str, config: Dict):
        """添加通知渠道"""
        self.channels[name] = config
        logger.info(f"[Webhook] 添加通知渠道: {name}")
    
    async def send(self, title: str, content: str, level: str = 'info') -> Dict[str, bool]:
        """
        发送通知到所有渠道
        
        Args:
            title: 标题
            content: 内容
            level: 级别 (info/warning/error/critical)
        
        Returns:
            各渠道发送结果
        """
        results = {}
        
        for name, config in self.channels.items():
            try:
                success = await self._send_to_channel(name, config, title, content, level)
                results[name] = success
            except Exception as e:
                logger.error(f"[Webhook] 发送到 {name} 失败: {e}")
                results[name] = False
        
        return results
    
    async def _send_to_channel(
        self, 
        name: str, 
        config: Dict, 
        title: str, 
        content: str, 
        level: str
    ) -> bool:
        """发送到指定渠道"""
        channel_type = config.get('type')
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            if channel_type == 'wecom':
                return await self._send_wecom(client, config, title, content)
            elif channel_type == 'dingtalk':
                return await self._send_dingtalk(client, config, title, content)
            elif channel_type == 'feishu':
                return await self._send_feishu(client, config, title, content)
            elif channel_type == 'bark':
                return await self._send_bark(client, config, title, content, level)
            elif channel_type == 'telegram':
                return await self._send_telegram(client, config, title, content)
            else:
                logger.warning(f"[Webhook] 未知渠道类型: {channel_type}")
                return False
    
    async def _send_wecom(
        self, 
        client: httpx.AsyncClient, 
        config: Dict, 
        title: str, 
        content: str
    ) -> bool:
        """发送到企业微信"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n\n{content}"
            }
        }
        
        resp = await client.post(config['webhook'], json=payload)
        result = resp.json()
        
        if result.get('errcode') == 0:
            logger.debug(f"[Webhook] 企业微信发送成功")
            return True
        else:
            logger.error(f"[Webhook] 企业微信发送失败: {result}")
            return False
    
    async def _send_dingtalk(
        self, 
        client: httpx.AsyncClient, 
        config: Dict, 
        title: str, 
        content: str
    ) -> bool:
        """发送到钉钉"""
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}"
            }
        }
        
        webhook = config['webhook']
        
        # 如果有签名密钥，需要加签
        if config.get('secret'):
            import time
            import hmac
            import hashlib
            import base64
            import urllib.parse
            
            timestamp = str(round(time.time() * 1000))
            secret = config['secret']
            string_to_sign = f'{timestamp}\n{secret}'
            hmac_code = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            webhook = f"{webhook}&timestamp={timestamp}&sign={sign}"
        
        resp = await client.post(webhook, json=payload)
        result = resp.json()
        
        if result.get('errcode') == 0:
            logger.debug(f"[Webhook] 钉钉发送成功")
            return True
        else:
            logger.error(f"[Webhook] 钉钉发送失败: {result}")
            return False
    
    async def _send_feishu(
        self, 
        client: httpx.AsyncClient, 
        config: Dict, 
        title: str, 
        content: str
    ) -> bool:
        """发送到飞书"""
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    }
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content
                    }
                ]
            }
        }
        
        resp = await client.post(config['webhook'], json=payload)
        result = resp.json()
        
        if result.get('code') == 0:
            logger.debug(f"[Webhook] 飞书发送成功")
            return True
        else:
            logger.error(f"[Webhook] 飞书发送失败: {result}")
            return False
    
    async def _send_bark(
        self, 
        client: httpx.AsyncClient, 
        config: Dict, 
        title: str, 
        content: str,
        level: str
    ) -> bool:
        """发送到 Bark (iOS)"""
        # Bark 支持不同的声音和图标
        sound = 'minuet' if level == 'critical' else 'glass'
        
        url = f"{config['url']}/{title}/{content}?sound={sound}"
        
        resp = await client.get(url)
        
        if resp.status_code == 200:
            logger.debug(f"[Webhook] Bark 发送成功")
            return True
        else:
            logger.error(f"[Webhook] Bark 发送失败: {resp.text}")
            return False
    
    async def _send_telegram(
        self, 
        client: httpx.AsyncClient, 
        config: Dict, 
        title: str, 
        content: str
    ) -> bool:
        """发送到 Telegram"""
        url = f"https://api.telegram.org/bot{config['token']}/sendMessage"
        
        payload = {
            "chat_id": config['chat_id'],
            "text": f"*{title}*\n\n{content}",
            "parse_mode": "Markdown"
        }
        
        resp = await client.post(url, json=payload)
        result = resp.json()
        
        if result.get('ok'):
            logger.debug(f"[Webhook] Telegram 发送成功")
            return True
        else:
            logger.error(f"[Webhook] Telegram 发送失败: {result}")
            return False


# 全局通知器实例
_notifier: Optional[WebhookNotifier] = None


def get_notifier() -> WebhookNotifier:
    """获取通知器实例"""
    global _notifier
    if _notifier is None:
        _notifier = WebhookNotifier()
    return _notifier


async def send_trade_alert(
    symbol: str,
    name: str,
    action: str,
    price: float,
    reason: str,
    score: float = None,
    risk_light: str = None
) -> Dict[str, bool]:
    """
    发送交易提醒
    
    Args:
        symbol: 股票代码
        name: 股票名称
        action: 动作 (ALLOW/WATCH/BLOCK)
        price: 当前价格
        reason: 提示原因
        score: 综合评分
        risk_light: 风险灯
    """
    notifier = get_notifier()
    
    # 构建消息
    action_emoji = {
        'ALLOW': '🟢 可操作',
        'WATCH': '🟡 观察',
        'BLOCK': '🔴 禁止'
    }.get(action, action)
    
    light_emoji = {
        'GREEN': '🟢',
        'YELLOW': '🟡',
        'RED': '🔴'
    }.get(risk_light, '')
    
    title = f"📈 打板信号 | {symbol} {name}"
    
    content = f"""
**{action_emoji}**

- 股票：{symbol} {name}
- 价格：{price:.2f}
- 评分：{score:.0f if score else '-'}
- 风险灯：{light_emoji} {risk_light or '-'}

**提示：**
{reason}

---
*{datetime.now().strftime('%H:%M:%S')} 请在涨乐财富通操作*
"""
    
    level = 'critical' if action == 'ALLOW' else 'info'
    
    return await notifier.send(title, content.strip(), level)


# 同步版本（方便非异步环境调用）
def send_trade_alert_sync(
    symbol: str,
    name: str,
    action: str,
    price: float,
    reason: str,
    **kwargs
) -> Dict[str, bool]:
    """同步版本的交易提醒"""
    return asyncio.run(send_trade_alert(symbol, name, action, price, reason, **kwargs))
