export interface BarProps {
  /** 0–100 */
  value: number
  width?: number | string
  /** CSS color for the fill; defaults to primary. */
  tone?: string
}

export function Bar({ value, width = 40, tone }: BarProps) {
  return (
    <span className="bar" style={{ width }}>
      <i style={{ width: `${Math.max(2, Math.min(100, value))}%`, background: tone }} />
    </span>
  )
}

export interface ConfidenceProps {
  /** 0–1, or null/undefined for manually-entered values. */
  value?: number | null
  width?: number
  showNum?: boolean
}

/* Confidence is the product's core AI signal: a bar, a two-decimal figure, and a
   colour band. >=0.90 ok, 0.60-0.89 warn, <0.60 danger. */
export function Confidence({ value, width = 40, showNum = true }: ConfidenceProps) {
  if (value == null) {
    return (
      <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
        manual
      </span>
    )
  }
  const tone = value >= 0.9 ? 'var(--ok)' : value >= 0.6 ? 'var(--wa)' : 'var(--da)'
  return (
    <span className="row" style={{ gap: 7 }}>
      <Bar value={value * 100} width={width} tone={tone} />
      {showNum && (
        <span className="mono num" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: tone }}>
          {value.toFixed(2)}
        </span>
      )}
    </span>
  )
}
