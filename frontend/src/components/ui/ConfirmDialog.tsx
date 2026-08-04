import { ReactNode } from 'react'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import { Button } from './Button'

export interface ConfirmDialogProps {
  open: boolean
  title: string
  body?: ReactNode
  /** What the action removes/changes — shown as an explicit red list. */
  affected?: string[]
  /** What the action does NOT touch — shown as an explicit green list. */
  safe?: string[]
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
  tone?: 'danger' | 'warn'
}

/* Every destructive action states exactly what is and is not affected. */
export function ConfirmDialog({
  open, title, body, affected, safe,
  confirmLabel = 'Delete', cancelLabel = 'Cancel',
  onConfirm, onCancel, tone = 'danger',
}: ConfirmDialogProps) {
  if (!open) return null
  return (
    <div className="scrim" onClick={onCancel}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} onClick={(e) => e.stopPropagation()}>
        <div className="modal-h">
          <span
            style={{
              width: 34, height: 34, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
              background: tone === 'danger' ? 'var(--da-f)' : 'var(--wa-f)',
              color: tone === 'danger' ? 'var(--da)' : 'var(--wa)',
              flexShrink: 0,
            }}
          >
            <ExclamationTriangleIcon style={{ width: 18, height: 18 }} aria-hidden />
          </span>
          <div style={{ paddingTop: 3 }}>
            <h3 style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, letterSpacing: '-.3px' }}>{title}</h3>
          </div>
        </div>
        <div className="modal-b">
          {body && (
            <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
              {body}
            </p>
          )}
          {affected && affected.length > 0 && (
            <div className="banner banner-da" style={{ marginTop: 14, flexDirection: 'column', gap: 6 }}>
              <b style={{ fontSize: 'var(--fs-sm)', letterSpacing: '.3px', textTransform: 'uppercase' }}>This removes</b>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {affected.map((a, n) => (
                  <li key={n}>{a}</li>
                ))}
              </ul>
            </div>
          )}
          {safe && safe.length > 0 && (
            <div
              className="banner"
              style={{
                marginTop: 8, flexDirection: 'column', gap: 6,
                background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)',
              }}
            >
              <b style={{ fontSize: 'var(--fs-sm)', letterSpacing: '.3px', textTransform: 'uppercase' }}>
                This does not touch
              </b>
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {safe.map((a, n) => (
                  <li key={n}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div className="modal-f">
          <Button variant="ghost" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant={tone === 'danger' ? 'danger' : 'primary'} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
