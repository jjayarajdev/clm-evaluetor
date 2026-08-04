export interface AvatarProps {
  name?: string
  /** Override the initials derived from name. */
  initials?: string
  size?: number
  src?: string
}

export function Avatar({ name = '', initials, size = 28, src }: AvatarProps) {
  const t =
    initials ||
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0])
      .join('')
      .toUpperCase()
  return (
    <span
      className="av"
      aria-label={name || undefined}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.4),
        background: src ? `center/cover no-repeat url(${src})` : undefined,
      }}
    >
      {!src && t}
    </span>
  )
}
