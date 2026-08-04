import { ButtonHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/lib/utils'
import type { IconType } from './types'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-ghost'
export type ButtonSize = 'sm' | 'md' | 'lg'

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'btn-p',
  secondary: 'btn-s',
  ghost: 'btn-g',
  danger: 'btn-d',
  'danger-ghost': 'btn-dg',
}

const ICON_SIZE: Record<ButtonSize, number> = { sm: 13, md: 15, lg: 17 }

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconType
  iconRight?: IconType
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'secondary', size = 'md', icon: Icon, iconRight: IconRight, className, children, type = 'button', ...props },
  ref
) {
  const s = ICON_SIZE[size]
  return (
    <button
      ref={ref}
      type={type}
      className={cn('btn', VARIANT[variant], size === 'sm' && 'btn-sm', size === 'lg' && 'btn-lg', className)}
      {...props}
    >
      {Icon && <Icon style={{ width: s, height: s, flexShrink: 0 }} aria-hidden />}
      {children}
      {IconRight && <IconRight style={{ width: s, height: s, flexShrink: 0 }} aria-hidden />}
    </button>
  )
})

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: IconType
  /** Accessible label (also shown as native tooltip). */
  label: string
  /** Active/pressed visual state. */
  active?: boolean
  size?: 'sm' | 'md'
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon: Icon, label, active, size = 'md', className, type = 'button', ...props },
  ref
) {
  const s = size === 'sm' ? 15 : 17
  return (
    <button
      ref={ref}
      type={type}
      className={cn('ib', active && 'on', size === 'sm' && 'ib-sm', className)}
      aria-label={label}
      title={label}
      {...props}
    >
      <Icon style={{ width: s, height: s }} aria-hidden />
    </button>
  )
})
