import { ReactNode } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { IconButton } from './Button'

export interface DrawerProps {
  open: boolean
  title: string
  /** Mono subtitle under the title (e.g. an id). */
  sub?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  width?: number | string
}

/** Right-side overlay panel for detail/edit flows. */
export function Drawer({ open, title, sub, onClose, children, footer, width }: DrawerProps) {
  if (!open) return null
  return (
    <>
      <div className="scrim" style={{ zIndex: 84, display: 'block' }} onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={title} style={width ? { width } : undefined}>
        <header className="row" style={{ padding: '14px 16px', borderBottom: '1px solid var(--b)', gap: 12 }}>
          <div className="grow">
            <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>{title}</h3>
            {sub && (
              <div className="faint mono" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>
                {sub}
              </div>
            )}
          </div>
          <IconButton icon={XMarkIcon} label="Close" onClick={onClose} />
        </header>
        <div className="scroll grow" style={{ padding: 16 }}>
          {children}
        </div>
        {footer && (
          <footer className="row" style={{ padding: 14, borderTop: '1px solid var(--b)', gap: 8, background: 'var(--s3)' }}>
            {footer}
          </footer>
        )}
      </aside>
    </>
  )
}
