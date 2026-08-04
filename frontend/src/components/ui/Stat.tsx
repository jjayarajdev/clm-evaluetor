import { ReactNode } from 'react'
import type { IconType } from './types'

export interface StatProps {
  icon?: IconType
  label: string
  value: ReactNode
  sub?: ReactNode
  /** CSS color for the sub line (e.g. 'var(--da)'). */
  subTone?: string
  onClick?: () => void
  active?: boolean
}

/** Compact metric card. Clickable variant doubles as a filter toggle. */
export function Stat({ icon: Icon, label, value, sub, subTone, onClick, active }: StatProps) {
  return (
    <div
      className="card card-p"
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } } : undefined}
      style={{
        cursor: onClick ? 'pointer' : undefined,
        borderColor: active ? 'var(--p-b)' : undefined,
        background: active ? 'var(--p-f)' : undefined,
        transition: 'border-color .12s, background .12s',
      }}
    >
      <div className="row" style={{ gap: 6, color: 'var(--m)', fontSize: 'var(--fs-sm)', fontWeight: 500 }}>
        {Icon && <Icon style={{ width: 14, height: 14, flexShrink: 0 }} aria-hidden />}
        <span className="trunc">{label}</span>
      </div>
      <div className="num" style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-1px', marginTop: 7, lineHeight: 1.1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 'var(--fs-sm)', color: subTone || 'var(--f)', marginTop: 3 }}>{sub}</div>
      )}
    </div>
  )
}
