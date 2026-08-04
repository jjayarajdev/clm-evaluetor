import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import type { IconType } from './types'

export interface MenuItem {
  value?: string
  label?: string
  icon?: IconType
  danger?: boolean
  disabled?: boolean
  /** Keyboard shortcut hint shown right-aligned. */
  kb?: string
  /** Separator row — ignores all other props. */
  sep?: boolean
}

export interface DropdownMenuProps {
  items: (MenuItem | false | null | undefined)[]
  onSelect?: (value: string | undefined) => void
  onClose?: () => void
  align?: 'left' | 'right'
  top?: number | string
}

/** Anchored dropdown menu. Render inside a position:relative parent, conditionally. */
export function DropdownMenu({ items, onSelect, onClose, align = 'right', top = '100%' }: DropdownMenuProps) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose?.()
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose?.()
    }
    // Defer so the click that opened the menu doesn't immediately close it.
    const t = setTimeout(() => document.addEventListener('mousedown', onDown), 0)
    document.addEventListener('keydown', onKey)
    return () => {
      clearTimeout(t)
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [onClose])

  return (
    <div ref={ref} className="menu" role="menu" style={{ top, [align]: 0, marginTop: 4 }}>
      {items
        .filter((it): it is MenuItem => Boolean(it))
        .map((it, n) =>
          it.sep ? (
            <div key={n} className="msep" />
          ) : (
            <div
              key={it.value || n}
              role="menuitem"
              className={cn('mi', it.danger && 'dg')}
              onClick={() => {
                onSelect?.(it.value)
                onClose?.()
              }}
              style={it.disabled ? { opacity: 0.4, pointerEvents: 'none' } : undefined}
            >
              {it.icon && (
                <it.icon
                  style={{ width: 15, height: 15, flexShrink: 0, color: it.danger ? 'currentColor' : 'var(--m)' }}
                  aria-hidden
                />
              )}
              {it.label}
              {it.kb && <span className="kb mono">{it.kb}</span>}
            </div>
          )
        )}
    </div>
  )
}
