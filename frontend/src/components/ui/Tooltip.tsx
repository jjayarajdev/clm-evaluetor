import { ReactNode, useState } from 'react'
import { cn } from '@/lib/utils'

export interface TooltipProps {
  children: ReactNode
  label: ReactNode
  /** rich=true gives the 280px provenance panel. */
  rich?: boolean
  subhead?: string
  footer?: string
  side?: 'top' | 'bottom'
}

/** Hover tooltip. Wraps its trigger inline. */
export function Tooltip({ children, label, rich, subhead, footer, side = 'top' }: TooltipProps) {
  const [show, setShow] = useState(false)
  const pos = side === 'bottom' ? { top: '100%', marginTop: 6 } : { bottom: '100%', marginBottom: 6 }
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)}
      onBlur={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          role="tooltip"
          className={cn('tip', rich && 'tip-rich')}
          style={{ ...pos, left: rich ? 0 : '50%', transform: rich ? 'none' : 'translateX(-50%)' }}
        >
          {subhead && (
            <span style={{ display: 'block', fontSize: 'var(--fs-sm)', fontWeight: 700, marginBottom: 5 }}>
              {subhead}
            </span>
          )}
          <span style={{ display: 'block', lineHeight: rich ? 1.55 : 1.3, color: rich ? 'var(--m)' : undefined }}>
            {label}
          </span>
          {footer && (
            <span className="mono" style={{ display: 'block', marginTop: 8, fontSize: 'var(--fs-xs)', color: 'var(--f)' }}>
              {footer}
            </span>
          )}
        </span>
      )}
    </span>
  )
}
