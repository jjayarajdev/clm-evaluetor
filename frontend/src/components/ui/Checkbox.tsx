import { CheckIcon, MinusIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

export interface CheckboxProps {
  checked?: boolean
  /** Indeterminate ("some selected") state — wins over checked. */
  mixed?: boolean
  disabled?: boolean
  onChange?: (checked: boolean) => void
  label?: string
}

export function Checkbox({ checked, mixed, disabled, onChange, label }: CheckboxProps) {
  const Icon = mixed ? MinusIcon : CheckIcon
  const box = (
    <span
      className={cn('cbx', mixed ? 'mix' : checked && 'on', disabled && 'off-lock')}
      role="checkbox"
      aria-checked={mixed ? 'mixed' : !!checked}
      tabIndex={disabled ? -1 : 0}
      onClick={(e) => {
        e.stopPropagation()
        if (!disabled) onChange?.(!checked)
      }}
      onKeyDown={(e) => {
        if ((e.key === ' ' || e.key === 'Enter') && !disabled) {
          e.preventDefault()
          onChange?.(!checked)
        }
      }}
    >
      <Icon style={{ width: 12, height: 12 }} aria-hidden />
    </span>
  )
  if (!label) return box
  return (
    <label className="row" style={{ gap: 8, cursor: disabled ? 'not-allowed' : 'pointer' }}>
      {box}
      <span style={{ fontSize: 'var(--fs-md)' }}>{label}</span>
    </label>
  )
}
