import { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import type { IconType } from './types'

export interface ChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Selected state. */
  on?: boolean
  icon?: IconType
}

/** Filter chip — a toggleable pill-shaped button. */
export function Chip({ on, icon: Icon, className, children, type = 'button', ...props }: ChipProps) {
  return (
    <button type={type} className={cn('chip', on && 'on', className)} aria-pressed={!!on} {...props}>
      {Icon && <Icon style={{ width: 13, height: 13 }} aria-hidden />}
      {children}
    </button>
  )
}
