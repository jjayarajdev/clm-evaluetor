import { createContext, useContext, useEffect, useState, ReactNode } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'

interface ThemeContextValue {
  /** User-selected mode (may be 'system') */
  mode: ThemeMode
  /** Resolved theme actually applied to the document */
  theme: 'light' | 'dark'
  setMode: (mode: ThemeMode) => void
  toggle: () => void
}

const STORAGE_KEY = 'ev-theme'

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function systemTheme(): 'light' | 'dark' {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved === 'light' || saved === 'dark' || saved === 'system' ? saved : 'light'
  })
  const [theme, setTheme] = useState<'light' | 'dark'>(() =>
    mode === 'system' ? systemTheme() : mode
  )

  useEffect(() => {
    if (mode !== 'system') {
      setTheme(mode)
      return
    }
    setTheme(systemTheme())
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => setTheme(e.matches ? 'dark' : 'light')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [mode])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  const setMode = (m: ThemeMode) => {
    setModeState(m)
    try {
      localStorage.setItem(STORAGE_KEY, m)
    } catch {
      // storage unavailable (private mode) — theme still applies for the session
    }
  }

  const toggle = () => setMode(theme === 'dark' ? 'light' : 'dark')

  return (
    <ThemeContext.Provider value={{ mode, theme, setMode, toggle }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
