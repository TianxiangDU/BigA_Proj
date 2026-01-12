import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// 格式化数字
export function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) return '-'
  return value.toFixed(decimals)
}

// 格式化百分比
export function formatPercent(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) return '-'
  return `${(value * 100).toFixed(decimals)}%`
}

// 格式化金额（亿）
export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  if (value >= 100000000) {
    return `${(value / 100000000).toFixed(2)}亿`
  }
  if (value >= 10000) {
    return `${(value / 10000).toFixed(0)}万`
  }
  return value.toFixed(0)
}

// 格式化时间
export function formatTime(ts: string | null | undefined): string {
  if (!ts) return '-'
  const date = new Date(ts)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// 格式化日期时间
export function formatDateTime(ts: string | null | undefined): string {
  if (!ts) return '-'
  const date = new Date(ts)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取风险灯样式
export function getRiskLightClass(light: string): string {
  switch (light) {
    case 'GREEN':
      return 'risk-light-green'
    case 'YELLOW':
      return 'risk-light-yellow'
    case 'RED':
      return 'risk-light-red'
    default:
      return 'risk-light-green'
  }
}

// 获取风险灯文本
export function getRiskLightText(light: string): string {
  switch (light) {
    case 'GREEN':
      return '🟢 绿灯'
    case 'YELLOW':
      return '🟡 黄灯'
    case 'RED':
      return '🔴 红灯'
    default:
      return '🟢 绿灯'
  }
}

// 获取动作样式
export function getActionClass(action: string): string {
  switch (action) {
    case 'ALLOW':
      return 'action-allow'
    case 'WATCH':
      return 'action-watch'
    case 'BLOCK':
      return 'action-block'
    default:
      return 'action-watch'
  }
}

// 获取动作文本
export function getActionText(action: string): string {
  switch (action) {
    case 'ALLOW':
      return '✅ 可执行'
    case 'WATCH':
      return '👁️ 观察'
    case 'BLOCK':
      return '🚫 禁止'
    default:
      return '观察'
  }
}

// 获取市场状态文本
export function getRegimeText(regime: string): string {
  const map: Record<string, string> = {
    'STRONG': '强势',
    'NORMAL': '正常',
    'DIVERGENCE': '分化',
    'WEAK': '弱势',
    'CHAOS': '混沌'
  }
  return map[regime] || regime
}

// 获取涨跌颜色
export function getPriceColor(value: number): string {
  if (value > 0) return 'text-rise'
  if (value < 0) return 'text-fall'
  return 'text-foreground'
}
