import { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, forwardRef } from 'react'
import { ChevronDownIcon } from '@heroicons/react/24/outline'
import type { IconType } from './types'

export interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  hint?: string
  error?: string
  icon?: IconType
  /** Custom control rendered inside the input frame instead of an <input>. */
  children?: ReactNode
  containerStyle?: React.CSSProperties
  containerClassName?: string
}

/** Labeled input frame: label + bordered control + hint/error line. */
export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, hint, error, icon: Icon, children, containerStyle, containerClassName, ...inputProps },
  ref
) {
  return (
    <div style={containerStyle} className={containerClassName}>
      {label && <label className="lbl">{label}</label>}
      <div className="inp">
        {Icon && <Icon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--f)' }} aria-hidden />}
        {children || <input ref={ref} {...inputProps} />}
      </div>
      {(hint || error) && <div className={'hint' + (error ? ' hint-e' : '')}>{error || hint}</div>}
    </div>
  )
})

export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label?: string
  hint?: string
  error?: string
  options: SelectOption[]
  containerStyle?: React.CSSProperties
  containerClassName?: string
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, options, containerStyle, containerClassName, ...selectProps },
  ref
) {
  return (
    <div style={containerStyle} className={containerClassName}>
      {label && <label className="lbl">{label}</label>}
      <div className="inp">
        <select ref={ref} style={{ appearance: 'none', cursor: 'pointer' }} {...selectProps}>
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDownIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
      </div>
      {(hint || error) && <div className={'hint' + (error ? ' hint-e' : '')}>{error || hint}</div>}
    </div>
  )
})
