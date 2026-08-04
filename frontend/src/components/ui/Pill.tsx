import { ReactNode } from 'react'
import { SparklesIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import type { IconType } from './types'

export type PillTone = 'ok' | 'wa' | 'da' | 'in' | 'p' | 'n'

/** Default tone for well-known status labels (prototype STATUS_PILL map). */
export const STATUS_PILL: Record<string, PillTone> = {
  Active: 'ok', 'In review': 'p', 'Renewal due': 'wa', Lapsed: 'da', Draft: 'n', Archived: 'n',
  Open: 'in', Overdue: 'da', 'Due soon': 'wa', Closed: 'ok', Met: 'ok', Breached: 'da', Pending: 'wa',
  High: 'da', Medium: 'wa', Low: 'ok',
}

export interface PillProps {
  children: ReactNode
  tone?: PillTone
  dot?: boolean
  className?: string
}

export function Pill({ children, tone, dot = true, className }: PillProps) {
  const t = tone || (typeof children === 'string' && STATUS_PILL[children]) || 'n'
  return (
    <span className={cn('pill', `pill-${t}`, className)}>
      {dot && <i className="dot" />}
      {children}
    </span>
  )
}

export function Tag({ children, icon: Icon }: { children: ReactNode; icon?: IconType }) {
  return (
    <span className="tag">
      {Icon && <Icon style={{ width: 11, height: 11 }} aria-hidden />}
      {children}
    </span>
  )
}

/** Marks a value as AI-derived. */
export function AiTag({ children = 'AI' }: { children?: ReactNode }) {
  return (
    <span className="ai-tag">
      <SparklesIcon style={{ width: 10, height: 10 }} aria-hidden />
      {children}
    </span>
  )
}
