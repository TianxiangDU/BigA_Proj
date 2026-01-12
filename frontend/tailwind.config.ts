import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // 主色调
        primary: {
          DEFAULT: '#3b82f6',
          foreground: '#ffffff',
        },
        // 涨跌色（可配置）
        rise: '#ef4444',    // 红色 - 涨
        fall: '#22c55e',    // 绿色 - 跌
        // 风险灯
        'light-green': '#22c55e',
        'light-yellow': '#eab308',
        'light-red': '#ef4444',
        // 背景
        background: '#0f172a',
        'background-secondary': '#1e293b',
        'background-tertiary': '#334155',
        // 边框
        border: '#475569',
        // 文字
        foreground: '#f1f5f9',
        muted: '#94a3b8',
      },
      fontFamily: {
        sans: ['DM Sans', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        lg: '0.75rem',
        md: '0.5rem',
        sm: '0.25rem',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
export default config
