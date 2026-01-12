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

type TabType = 'dashboard' | 'pool' | 'alerts' | 'portfolio'

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

  const loadData = useCallback(async () => {
    try {
      const dashboardData = await api.getDashboard()
      setDashboard(dashboardData)
      setRiskState(dashboardData.risk_state)
      setLastUpdate(new Date())
      setLoading(false)
      
      // 更新刷新间隔
      if (dashboardData.refresh_config) {
        setRefreshSec(dashboardData.refresh_config.refresh_sec || 5)
        setCountdown(dashboardData.refresh_config.refresh_sec || 5)
      }
      
      Promise.all([
        api.getCandidates(undefined, 100),
        api.getAlerts(50),
      ]).then(([candidatesData, alertsData]) => {
        setCandidates(candidatesData.candidates || [])
        setAlerts(alertsData.alerts || [])
      }).catch(e => console.error('加载候选池失败:', e))
      
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
      <header className="nav-header">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-base font-bold text-foreground flex items-center gap-2">
              <Flame className="w-5 h-5 text-rise" />
              <span className="hidden sm:inline">A股打板提示</span>
            </h1>
            <nav className="hidden md:flex gap-1">
              {[
                { id: 'dashboard', label: '实时看板', icon: LayoutDashboard },
                { id: 'pool', label: '候选池', icon: ListFilter },
                { id: 'alerts', label: '提示卡', icon: Bell },
                { id: 'portfolio', label: '持仓', icon: Wallet },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as TabType)}
                  className={`nav-tab flex items-center gap-1.5 ${activeTab === tab.id ? 'active' : ''}`}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <SessionBadge session={dashboard?.trading_session} />
            <RiskLightBadge light={dashboard?.summary?.risk_light || 'GREEN'} />
            <RefreshStatus 
              countdown={countdown} 
              refreshSec={refreshSec} 
              lastUpdate={lastUpdate}
              isTrading={dashboard?.refresh_config?.is_trading}
            />
            <button 
              onClick={() => setShowFilter(!showFilter)}
              className={`btn btn-secondary p-2 ${showFilter ? 'bg-rise/10 text-rise' : ''}`}
            >
              <Filter className="w-4 h-4" />
            </button>
            <button 
              onClick={handleRefresh} 
              disabled={refreshing}
              className="btn btn-secondary p-2"
              title="手动刷新"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
        
        {/* 筛选器 */}
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
        {activeTab === 'portfolio' && <PortfolioView riskState={riskState} />}
      </main>

      {/* 移动端底部导航 */}
      <nav className="mobile-nav">
        {[
          { id: 'dashboard', label: '看板', icon: LayoutDashboard },
          { id: 'pool', label: '候选', icon: ListFilter },
          { id: 'alerts', label: '提示', icon: Bell },
          { id: 'portfolio', label: '持仓', icon: Wallet },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as TabType)}
            className={`mobile-nav-item ${activeTab === tab.id ? 'active' : ''}`}
          >
            <tab.icon className="w-5 h-5 mb-0.5" />
            <span>{tab.label}</span>
          </button>
        ))}
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

function RefreshStatus({ countdown, refreshSec, lastUpdate, isTrading }: {
  countdown: number
  refreshSec: number
  lastUpdate: Date | null
  isTrading: boolean
}) {
  const formatLastUpdate = (date: Date | null) => {
    if (!date) return '--:--:--'
    return date.toLocaleTimeString('zh-CN', { hour12: false })
  }
  
  return (
    <div className="hidden sm:flex items-center gap-2 text-xs">
      <div className="flex items-center gap-1 text-muted">
        <span>更新:</span>
        <span className="font-mono">{formatLastUpdate(lastUpdate)}</span>
      </div>
      <div className={`flex items-center gap-1 px-2 py-1 rounded ${
        isTrading ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-500'
      }`}>
        <span>{countdown}s</span>
        <span className="text-[10px]">/ {refreshSec}s</span>
      </div>
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

function RiskLightBadge({ light }: { light: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`risk-light ${getRiskLightClass(light)}`} />
      <span className="text-sm font-medium hidden sm:inline">{getRiskLightText(light)}</span>
    </div>
  )
}

function DashboardView({ dashboard, candidates, filterStocks }: any) {
  const market = dashboard?.market || {}
  const [expandedSection, setExpandedSection] = useState<string | null>('limit_up')
  
  // 应用筛选
  const limitUpStocks = useMemo(() => filterStocks(market.limit_up_stocks || []), [market.limit_up_stocks, filterStocks])
  const limitDownStocks = useMemo(() => filterStocks(market.limit_down_stocks || []), [market.limit_down_stocks, filterStocks])
  const nearLimitUpStocks = useMemo(() => filterStocks(market.near_limit_up_stocks || []), [market.near_limit_up_stocks, filterStocks])

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section)
  }

  return (
    <div className="space-y-4">
      {/* 核心统计 */}
      <div className="grid grid-cols-4 gap-3">
        <div className="stat-card cursor-pointer hover:shadow-md transition-shadow" onClick={() => toggleSection('limit_up')}>
          <div className="stat-value text-rise">{limitUpStocks.length}</div>
          <div className="stat-label">涨停</div>
          <div className="text-xs text-muted mt-1">全市场 {(market.limit_up_stocks || []).length}</div>
        </div>
        <div className="stat-card cursor-pointer hover:shadow-md transition-shadow" onClick={() => toggleSection('limit_down')}>
          <div className="stat-value text-fall">{limitDownStocks.length}</div>
          <div className="stat-label">跌停</div>
          <div className="text-xs text-muted mt-1">全市场 {(market.limit_down_stocks || []).length}</div>
        </div>
        <div className="stat-card">
          <div className={`stat-value ${(market.bomb_rate || 0) > 0.3 ? 'text-yellow-500' : ''}`}>
            {formatPercent(market.bomb_rate || 0)}
          </div>
          <div className="stat-label">炸板率</div>
        </div>
        <div className="stat-card cursor-pointer hover:shadow-md transition-shadow" onClick={() => toggleSection('near')}>
          <div className="stat-value text-orange-500">{nearLimitUpStocks.length}</div>
          <div className="stat-label">冲板中</div>
          <div className="text-xs text-muted mt-1">全市场 {(market.near_limit_up_stocks || []).length}</div>
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
  const displayStocks = expanded ? stocks : stocks.slice(0, 10)
  const changeColor = colorType === 'rise' ? 'text-rise' : 'text-fall'
  
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
