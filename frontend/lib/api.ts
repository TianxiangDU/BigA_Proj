// API 客户端

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 通用 fetch 封装
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`)
  }

  return response.json()
}

// ==================== API 方法 ====================

export const api = {
  // 市场仪表盘
  getDashboard: () => fetchAPI<any>('/api/market/dashboard'),

  // 候选池
  getCandidates: (strategyId?: string, top: number = 30) => {
    const params = new URLSearchParams()
    if (strategyId) params.append('strategy_id', strategyId)
    params.append('top', top.toString())
    return fetchAPI<any>(`/api/candidates?${params}`)
  },

  // 提示卡
  getAlerts: (limit: number = 200, strategyId?: string) => {
    const params = new URLSearchParams()
    params.append('limit', limit.toString())
    if (strategyId) params.append('strategy_id', strategyId)
    return fetchAPI<any>(`/api/alerts?${params}`)
  },

  // 更新提示卡标签
  updateAlertLabel: (alertId: string, label: string) =>
    fetchAPI<any>(`/api/alerts/${alertId}/label`, {
      method: 'PATCH',
      body: JSON.stringify({ label }),
    }),

  // 持仓
  getPositions: () => fetchAPI<any>('/api/portfolio/positions'),

  addPosition: (position: { symbol: string; name?: string; qty: number; avg_cost: number }) =>
    fetchAPI<any>('/api/portfolio/positions', {
      method: 'POST',
      body: JSON.stringify(position),
    }),

  deletePosition: (symbol: string) =>
    fetchAPI<any>(`/api/portfolio/positions/${symbol}`, {
      method: 'DELETE',
    }),

  // 风控
  getRiskState: () => fetchAPI<any>('/api/risk/state'),

  // 复盘
  getSnapshotReplay: (snapshotId: string) =>
    fetchAPI<any>(`/api/replay/snapshot/${snapshotId}`),

  getDailySummary: (date?: string) => {
    const params = date ? `?date=${date}` : ''
    return fetchAPI<any>(`/api/replay/daily${params}`)
  },

  analyzeFailures: (days: number = 7) =>
    fetchAPI<any>(`/api/replay/failures?days=${days}`),

  compareStrategies: (days: number = 30) =>
    fetchAPI<any>(`/api/replay/strategies?days=${days}`),

  // 策略
  getStrategies: () => fetchAPI<any>('/api/strategies'),

  activateStrategy: (strategyId: string) =>
    fetchAPI<any>(`/api/strategies/${strategyId}/activate`, {
      method: 'POST',
    }),

  reloadStrategies: () =>
    fetchAPI<any>('/api/settings/strategies/reload', {
      method: 'POST',
    }),

  // 自选股
  getWatchlist: () => fetchAPI<any>('/api/watchlist'),

  addToWatchlist: (symbol: string, name?: string) =>
    fetchAPI<any>(`/api/watchlist/${symbol}?name=${name || ''}`, {
      method: 'POST',
    }),

  removeFromWatchlist: (symbol: string) =>
    fetchAPI<any>(`/api/watchlist/${symbol}`, {
      method: 'DELETE',
    }),

  // 黑名单
  getBlacklist: () => fetchAPI<any>('/api/blacklist'),

  addToBlacklist: (symbol: string, reason?: string) =>
    fetchAPI<any>(`/api/blacklist/${symbol}?reason=${reason || ''}`, {
      method: 'POST',
    }),

  removeFromBlacklist: (symbol: string) =>
    fetchAPI<any>(`/api/blacklist/${symbol}`, {
      method: 'DELETE',
    }),

  // ==================== 市场情绪 ====================
  
  // 获取增强版市场情绪分析
  getSentiment: () => fetchAPI<any>('/api/market/sentiment'),

  // 获取情绪历史
  getSentimentHistory: (limit: number = 100) =>
    fetchAPI<any>(`/api/market/sentiment/history?limit=${limit}`),

  // ==================== 交易模式 ====================
  
  // 获取交易状态
  getTradingStatus: () => fetchAPI<any>('/api/trading/status'),

  // 切换交易模式
  switchTradingMode: (mode: string, reason?: string) => {
    const params = new URLSearchParams({ mode })
    if (reason) params.append('reason', reason)
    return fetchAPI<any>(`/api/trading/mode?${params}`, { method: 'POST' })
  },

  // 获取交易账户
  getTradingAccount: () => fetchAPI<any>('/api/trading/account'),

  // 重置模拟盘
  resetPaperAccount: (initialCapital: number = 1000000) =>
    fetchAPI<any>(`/api/trading/paper/reset?initial_capital=${initialCapital}`, {
      method: 'POST',
    }),

  // 执行交易
  executeTrade: (trade: {
    symbol: string
    name?: string
    action: 'BUY' | 'SELL'
    price: number
    shares: number
    strategy_id?: string
    reason?: string
  }) =>
    fetchAPI<any>('/api/trading/execute', {
      method: 'POST',
      body: JSON.stringify(trade),
    }),

  // 获取订单
  getOrders: (limit: number = 100) =>
    fetchAPI<any>(`/api/trading/orders?limit=${limit}`),

  // 确认订单
  confirmOrder: (orderId: string) =>
    fetchAPI<any>(`/api/trading/orders/${orderId}/confirm`, { method: 'POST' }),

  // 取消订单
  cancelOrder: (orderId: string) =>
    fetchAPI<any>(`/api/trading/orders/${orderId}/cancel`, { method: 'POST' }),

  // 获取交易记录
  getTrades: (limit: number = 100) =>
    fetchAPI<any>(`/api/trading/trades?limit=${limit}`),

  // 配置实盘
  configureLive: (config: {
    broker: string
    account_id?: string
    require_confirmation?: boolean
    max_single_order?: number
    daily_limit?: number
  }) =>
    fetchAPI<any>('/api/trading/live/configure', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
}

// ==================== WebSocket 客户端 ====================

export class WebSocketClient {
  private ws: WebSocket | null = null
  private reconnectTimer: NodeJS.Timeout | null = null
  private messageHandlers: Set<(data: any) => void> = new Set()

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/stream'
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer)
        this.reconnectTimer = null
      }
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.messageHandlers.forEach((handler) => handler(data))
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    this.ws.onclose = () => {
      console.log('WebSocket disconnected, reconnecting...')
      this.reconnectTimer = setTimeout(() => this.connect(), 3000)
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  subscribe(handler: (data: any) => void) {
    this.messageHandlers.add(handler)
    return () => this.messageHandlers.delete(handler)
  }

  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }
}

export const wsClient = new WebSocketClient()
