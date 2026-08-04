import { ReactNode } from 'react'
import { InboxIcon } from '@heroicons/react/24/outline'
import type { IconType } from './types'

export interface EmptyStateProps {
  icon?: IconType
  title: string
  body?: string
  action?: ReactNode
}

/* Empty states explain WHY empty and offer the next move — never a bare zero. */
export function EmptyState({ icon: Icon = InboxIcon, title, body, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <span
        style={{
          width: 40, height: 40, borderRadius: 'var(--r-lg)',
          background: 'var(--s2)', color: 'var(--f)', display: 'grid', placeItems: 'center',
        }}
      >
        <Icon style={{ width: 20, height: 20 }} aria-hidden />
      </span>
      <h4>{title}</h4>
      {body && <p>{body}</p>}
      {action}
    </div>
  )
}
