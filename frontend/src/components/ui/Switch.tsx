import { cn } from '@/lib/utils'

export interface SwitchProps {
  checked?: boolean
  onChange?: (checked: boolean) => void
  label?: string
  disabled?: boolean
}

export function Switch({ checked, onChange, label, disabled }: SwitchProps) {
  const el = (
    <span
      className={cn('sw', checked && 'on')}
      role="switch"
      aria-checked={!!checked}
      tabIndex={disabled ? -1 : 0}
      style={disabled ? { opacity: 0.45, cursor: 'not-allowed' } : undefined}
      onClick={() => !disabled && onChange?.(!checked)}
      onKeyDown={(e) => {
        if ((e.key === ' ' || e.key === 'Enter') && !disabled) {
          e.preventDefault()
          onChange?.(!checked)
        }
      }}
    >
      <i />
    </span>
  )
  if (!label) return el
  return (
    <label className="row" style={{ gap: 10, cursor: disabled ? 'not-allowed' : 'pointer' }}>
      {el}
      <span style={{ fontSize: 'var(--fs-md)' }}>{label}</span>
    </label>
  )
}
