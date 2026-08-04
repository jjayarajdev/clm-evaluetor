import { CSSProperties } from 'react'
import { cn } from '@/lib/utils'
import type { IconType } from './types'

export interface TabDef<T extends string = string> {
  value: T
  label: string
  icon?: IconType
  count?: number
}

export interface TabsProps<T extends string = string> {
  tabs: TabDef<T>[]
  value: T
  onChange: (value: T) => void
  style?: CSSProperties
  className?: string
}

export function Tabs<T extends string = string>({ tabs, value, onChange, style, className }: TabsProps<T>) {
  return (
    <div className={cn('tabs', className)} style={style} role="tablist">
      {tabs.map((t) => {
        const Icon = t.icon
        return (
          <button
            key={t.value}
            type="button"
            role="tab"
            aria-selected={value === t.value}
            className={cn('tab', value === t.value && 'on')}
            onClick={() => onChange(t.value)}
          >
            {Icon && <Icon style={{ width: 15, height: 15 }} aria-hidden />}
            {t.label}
            {t.count != null && <span className="ct num">{t.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
