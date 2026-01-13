'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import { api, wsClient } from '@/lib/api'
import {
  formatNumber,
  formatPercent,
  formatAmount,
  formatTime,
  getRiskLightClass,
  getRiskLightText,
  getRegimeText,
  getActionClass,
  getActionText,
} from '@/lib/utils'
import { 
  LayoutDashboard, 
  ListFilter, 
  Bell, 
  Wallet, 
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Flame,
  AlertTriangle,
  Filter,
  X,
  ChevronDown,
  ChevronUp,
  Activity,
  Zap,
  DollarSign,
  BarChart3,
  Brain,
  PlayCircle,
  PauseCircle,
  Settings2,
  Clock,
} from 'lucide-react'

// 筛选选项
const EXCHANGE_OPTIONS = [
  { value: 'SH', label: '沪市主板', prefix: '60' },
  { value: 'SZ', label: '深市主板', prefix: '00' },
  { value: 'CYB', label: '创业板', prefix: '30' },
  { value: 'KCB', label: '科创板', prefix: '68' },
  { value: 'BJ', label: '北交所', prefix: '8' },
]

const STOCK_TYPE_OPTIONS = [
  { value: 'normal', label: '普通股' },
  { value: 'st', label: 'ST股' },
]

// 排序选项
const SORT_OPTIONS = [
  { value: 'pct_change', label: '涨幅', desc: true },
  { value: 'amount', label: '成交额', desc: true },
  { value: 'close', label: '现价', desc: true },
  { value: 'symbol', label: '代码', desc: false },
  { value: 'name', label: '名称', desc: false },
]

type SortKey = 'pct_change' | 'amount' | 'close' | 'symbol' | 'name'

type TabType = 'dashboard' | 'pool' | 'alerts' | 'trading'

// 筛选配置类型
interface FilterConfig {
  exchanges: string[]
  showST: boolean
  minAmount: number  // 最小成交额（亿）
}

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard')
  const [dashboard, setDashboard] = useState<any>(null)
  const [candidates, setCandidates] = useState<any[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [riskState, setRiskState] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const [refreshSec, setRefreshSec] = useState(5)
  const [countdown, setCountdown] = useState(0)
  
  // 筛选配置
  const [filterConfig, setFilterConfig] = useState<FilterConfig>({
    exchanges: ['SH', 'SZ', 'CYB', 'KCB'],  // 默认不含北交所
    showST: false,
    minAmount: 0,
  })
  const [showFilter, setShowFilter] = useState(false)
  
  // 情绪分析
  const [sentiment, setSentiment] = useState<any>(null)
  
  // 交易状态
  const [tradingStatus, setTradingStatus] = useState<any>(null)
  const [trades, setTrades] = useState<any[]>([])
  const [orders, setOrders] = useState<any>({ pending: [], history: [] })

  const loadData = useCallback(async () => {
    try {
      const dashboardData = await api.getDashboard()
      setDashboard(dashboardData)
      setRiskState(dashboardData.risk_state)
      setLoading(false)
      
      // 使用后端返回的实际数据获取时间
      if (dashboardData.refresh_config) {
        const fetchTime = dashboardData.refresh_config.last_fetch_time
        if (fetchTime) {
          setLastUpdate(new Date(fetchTime))
        } else {
          setLastUpdate(new Date())
        }
        setRefreshSec(dashboardData.refresh_config.refresh_sec || 5)
        setCountdown(dashboardData.refresh_config.refresh_sec || 5)
      } else {
        setLastUpdate(new Date())
      }
      
      // 并行加载其他数据
      Promise.all([
        api.getCandidates(undefined, 100),
        api.getAlerts(50),
        api.getSentiment().catch(() => null),
        api.getTradingStatus().catch(() => null),
      ]).then(([candidatesData, alertsData, sentimentData, tradingData]) => {
        setCandidates(candidatesData.candidates || [])
        setAlerts(alertsData.alerts || [])
        if (sentimentData) setSentiment(sentimentData)
        if (tradingData) setTradingStatus(tradingData)
      }).catch(e => console.error('加载数据失败:', e))
      
    } catch (error) {
      console.error('加载数据失败:', error)
      setLoading(false)
    }
  }, [])

  const handleRefresh = async () => {
    setRefreshing(true)
    await loadData()
    setRefreshing(false)
  }

  // 筛选函数
  const filterStocks = useCallback((stocks: any[]) => {
    if (!stocks) return []
    
    return stocks.filter(stock => {
      const symbol = stock.symbol || ''
      const name = stock.name || ''
      
      // 交易所筛选
      let matchExchange = false
      for (const ex of filterConfig.exchanges) {
        const opt = EXCHANGE_OPTIONS.find(o => o.value === ex)
        if (opt && symbol.startsWith(opt.prefix)) {
          matchExchange = true
          break
        }
      }
      if (!matchExchange) return false
      
      // ST 筛选
      const isST = name.includes('ST') || name.includes('*')
      if (!filterConfig.showST && isST) return false
      
      // 成交额筛选
      if (filterConfig.minAmount > 0) {
        const amount = stock.amount || 0
        if (amount < filterConfig.minAmount * 100000000) return false
      }
      
      return true
    })
  }, [filterConfig])

  // 倒计时
  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          loadData()
          return refreshSec
        }
        return prev - 1
      })
    }, 1000)
    
    return () => clearInterval(timer)
  }, [loadData, refreshSec])

  // 初始化加载和 WebSocket
  useEffect(() => {
    loadData()
    const wsTimer = setTimeout(() => wsClient.connect(), 1000)
    const unsubscribe = wsClient.subscribe((message) => {
      if (message.type === 'update' || message.type === 'init') {
        const data = message.data
        if (data.dashboard) {
          setDashboard((prev: any) => ({ ...prev, summary: data.dashboard }))
          setLastUpdate(new Date())
        }
        if (data.candidates) setCandidates(data.candidates)
        if (data.alerts) setAlerts(data.alerts)
        if (data.risk_state) setRiskState(data.risk_state)
      }
    })

    return () => {
      clearTimeout(wsTimer)
      unsubscribe()
      wsClient.disconnect()
    }
  }, [loadData])

  if (loading) {
    return (
      <div className="min-h-screen bg-background-secondary flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-rise mx-auto mb-4" />
          <p className="text-muted">正在加载市场数据...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background-secondary pb-20 md:pb-4">
      {/* 顶部导航 */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-gray-100 shadow-sm">
        <div className="max-w-6xl mx-auto">
          {/* 主导航行 */}
          <div className="px-4 h-14 flex items-center justify-between">
            {/* 左侧：Logo + 情绪指示器 */}
            <div className="flex items-center gap-3">
              <h1 className="text-lg font-bold text-gray-800 flex items-center gap-2">
                <Flame className="w-5 h-5 text-rise" />
                <span className="hidden sm:inline">打板提示</span>
              </h1>
              
              {/* 情绪指示器（带hover详情） */}
              <SentimentIndicator 
                sentiment={sentiment}
                dashboard={dashboard}
              />
            </div>
            
            {/* 桌面端导航标签 */}
            <nav className="hidden md:flex items-center bg-gray-50 rounded-lg p-1">
              {[
                { id: 'dashboard', label: '看板', icon: LayoutDashboard },
                { id: 'pool', label: '候选', icon: ListFilter },
                { id: 'alerts', label: '提示', icon: Bell },
                { id: 'trading', label: '交易', icon: Zap },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                    activeTab === tab.id 
                      ? 'bg-white text-gray-900 shadow-sm' 
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              ))}
            </nav>
            
            {/* 右侧：数据时间 + 操作按钮 */}
            <div className="flex items-center gap-2">
              {/* 数据获取时间 */}
              <DataTimestamp 
                lastUpdate={lastUpdate}
                fetchDuration={dashboard?.refresh_config?.last_fetch_duration_ms}
                countdown={countdown}
                refreshSec={refreshSec}
                isTrading={dashboard?.refresh_config?.is_trading}
              />
              
              {/* 筛选按钮 */}
              <button 
                onClick={() => setShowFilter(!showFilter)}
                className={`p-2 rounded-lg transition-colors ${
                  showFilter 
                    ? 'bg-primary/10 text-primary' 
                    : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Filter className="w-5 h-5" />
              </button>
              
              {/* 刷新按钮 */}
              <button 
                onClick={handleRefresh} 
                disabled={refreshing}
                className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                title="刷新数据"
              >
                <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin text-primary' : ''}`} />
              </button>
            </div>
          </div>
        </div>
        
        {/* 筛选面板 */}
        {showFilter && (
          <FilterPanel 
            config={filterConfig} 
            onChange={setFilterConfig}
            onClose={() => setShowFilter(false)}
          />
        )}
      </header>

      {/* 主内容区 */}
      <main className="max-w-6xl mx-auto px-4 py-4">
        {activeTab === 'dashboard' && (
          <DashboardView 
            dashboard={dashboard} 
            candidates={candidates}
            filterStocks={filterStocks}
          />
        )}
        {activeTab === 'pool' && <PoolView candidates={candidates} />}
        {activeTab === 'alerts' && <AlertsView alerts={alerts} onRefresh={loadData} />}
        {activeTab === 'trading' && (
          <TradingView 
            tradingStatus={tradingStatus} 
            riskState={riskState}
            onRefresh={loadData}
          />
        )}
      </main>

      {/* 移动端底部导航 - 简洁设计 */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-white border-t border-gray-100 safe-area-pb">
        <div className="flex items-stretch">
          {[
            { id: 'dashboard', label: '看板', icon: LayoutDashboard },
            { id: 'pool', label: '候选', icon: ListFilter },
            { id: 'alerts', label: '提示', icon: Bell },
            { id: 'trading', label: '交易', icon: Zap },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex-1 flex flex-col items-center justify-center py-2 transition-colors ${
                activeTab === tab.id 
                  ? 'text-primary' 
                  : 'text-gray-400'
              }`}
            >
              <tab.icon className={`w-5 h-5 ${activeTab === tab.id ? 'stroke-2' : ''}`} />
              <span className="text-[10px] mt-0.5 font-medium">{tab.label}</span>
              {activeTab === tab.id && (
                <div className="absolute bottom-0 w-8 h-0.5 bg-primary rounded-full" />
              )}
            </button>
          ))}
        </div>
      </nav>
    </div>
  )
}

// ==================== 筛选面板 ====================

function FilterPanel({ config, onChange, onClose }: {
  config: FilterConfig
  onChange: (config: FilterConfig) => void
  onClose: () => void
}) {
  const toggleExchange = (value: string) => {
    const newExchanges = config.exchanges.includes(value)
      ? config.exchanges.filter(e => e !== value)
      : [...config.exchanges, value]
    onChange({ ...config, exchanges: newExchanges })
  }

  return (
    <div className="border-t border-gray-100 bg-white px-4 py-3">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-sm font-medium">筛选条件</h3>
          <button onClick={onClose} className="text-muted hover:text-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex flex-wrap gap-4">
          {/* 交易所 */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted">板块:</span>
            {EXCHANGE_OPTIONS.map(opt => (
              <button
                key={opt.value}
                onClick={() => toggleExchange(opt.value)}
                className={`filter-tag ${config.exchanges.includes(opt.value) ? 'active' : ''}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          
          {/* ST */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">ST股:</span>
            <button
              onClick={() => onChange({ ...config, showST: !config.showST })}
              className={`filter-tag ${config.showST ? 'active' : ''}`}
            >
              {config.showST ? '显示' : '隐藏'}
            </button>
          </div>
          
          {/* 成交额 */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted">成交额:</span>
            {[0, 1, 5, 10].map(v => (
              <button
                key={v}
                onClick={() => onChange({ ...config, minAmount: v })}
                className={`filter-tag ${config.minAmount === v ? 'active' : ''}`}
              >
                {v === 0 ? '不限' : `>${v}亿`}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ==================== 组件 ====================

function RefreshStatus({ countdown, refreshSec, lastUpdate, isTrading, fetchDuration, fetchCount }: {
  countdown: number
  refreshSec: number
  lastUpdate: Date | null
  isTrading: boolean
  fetchDuration?: number
  fetchCount?: number
}) {
  const formatLastUpdate = (date: Date | null) => {
    if (!date) return '--:--:--'
    return date.toLocaleTimeString('zh-CN', { hour12: false })
  }
  
  // 计算数据新鲜度（秒）
  const dataAge = lastUpdate ? Math.floor((Date.now() - lastUpdate.getTime()) / 1000) : 0
  const isStale = dataAge > 30  // 超过30秒算陈旧
  
  return (
    <div className="hidden sm:flex items-center gap-2 text-xs">
      <div className={`flex items-center gap-1 ${isStale ? 'text-yellow-600' : 'text-muted'}`}>
        <span>数据:</span>
        <span className="font-mono">{formatLastUpdate(lastUpdate)}</span>
        {dataAge > 0 && (
          <span className={`${isStale ? 'text-yellow-600 font-medium' : 'text-muted'}`}>
            ({dataAge}s前)
          </span>
        )}
      </div>
      {fetchDuration !== undefined && (
        <span className="text-muted">
          耗时{fetchDuration}ms
        </span>
      )}
      <div className={`flex items-center gap-1 px-2 py-1 rounded ${
        isTrading ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
      }`}>
        <span>{countdown}s</span>
        <span className="text-[10px]">/ {refreshSec}s</span>
      </div>
      {fetchCount !== undefined && fetchCount > 0 && (
        <span className="text-muted text-[10px]">
          #{fetchCount}
        </span>
      )}
    </div>
  )
}

function SessionBadge({ session }: { session: string }) {
  const config: Record<string, { label: string; active: boolean }> = {
    PRE_OPEN: { label: '集合竞价', active: true },
    MORNING: { label: '上午盘', active: true },
    LUNCH: { label: '午休', active: false },
    AFTERNOON: { label: '下午盘', active: true },
    CLOSED: { label: '已收盘', active: false },
  }
  
  const { label, active } = config[session] || { label: session, active: false }
  
  return (
    <span className={`text-xs px-2 py-1 rounded font-medium ${
      active ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
    }`}>
      {label}
    </span>
  )
}

// ==================== 情绪指示器（带hover详情）====================
function SentimentIndicator({ sentiment, dashboard }: { sentiment: any; dashboard: any }) {
  const [showDetails, setShowDetails] = useState(false)
  
  // 从情绪分析或市场数据获取风险灯
  const riskLight = sentiment?.risk_light || dashboard?.summary?.risk_light || 'GREEN'
  const score = sentiment?.sentiment_score || 50
  const grade = sentiment?.sentiment_grade || 'C'
  const gradeText = sentiment?.sentiment_text || '中性'
  
  // 交易时段
  const session = dashboard?.trading_session || 'CLOSED'
  const sessionConfig: Record<string, { label: string; active: boolean }> = {
    PRE_OPEN: { label: '集合竞价', active: true },
    MORNING: { label: '上午盘', active: true },
    LUNCH: { label: '午休', active: false },
    AFTERNOON: { label: '下午盘', active: true },
    CLOSED: { label: '已收盘', active: false },
  }
  const sessionInfo = sessionConfig[session] || { label: session, active: false }
  
  // 风险灯配置
  const lightConfig: Record<string, { bg: string; glow: string; label: string }> = {
    GREEN: { bg: 'bg-green-500', glow: 'shadow-green-500/50', label: '绿灯' },
    YELLOW: { bg: 'bg-yellow-400', glow: 'shadow-yellow-400/50', label: '黄灯' },
    RED: { bg: 'bg-red-500', glow: 'shadow-red-500/50', label: '红灯' },
  }
  const lc = lightConfig[riskLight] || lightConfig.GREEN
  
  // 情绪分数颜色
  const getScoreColor = (s: number) => {
    if (s >= 70) return 'text-green-600'
    if (s >= 50) return 'text-yellow-600'
    if (s >= 30) return 'text-orange-500'
    return 'text-red-500'
  }
  
  // 判断原因列表
  const getReasons = () => {
    const reasons: string[] = []
    
    // 从情绪分析获取
    if (sentiment?.agent_analysis_reasons?.length > 0) {
      reasons.push(...sentiment.agent_analysis_reasons)
    }
    
    // 基于市场数据补充
    const market = dashboard?.market || {}
    const limitUp = market.limit_up_count || 0
    const limitDown = market.down_limit_count || 0
    const bombRate = market.bomb_rate || 0
    
    if (limitUp > 100) reasons.push(`涨停${limitUp}家，市场热度高`)
    else if (limitUp > 50) reasons.push(`涨停${limitUp}家，市场一般`)
    else if (limitUp < 30) reasons.push(`涨停仅${limitUp}家，市场低迷`)
    
    if (bombRate > 0.4) reasons.push(`炸板率${(bombRate*100).toFixed(0)}%，风险较高`)
    if (limitDown > 30) reasons.push(`跌停${limitDown}家，需警惕`)
    
    // 涨跌比
    if (sentiment?.rise_fall_ratio) {
      if (sentiment.rise_fall_ratio > 2) reasons.push(`涨跌比${sentiment.rise_fall_ratio.toFixed(1)}，多头占优`)
      else if (sentiment.rise_fall_ratio < 0.5) reasons.push(`涨跌比${sentiment.rise_fall_ratio.toFixed(1)}，空头主导`)
    }
    
    return reasons.slice(0, 5)  // 最多显示5条
  }

  return (
    <div className="flex items-center gap-2">
      {/* 交易时段 */}
      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
        sessionInfo.active ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
      }`}>
        {sessionInfo.label}
      </span>
      
      {/* 情绪指示器（带hover） */}
      <div 
        className="relative"
        onMouseEnter={() => setShowDetails(true)}
        onMouseLeave={() => setShowDetails(false)}
      >
        {/* 主显示区域 */}
        <div className="flex items-center gap-1.5 cursor-pointer px-2 py-1 rounded-lg hover:bg-gray-50 transition-colors">
          {/* 风险灯 */}
          <div className={`w-2.5 h-2.5 rounded-full ${lc.bg} shadow-lg ${lc.glow} ${sessionInfo.active ? 'animate-pulse' : ''}`} />
          
          {/* 分数和等级 */}
          <span className={`font-bold text-sm ${getScoreColor(score)}`}>{score}</span>
          <span className="text-xs text-gray-400">{grade}级</span>
        </div>
      
      {/* Hover详情面板 */}
      {showDetails && (
        <div className="absolute top-full left-0 mt-2 w-72 bg-white rounded-xl shadow-xl border border-gray-100 p-4 z-50">
          {/* 头部：分数和等级 */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className={`w-4 h-4 rounded-full ${lc.bg}`} />
              <span className="font-medium text-gray-800">{lc.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-bold ${getScoreColor(score)}`}>{score}</span>
              <span className="text-sm text-gray-500">/ 100</span>
            </div>
          </div>
          
          {/* 情绪等级条 */}
          <div className="mb-3">
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div 
                className={`h-full transition-all ${
                  score >= 70 ? 'bg-green-500' : 
                  score >= 50 ? 'bg-yellow-500' : 
                  score >= 30 ? 'bg-orange-500' : 'bg-red-500'
                }`}
                style={{ width: `${score}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
              <span>极弱</span>
              <span>中性</span>
              <span>极强</span>
            </div>
          </div>
          
          {/* 等级说明 */}
          <div className="text-sm text-gray-600 mb-3 py-2 px-3 bg-gray-50 rounded-lg">
            <span className="font-medium">{grade}级 · {gradeText}</span>
          </div>
          
          {/* 判断原因 */}
          <div className="space-y-1.5">
            <div className="text-xs font-medium text-gray-500 mb-1">判断依据</div>
            {getReasons().length > 0 ? (
              getReasons().map((reason, i) => (
                <div key={i} className="text-xs text-gray-600 flex items-start gap-1.5">
                  <span className="text-gray-400 mt-0.5">•</span>
                  <span>{reason}</span>
                </div>
              ))
            ) : (
              <div className="text-xs text-gray-400">暂无详细数据</div>
            )}
          </div>
          
          {/* Agent分析提示 */}
          {sentiment?.needs_agent_analysis && (
            <div className="mt-3 p-2 bg-purple-50 rounded-lg text-xs text-purple-700 flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5" />
              <span>建议进行深度分析</span>
            </div>
          )}
        </div>
      )}
      </div>
    </div>
  )
}

// ==================== 数据时间戳组件 ====================
function DataTimestamp({ lastUpdate, fetchDuration, countdown, refreshSec, isTrading }: {
  lastUpdate: Date | null
  fetchDuration?: number
  countdown: number
  refreshSec: number
  isTrading?: boolean
}) {
  const formatTime = (date: Date | null) => {
    if (!date) return '--:--'
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
  
  const dataAge = lastUpdate ? Math.floor((Date.now() - lastUpdate.getTime()) / 1000) : 0
  const isStale = dataAge > 30
  
  return (
    <div className="hidden sm:flex items-center gap-2 text-xs">
      {/* 数据时间 */}
      <div className={`flex items-center gap-1 ${isStale ? 'text-yellow-600' : 'text-gray-500'}`}>
        <Clock className="w-3.5 h-3.5" />
        <span className="font-mono">{formatTime(lastUpdate)}</span>
        {fetchDuration && (
          <span className="text-gray-400">({fetchDuration}ms)</span>
        )}
      </div>
      
      {/* 倒计时 */}
      <div className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
        isTrading ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
      }`}>
        {countdown}s
      </div>
    </div>
  )
}

// 增强版风险灯显示（带hover提示）
function RiskLightDisplay({ light, bombRate, limitUpCount, limitDownCount }: {
  light: string
  bombRate?: number
  limitUpCount?: number
  limitDownCount?: number
}) {
  const [showTooltip, setShowTooltip] = useState(false)
  
  const config: Record<string, { 
    bg: string; 
    border: string; 
    text: string; 
    glow: string;
    label: string;
    description: string 
  }> = {
    GREEN: { 
      bg: 'bg-green-500', 
      border: 'border-green-400',
      text: 'text-green-700',
      glow: 'shadow-green-500/50',
      label: '绿灯',
      description: '市场环境良好，可正常操作'
    },
    YELLOW: { 
      bg: 'bg-yellow-400', 
      border: 'border-yellow-300',
      text: 'text-yellow-700',
      glow: 'shadow-yellow-400/50',
      label: '黄灯',
      description: '市场有分歧，需谨慎操作'
    },
    RED: { 
      bg: 'bg-red-500', 
      border: 'border-red-400',
      text: 'text-red-700',
      glow: 'shadow-red-500/50',
      label: '红灯',
      description: '市场环境恶劣，禁止新开仓'
    },
  }
  
  const c = config[light] || config.GREEN
  
  // 生成判断原因
  const reasons: string[] = []
  if (limitUpCount !== undefined) {
    if (limitUpCount > 100) reasons.push(`涨停${limitUpCount}家(强)`)
    else if (limitUpCount > 50) reasons.push(`涨停${limitUpCount}家(中)`)
    else reasons.push(`涨停${limitUpCount}家(弱)`)
  }
  if (bombRate !== undefined) {
    if (bombRate > 0.4) reasons.push(`炸板率${(bombRate*100).toFixed(0)}%(高)`)
    else if (bombRate > 0.25) reasons.push(`炸板率${(bombRate*100).toFixed(0)}%(中)`)
    else reasons.push(`炸板率${(bombRate*100).toFixed(0)}%(低)`)
  }
  if (limitDownCount !== undefined && limitDownCount > 20) {
    reasons.push(`跌停${limitDownCount}家(警告)`)
  }
  
  return (
    <div 
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className={`
        flex items-center gap-2 px-3 py-1.5 rounded-full cursor-help
        ${c.border} border-2 ${c.text} font-semibold
        transition-all duration-300
      `}>
        <div className={`
          w-4 h-4 rounded-full ${c.bg} 
          shadow-lg ${c.glow}
          animate-pulse
        `} />
        <span className="text-sm">{c.label}</span>
      </div>
      
      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute top-full right-0 mt-2 z-50 w-64 p-3 bg-white rounded-lg shadow-xl border text-sm">
          <div className={`font-bold mb-2 ${c.text}`}>{c.label} - {c.description}</div>
          <div className="space-y-1 text-muted">
            <div className="font-medium text-foreground">判断依据：</div>
            {reasons.map((r, i) => (
              <div key={i} className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                {r}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function DashboardView({ dashboard, candidates, filterStocks }: any) {
  const market = dashboard?.market || {}
  const summary = dashboard?.summary || {}
  const dataQuality = dashboard?.data_quality || {}
  const refreshConfig = dashboard?.refresh_config || {}
  const [expandedSection, setExpandedSection] = useState<string | null>('limit_up')
  
  // 应用筛选
  const limitUpStocks = useMemo(() => filterStocks(market.limit_up_stocks || []), [market.limit_up_stocks, filterStocks])
  const limitDownStocks = useMemo(() => filterStocks(market.limit_down_stocks || []), [market.limit_down_stocks, filterStocks])
  const nearLimitUpStocks = useMemo(() => filterStocks(market.near_limit_up_stocks || []), [market.near_limit_up_stocks, filterStocks])

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  // 计算市场整体情绪
  const getMarketMood = () => {
    const limitUp = (market.limit_up_stocks || []).length
    const limitDown = (market.limit_down_stocks || []).length
    const bombRate = market.bomb_rate || 0
    
    if (limitUp > 100 && bombRate < 0.2) return { text: '强势', color: 'text-rise', bg: 'bg-rise/10' }
    if (limitUp > 50 && bombRate < 0.3) return { text: '偏强', color: 'text-orange-500', bg: 'bg-orange-50' }
    if (limitDown > 50 || bombRate > 0.4) return { text: '弱势', color: 'text-fall', bg: 'bg-fall/10' }
    return { text: '震荡', color: 'text-yellow-600', bg: 'bg-yellow-50' }
  }
  
  const mood = getMarketMood()

  return (
    <div className="space-y-4">
      {/* 大盘指数看板 */}
      <div className="card overflow-hidden">
        {/* 指数网格 */}
        <div className="grid grid-cols-3 md:grid-cols-6 divide-x divide-gray-100">
          {(market.indices || []).slice(0, 6).map((idx: any, i: number) => (
            <IndexCard key={idx.code} index={idx} isFirst={i === 0} />
          ))}
        </div>
        
        {(market.indices || []).length === 0 && (
          <div className="text-center text-muted text-sm py-8">
            <Activity className="w-6 h-6 mx-auto mb-2 opacity-50" />
            加载指数数据中...
          </div>
        )}
        
        {/* 数据来源 */}
        <div className="flex items-center justify-between text-[11px] text-gray-400 bg-gray-50/50 px-4 py-2">
          <span>数据源: {refreshConfig.data_source || 'akshare (东方财富)'}</span>
          <span className="font-mono">
            {refreshConfig.last_fetch_time 
              ? new Date(refreshConfig.last_fetch_time).toLocaleTimeString('zh-CN')
              : '--:--:--'}
            {refreshConfig.last_fetch_duration_ms !== undefined && refreshConfig.last_fetch_duration_ms > 0 && (
              <span className="ml-1 opacity-70">({refreshConfig.last_fetch_duration_ms}ms)</span>
            )}
          </span>
        </div>
      </div>

      {/* 市场统计看板 */}
      <div className="grid grid-cols-6 gap-3">
        <div className="stat-card cursor-pointer hover:shadow-md transition-shadow" onClick={() => toggleSection('limit_up')}>
          <div className="stat-value text-rise">{limitUpStocks.length}</div>
          <div className="stat-label">涨停</div>
          {limitUpStocks.length !== (market.limit_up_stocks || []).length && (
            <div className="text-[10px] text-muted">全{(market.limit_up_stocks || []).length}</div>
          )}
        </div>
        <div className="stat-card cursor-pointer hover:shadow-md transition-shadow" onClick={() => toggleSection('limit_down')}>
          <div className="stat-value text-fall">{limitDownStocks.length}</div>
          <div className="stat-label">跌停</div>
          {limitDownStocks.length !== (market.limit_down_stocks || []).length && (
            <div className="text-[10px] text-muted">全{(market.limit_down_stocks || []).length}</div>
          )}
        </div>
        <div className="stat-card cursor-pointer hover:shadow-md transition-shadow" onClick={() => toggleSection('near')}>
          <div className="stat-value text-orange-500">{nearLimitUpStocks.length}</div>
          <div className="stat-label">冲板</div>
          {nearLimitUpStocks.length !== (market.near_limit_up_stocks || []).length && (
            <div className="text-[10px] text-muted">全{(market.near_limit_up_stocks || []).length}</div>
          )}
        </div>
        <div className="stat-card">
          <div className={`stat-value ${(market.bomb_rate || 0) > 0.3 ? 'text-yellow-500' : ''}`}>
            {formatPercent(market.bomb_rate || 0)}
          </div>
          <div className="stat-label">炸板率</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{market.max_streak || '-'}</div>
          <div className="stat-label">连板高度</div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${mood.color}`}>{mood.text}</div>
          <div className="stat-label">情绪</div>
        </div>
      </div>

      {/* 涨停股列表 */}
      <StockListCard
        title="涨停板"
        icon={<TrendingUp className="w-4 h-4 text-rise" />}
        stocks={limitUpStocks}
        totalCount={(market.limit_up_stocks || []).length}
        expanded={expandedSection === 'limit_up'}
        onToggle={() => toggleSection('limit_up')}
        colorType="rise"
      />

      {/* 跌停股列表 */}
      <StockListCard
        title="跌停板"
        icon={<TrendingDown className="w-4 h-4 text-fall" />}
        stocks={limitDownStocks}
        totalCount={(market.limit_down_stocks || []).length}
        expanded={expandedSection === 'limit_down'}
        onToggle={() => toggleSection('limit_down')}
        colorType="fall"
      />

      {/* 冲板中 */}
      <StockListCard
        title="冲板中"
        icon={<AlertTriangle className="w-4 h-4 text-orange-500" />}
        stocks={nearLimitUpStocks}
        totalCount={(market.near_limit_up_stocks || []).length}
        expanded={expandedSection === 'near'}
        onToggle={() => toggleSection('near')}
        colorType="rise"
      />

      {/* 候选池预览 */}
      {candidates.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">
              <Flame className="w-4 h-4 text-orange-500" />
              策略候选 ({candidates.length})
            </h2>
          </div>
          <div className="stock-list max-h-48 overflow-y-auto">
            {candidates.slice(0, 10).map((c: any, i: number) => (
              <div key={c.symbol} className="stock-row">
                <span className="text-muted w-6 text-sm">{i + 1}</span>
                <div className="info">
                  <span className="symbol">{c.symbol}</span>
                  <span className="name">{c.name}</span>
                  <ExchangeTag symbol={c.symbol} />
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{formatNumber(c.total_score, 0)}</span>
                  <span className={`action-badge ${getActionClass(c.action)}`}>
                    {getActionText(c.action)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StockListCard({ title, icon, stocks, totalCount, expanded, onToggle, colorType }: {
  title: string
  icon: React.ReactNode
  stocks: any[]
  totalCount: number
  expanded: boolean
  onToggle: () => void
  colorType: 'rise' | 'fall'
}) {
  const [sortKey, setSortKey] = useState<SortKey>('amount')  // 默认按成交额排序
  const [sortDesc, setSortDesc] = useState(true)
  
  // 排序后的股票列表
  const sortedStocks = useMemo(() => {
    const sorted = [...stocks].sort((a, b) => {
      let aVal = a[sortKey]
      let bVal = b[sortKey]
      
      // 处理字符串排序
      if (sortKey === 'symbol' || sortKey === 'name') {
        aVal = aVal || ''
        bVal = bVal || ''
        return sortDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal)
      }
      
      // 数值排序
      aVal = aVal || 0
      bVal = bVal || 0
      return sortDesc ? bVal - aVal : aVal - bVal
    })
    return sorted
  }, [stocks, sortKey, sortDesc])
  
  const displayStocks = expanded ? sortedStocks : sortedStocks.slice(0, 10)
  const changeColor = colorType === 'rise' ? 'text-rise' : 'text-fall'
  
  const handleSortChange = (key: SortKey) => {
    if (sortKey === key) {
      setSortDesc(!sortDesc)
    } else {
      setSortKey(key)
      const opt = SORT_OPTIONS.find(o => o.value === key)
      setSortDesc(opt?.desc ?? true)
    }
  }
  
  return (
    <div className="card">
      <div className="card-header cursor-pointer" onClick={onToggle}>
        <h2 className="card-title">
          {icon}
          {title} ({stocks.length})
          {stocks.length !== totalCount && (
            <span className="text-xs text-muted font-normal ml-2">
              / 全市场 {totalCount}
            </span>
          )}
        </h2>
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-muted" />
          ) : (
            <ChevronDown className="w-4 h-4 text-muted" />
          )}
        </div>
      </div>
      
      {/* 排序选项 */}
      {stocks.length > 0 && (
        <div className="flex items-center gap-1 px-3 py-2 border-b border-gray-100 text-xs">
          <span className="text-muted mr-1">排序:</span>
          {SORT_OPTIONS.map(opt => (
            <button
              key={opt.value}
              onClick={(e) => { e.stopPropagation(); handleSortChange(opt.value as SortKey) }}
              className={`px-2 py-1 rounded transition-colors ${
                sortKey === opt.value 
                  ? 'bg-primary/10 text-primary font-medium' 
                  : 'text-muted hover:bg-gray-100'
              }`}
            >
              {opt.label}
              {sortKey === opt.value && (
                <span className="ml-0.5">{sortDesc ? '↓' : '↑'}</span>
              )}
            </button>
          ))}
        </div>
      )}
      
      {stocks.length > 0 ? (
        <div className={`stock-list ${expanded ? 'max-h-[500px]' : 'max-h-[300px]'} overflow-y-auto`}>
          {displayStocks.map((stock: any, i: number) => (
            <div key={stock.symbol} className="stock-row">
              <div className={`rank ${i < 3 ? 'top3' : 'normal'}`}>{i + 1}</div>
              <div className="info">
                <span className="symbol">{stock.symbol}</span>
                <span className="name">{stock.name || '-'}</span>
                <ExchangeTag symbol={stock.symbol} />
              </div>
              <div className="price-info">
                <div className={`price ${changeColor}`}>{formatNumber(stock.close, 2)}</div>
                <div className={`change ${changeColor}`}>
                  {colorType === 'fall' ? '' : '+'}{formatPercent(stock.pct_change / 100)}
                </div>
                <div className="amount">{formatAmount(stock.amount)}</div>
              </div>
            </div>
          ))}
          
          {!expanded && stocks.length > 10 && (
            <div className="text-center py-2">
              <button onClick={onToggle} className="text-xs text-muted hover:text-foreground">
                展开查看全部 {stocks.length} 只 ↓
              </button>
            </div>
          )}
        </div>
      ) : (
        <p className="text-muted text-sm py-6 text-center">暂无数据</p>
      )}
    </div>
  )
}

// 大盘指数卡片
function IndexCard({ index, isFirst }: { index: any; isFirst?: boolean }) {
  const pctChange = index.pct_change || 0
  const isUp = pctChange >= 0
  const colorClass = isUp ? 'text-rise' : 'text-fall'
  
  // 简化指数名称
  const shortName = index.short || index.name?.replace('指数', '') || index.name
  
  return (
    <div className={`py-4 px-3 text-center hover:bg-gray-50/50 transition-colors ${isFirst ? '' : ''}`}>
      <div className="text-xs text-gray-500 mb-1.5 font-medium">{shortName}</div>
      <div className={`text-xl font-bold ${colorClass} leading-tight tracking-tight`}>
        {formatNumber(index.close, index.close > 10000 ? 0 : index.close > 1000 ? 0 : 2)}
      </div>
      <div className="mt-1 space-y-0">
        <div className={`text-sm font-semibold ${colorClass}`}>
          {isUp ? '+' : ''}{pctChange.toFixed(2)}%
        </div>
        <div className={`text-[10px] ${colorClass} opacity-80`}>
          {isUp ? '+' : ''}{formatNumber(index.change, 2)}
        </div>
      </div>
    </div>
  )
}

// 交易所标签
function ExchangeTag({ symbol }: { symbol: string }) {
  let label = ''
  let className = ''
  
  if (symbol.startsWith('60')) {
    label = '沪'
    className = 'bg-blue-50 text-blue-600'
  } else if (symbol.startsWith('00')) {
    label = '深'
    className = 'bg-purple-50 text-purple-600'
  } else if (symbol.startsWith('30')) {
    label = '创'
    className = 'bg-orange-50 text-orange-600'
  } else if (symbol.startsWith('68')) {
    label = '科'
    className = 'bg-green-50 text-green-600'
  } else if (symbol.startsWith('8') || symbol.startsWith('4')) {
    label = '北'
    className = 'bg-pink-50 text-pink-600'
  }
  
  if (!label) return null
  
  return (
    <span className={`ml-1 px-1.5 py-0.5 text-[10px] rounded ${className}`}>
      {label}
    </span>
  )
}

function PoolView({ candidates }: { candidates: any[] }) {
  const [filter, setFilter] = useState<string>('')

  const filtered = candidates.filter((c) => {
    if (!filter) return true
    return c.action === filter
  })

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">候选池 ({filtered.length})</h2>
        <div className="flex gap-1">
          {['', 'ALLOW', 'WATCH'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`btn text-xs ${filter === f ? 'btn-primary' : 'btn-secondary'}`}
            >
              {f === '' ? '全部' : getActionText(f)}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>#</th>
              <th>代码</th>
              <th>名称</th>
              <th>板块</th>
              <th>得分</th>
              <th>状态</th>
              <th>涨幅</th>
              <th>成交额</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => (
              <tr key={c.symbol}>
                <td className="text-muted">{i + 1}</td>
                <td className="font-mono font-semibold">{c.symbol}</td>
                <td>{c.name || '-'}</td>
                <td><ExchangeTag symbol={c.symbol} /></td>
                <td className="font-bold">{formatNumber(c.total_score, 1)}</td>
                <td>
                  <span className={`action-badge ${getActionClass(c.action)}`}>
                    {getActionText(c.action)}
                  </span>
                </td>
                <td className={c.features?.pct_change > 0 ? 'text-rise' : 'text-fall'}>
                  {formatPercent(c.features?.pct_change / 100)}
                </td>
                <td>{formatAmount(c.features?.amt)}</td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-muted py-8">暂无数据</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function AlertsView({ alerts, onRefresh }: { alerts: any[]; onRefresh: () => void }) {
  return (
    <div className="space-y-4">
      {alerts.length === 0 ? (
        <div className="card text-center py-12">
          <Bell className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p className="text-muted">暂无提示卡</p>
          <p className="text-xs text-muted mt-2">当有符合条件的交易机会时会显示在这里</p>
        </div>
      ) : (
        alerts.map((alert) => (
          <AlertCard key={alert.alert_id} alert={alert} onRefresh={onRefresh} />
        ))
      )}
    </div>
  )
}

function AlertCard({ alert, onRefresh }: { alert: any; onRefresh: () => void }) {
  const card = alert.card || {}
  const actionClass = alert.action === 'ALLOW' ? 'alert-card-allow' : 
                      alert.action === 'WATCH' ? 'alert-card-watch' : 'alert-card-block'

  const handleLabel = async (label: string) => {
    try {
      await api.updateAlertLabel(alert.alert_id, label)
      onRefresh()
    } catch (error) {
      console.error('更新标签失败:', error)
    }
  }

  return (
    <div className={`alert-card ${actionClass}`}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-lg font-bold">{alert.symbol}</span>
            <span className="text-muted">{alert.name}</span>
            <ExchangeTag symbol={alert.symbol} />
            <span className={`action-badge ${getActionClass(alert.action)}`}>
              {getActionText(alert.action)}
            </span>
          </div>
          <p className="text-sm text-muted">{card.one_liner || alert.one_liner}</p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{formatNumber(card.total_score || alert.total_score, 0)}</div>
          <div className="text-xs text-muted">{formatTime(alert.ts)}</div>
        </div>
      </div>

      <div className="flex gap-2">
        <button onClick={() => handleLabel('success')} className={`btn text-xs ${alert.user_label === 'success' ? 'bg-green-100 text-green-700' : 'btn-secondary'}`}>
          ✓ 成功
        </button>
        <button onClick={() => handleLabel('fail')} className={`btn text-xs ${alert.user_label === 'fail' ? 'bg-red-100 text-red-700' : 'btn-secondary'}`}>
          ✗ 失败
        </button>
        <button onClick={() => handleLabel('skip')} className={`btn text-xs ${alert.user_label === 'skip' ? 'bg-yellow-100 text-yellow-700' : 'btn-secondary'}`}>
          跳过
        </button>
      </div>
    </div>
  )
}

function PortfolioView({ riskState }: { riskState: any }) {
  return (
    <div className="space-y-4">
      <div className="card">
        <h2 className="card-title mb-4">风控状态</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="metric">
            <div className={`metric-value ${riskState?.consecutive_losses >= 2 ? 'text-yellow-500' : ''}`}>
              {riskState?.consecutive_losses || 0}
            </div>
            <div className="metric-label">连亏次数</div>
          </div>
          <div className="metric">
            <div className={`metric-value ${(riskState?.daily_pnl_pct || 0) < 0 ? 'text-fall' : 'text-rise'}`}>
              {formatPercent(riskState?.daily_pnl_pct || 0)}
            </div>
            <div className="metric-label">日内盈亏</div>
          </div>
          <div className="metric">
            <div className="metric-value">{formatPercent(riskState?.total_position || 0)}</div>
            <div className="metric-label">总仓位</div>
          </div>
          <div className="metric">
            <div className={`metric-value ${riskState?.is_stopped ? 'text-rise' : 'text-fall'}`}>
              {riskState?.is_stopped ? '已停' : '正常'}
            </div>
            <div className="metric-label">交易状态</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ==================== 交易视图（合并持仓和交易）====================

function TradingView({ tradingStatus, riskState, onRefresh }: { 
  tradingStatus: any
  riskState: any
  onRefresh: () => void
}) {
  const [activeMode, setActiveMode] = useState(tradingStatus?.mode || 'paper')
  const [switching, setSwitching] = useState(false)
  
  useEffect(() => {
    if (tradingStatus?.mode) {
      setActiveMode(tradingStatus.mode)
    }
  }, [tradingStatus?.mode])
  
  const handleModeSwitch = async (mode: string) => {
    setSwitching(true)
    try {
      await api.switchTradingMode(mode)
      onRefresh()
    } catch (e) {
      console.error('切换模式失败:', e)
    } finally {
      setSwitching(false)
    }
  }
  
  const handleResetPaper = async () => {
    if (confirm('确定要重置模拟盘账户吗？所有持仓和交易记录将被清空。')) {
      try {
        await api.resetPaperAccount()
        onRefresh()
      } catch (e) {
        console.error('重置失败:', e)
      }
    }
  }
  
  const account = tradingStatus?.account || {}
  const isPaper = activeMode === 'paper'
  const isLive = activeMode === 'live'
  
  return (
    <div className="space-y-4">
      {/* 交易模式切换 */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="card-title flex items-center gap-2">
            <Zap className="w-5 h-5 text-primary" />
            交易模式
          </h2>
          <div className="flex items-center gap-2">
            {['paper', 'live', 'disabled'].map((mode) => (
              <button
                key={mode}
                onClick={() => handleModeSwitch(mode)}
                disabled={switching}
                className={`px-3 py-1.5 text-sm rounded-lg font-medium transition-all ${
                  activeMode === mode
                    ? mode === 'paper' 
                      ? 'bg-blue-100 text-blue-700 ring-2 ring-blue-300'
                      : mode === 'live'
                      ? 'bg-green-100 text-green-700 ring-2 ring-green-300'
                      : 'bg-gray-100 text-gray-700 ring-2 ring-gray-300'
                    : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                }`}
              >
                {mode === 'paper' && '🎮 模拟盘'}
                {mode === 'live' && '💰 实盘'}
                {mode === 'disabled' && '🚫 禁用'}
              </button>
            ))}
          </div>
        </div>
        
        {/* 模拟盘账户信息 */}
        {isPaper && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-blue-50 rounded-lg">
                <div className="text-sm text-blue-600 mb-1">总资产</div>
                <div className="text-xl font-bold text-blue-700">
                  {formatAmount(account.total_value || 0)}
                </div>
              </div>
              <div className="p-3 bg-gray-50 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">可用资金</div>
                <div className="text-xl font-bold">
                  {formatAmount(account.cash || 0)}
                </div>
              </div>
              <div className={`p-3 rounded-lg ${(account.total_pnl || 0) >= 0 ? 'bg-rise/10' : 'bg-fall/10'}`}>
                <div className="text-sm text-gray-600 mb-1">累计盈亏</div>
                <div className={`text-xl font-bold ${(account.total_pnl || 0) >= 0 ? 'text-rise' : 'text-fall'}`}>
                  {(account.total_pnl || 0) >= 0 ? '+' : ''}{formatAmount(account.total_pnl || 0)}
                </div>
              </div>
              <div className={`p-3 rounded-lg ${(account.total_pnl_pct || 0) >= 0 ? 'bg-rise/10' : 'bg-fall/10'}`}>
                <div className="text-sm text-gray-600 mb-1">收益率</div>
                <div className={`text-xl font-bold ${(account.total_pnl_pct || 0) >= 0 ? 'text-rise' : 'text-fall'}`}>
                  {(account.total_pnl_pct || 0) >= 0 ? '+' : ''}{formatPercent(account.total_pnl_pct || 0)}
                </div>
              </div>
            </div>
            
            {/* 持仓列表 */}
            {Object.keys(account.positions || {}).length > 0 && (
              <div>
                <h3 className="font-medium mb-2">当前持仓</h3>
                <div className="space-y-2">
                  {Object.values(account.positions || {}).map((pos: any) => (
                    <div key={pos.symbol} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-medium">{pos.symbol}</span>
                        <span className="text-muted text-sm">{pos.name}</span>
                        <span className="text-sm text-gray-500">{pos.shares}股</span>
                      </div>
                      <div className={`font-medium ${(pos.pnl || 0) >= 0 ? 'text-rise' : 'text-fall'}`}>
                        {(pos.pnl || 0) >= 0 ? '+' : ''}{formatAmount(pos.pnl || 0)}
                        <span className="text-xs ml-1">
                          ({(pos.pnl_pct || 0) >= 0 ? '+' : ''}{formatPercent(pos.pnl_pct || 0)})
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div className="flex justify-end">
              <button onClick={handleResetPaper} className="btn btn-secondary text-sm">
                🔄 重置账户
              </button>
            </div>
          </div>
        )}
        
        {/* 实盘提示 */}
        {isLive && (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center gap-2 text-yellow-700 font-medium mb-2">
              <AlertTriangle className="w-5 h-5" />
              实盘交易
            </div>
            <p className="text-sm text-yellow-600">
              实盘交易需要配置券商连接。当前支持 EasyTrader（同花顺等客户端）。
              请在后端配置券商信息后使用。
            </p>
            <div className="mt-3 text-xs text-yellow-500">
              券商: {tradingStatus?.config?.broker || '未配置'} | 
              确认模式: {tradingStatus?.config?.require_confirmation ? '需确认' : '自动'}
            </div>
          </div>
        )}
        
        {/* 禁用状态 */}
        {activeMode === 'disabled' && (
          <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-center">
            <PauseCircle className="w-12 h-12 text-gray-400 mx-auto mb-2" />
            <p className="text-gray-600">交易功能已禁用，仅可查看行情</p>
          </div>
        )}
      </div>
      
      {/* 交易记录 */}
      {isPaper && (account.trades || []).length > 0 && (
        <div className="card">
          <h2 className="card-title mb-3">最近交易</h2>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {(account.trades || []).slice(-10).reverse().map((trade: any, i: number) => (
              <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded text-sm">
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${trade.type === 'BUY' ? 'text-rise' : 'text-fall'}`}>
                    {trade.type === 'BUY' ? '买入' : '卖出'}
                  </span>
                  <span className="font-mono">{trade.symbol}</span>
                  <span className="text-muted">{trade.shares}股 @ {trade.price}</span>
                </div>
                <div className="text-right">
                  {trade.pnl !== undefined && (
                    <span className={trade.pnl >= 0 ? 'text-rise' : 'text-fall'}>
                      {trade.pnl >= 0 ? '+' : ''}{formatAmount(trade.pnl)}
                    </span>
                  )}
                  <span className="text-xs text-muted ml-2">
                    {new Date(trade.ts).toLocaleTimeString('zh-CN')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* 风控状态 */}
      <div className="card">
        <h2 className="card-title mb-4 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-500" />
          风控状态
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-3 bg-gray-50 rounded-lg text-center">
            <div className={`text-xl font-bold ${(riskState?.consecutive_losses || 0) >= 2 ? 'text-yellow-500' : 'text-gray-700'}`}>
              {riskState?.consecutive_losses || 0}
            </div>
            <div className="text-xs text-muted mt-1">连亏次数</div>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg text-center">
            <div className={`text-xl font-bold ${(riskState?.daily_pnl_pct || 0) < 0 ? 'text-fall' : 'text-rise'}`}>
              {formatPercent(riskState?.daily_pnl_pct || 0)}
            </div>
            <div className="text-xs text-muted mt-1">日内盈亏</div>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg text-center">
            <div className="text-xl font-bold text-gray-700">
              {formatPercent(riskState?.total_position || 0)}
            </div>
            <div className="text-xs text-muted mt-1">总仓位</div>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg text-center">
            <div className={`text-xl font-bold ${riskState?.is_stopped ? 'text-rise' : 'text-green-600'}`}>
              {riskState?.is_stopped ? '已停止' : '正常'}
            </div>
            <div className="text-xs text-muted mt-1">交易状态</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// 情绪分析卡片（已移至顶栏，保留备用）
function SentimentCard({ sentiment }: { sentiment: any }) {
  if (!sentiment) {
    return (
      <div className="card">
        <div className="text-center text-muted py-8">
          <Brain className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>情绪分析加载中...</p>
        </div>
      </div>
    )
  }
  
  const score = sentiment.sentiment_score || 50
  const grade = sentiment.sentiment_grade || 'C'
  const text = sentiment.sentiment_text || '中性'
  const riskLight = sentiment.risk_light || 'YELLOW'
  
  // 情绪分数颜色
  const getScoreColor = (s: number) => {
    if (s >= 70) return 'text-rise'
    if (s >= 50) return 'text-orange-500'
    if (s >= 30) return 'text-yellow-600'
    return 'text-fall'
  }
  
  // 情绪等级背景
  const getGradeBg = (g: string) => {
    switch (g) {
      case 'A': return 'bg-green-100 text-green-700'
      case 'B': return 'bg-green-50 text-green-600'
      case 'C': return 'bg-yellow-50 text-yellow-700'
      case 'D': return 'bg-orange-50 text-orange-600'
      case 'E': return 'bg-red-50 text-red-600'
      default: return 'bg-gray-50 text-gray-600'
    }
  }
  
  return (
    <div className="card bg-gradient-to-r from-purple-50 to-indigo-50">
      <div className="flex items-center justify-between mb-4">
        <h2 className="card-title flex items-center gap-2">
          <Brain className="w-5 h-5 text-purple-600" />
          市场情绪分析
        </h2>
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-sm font-bold ${getGradeBg(grade)}`}>
            {grade}级 {text}
          </span>
          {sentiment.needs_agent_analysis && (
            <span className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full animate-pulse">
              🤖 需深度分析
            </span>
          )}
        </div>
      </div>
      
      {/* 情绪分数仪表 */}
      <div className="flex items-center gap-6 mb-4">
        <div className="text-center">
          <div className={`text-4xl font-bold ${getScoreColor(score)}`}>{score}</div>
          <div className="text-xs text-muted">情绪分数</div>
        </div>
        
        {/* 进度条 */}
        <div className="flex-1">
          <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all ${
                score >= 70 ? 'bg-green-500' : 
                score >= 50 ? 'bg-yellow-500' : 
                score >= 30 ? 'bg-orange-500' : 'bg-red-500'
              }`}
              style={{ width: `${score}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-muted mt-1">
            <span>极弱</span>
            <span>中性</span>
            <span>极强</span>
          </div>
        </div>
      </div>
      
      {/* 多维度指标 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-2 bg-white/50 rounded">
          <div className="text-xs text-muted">涨跌比</div>
          <div className={`font-bold ${sentiment.rise_fall_ratio > 1 ? 'text-rise' : 'text-fall'}`}>
            {sentiment.rise_fall_ratio?.toFixed(2) || '-'}
          </div>
        </div>
        <div className="p-2 bg-white/50 rounded">
          <div className="text-xs text-muted">上证涨跌</div>
          <div className={`font-bold ${(sentiment.sh_pct_change || 0) >= 0 ? 'text-rise' : 'text-fall'}`}>
            {sentiment.sh_pct_change >= 0 ? '+' : ''}{sentiment.sh_pct_change?.toFixed(2) || 0}%
          </div>
        </div>
        <div className="p-2 bg-white/50 rounded">
          <div className="text-xs text-muted">创业板涨跌</div>
          <div className={`font-bold ${(sentiment.cyb_pct_change || 0) >= 0 ? 'text-rise' : 'text-fall'}`}>
            {sentiment.cyb_pct_change >= 0 ? '+' : ''}{sentiment.cyb_pct_change?.toFixed(2) || 0}%
          </div>
        </div>
        <div className="p-2 bg-white/50 rounded">
          <div className="text-xs text-muted">成交额</div>
          <div className="font-bold">{formatAmount(sentiment.total_amount * 100000000)}</div>
        </div>
      </div>
      
      {/* Agent 分析原因 */}
      {sentiment.needs_agent_analysis && sentiment.agent_analysis_reasons?.length > 0 && (
        <div className="mt-3 p-2 bg-purple-100/50 rounded text-sm">
          <div className="font-medium text-purple-700 mb-1">🤖 Agent 分析建议：</div>
          <ul className="text-purple-600 space-y-1">
            {sentiment.agent_analysis_reasons.map((reason: string, i: number) => (
              <li key={i} className="flex items-start gap-1">
                <span className="text-purple-400">•</span>
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
