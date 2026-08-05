import { ReactNode, useMemo, useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

export interface TableColumn<T> {
  key: string
  header: ReactNode
  render?: (row: T) => ReactNode
  /** Enables click-to-sort. Provide sortValue when render is custom. */
  sortable?: boolean
  sortValue?: (row: T) => string | number | null | undefined
  align?: 'left' | 'right'
  nowrap?: boolean
  width?: number | string
}

export interface TableProps<T> {
  columns: TableColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  onRowClick?: (row: T) => void
  selectedKey?: string | number | null
  /** Shown instead of the body when rows is empty. */
  empty?: ReactNode
  /** min-width of the table; container scrolls horizontally below it. */
  minWidth?: number
  className?: string
  /** Controlled (server-side) sort. When onSortChange is provided the table
   *  does NOT sort its rows itself — the parent sorts server-side across the
   *  whole dataset and passes already-ordered rows. Without it, the table sorts
   *  client-side over the rows it's given (correct only for full, non-paginated
   *  lists). */
  sortState?: SortState | null
  onSortChange?: (next: SortState | null) => void
}

export interface SortState {
  key: string
  dir: 1 | -1
}

function defaultValue<T>(row: T, key: string): string | number | null | undefined {
  const v = (row as Record<string, unknown>)[key]
  return typeof v === 'string' || typeof v === 'number' ? v : v == null ? null : String(v)
}

/** Direction B data table: sticky uppercase headers, sortable columns, row states. */
export function Table<T>({
  columns, rows, rowKey, onRowClick, selectedKey, empty, minWidth = 780, className,
  sortState, onSortChange,
}: TableProps<T>) {
  const controlled = !!onSortChange
  const [internalSort, setInternalSort] = useState<SortState | null>(null)
  const sort = controlled ? (sortState ?? null) : internalSort

  const sorted = useMemo(() => {
    // Controlled: the parent already ordered the rows server-side; don't re-sort.
    if (controlled || !sort) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col) return rows
    const val = col.sortValue || ((r: T) => defaultValue(r, col.key))
    return [...rows].sort((a, b) => {
      const va = val(a)
      const vb = val(b)
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * sort.dir
      return String(va).localeCompare(String(vb)) * sort.dir
    })
  }, [controlled, rows, sort, columns])

  const toggleSort = (key: string) => {
    const next: SortState | null =
      sort?.key === key ? (sort.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 }
    if (controlled) onSortChange!(next)
    else setInternalSort(next)
  }

  if (rows.length === 0 && empty) {
    return <div className={cn('tbl-w', className)}>{empty}</div>
  }

  return (
    <div className={cn('tbl-w', className)}>
      <table className="tbl" style={{ minWidth }}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={cn(c.sortable && 'sortable', c.align === 'right' && 'r')}
                style={c.width ? { width: c.width } : undefined}
                onClick={c.sortable ? () => toggleSort(c.key) : undefined}
                aria-sort={
                  sort?.key === c.key ? (sort.dir === 1 ? 'ascending' : 'descending') : undefined
                }
              >
                <span className="row" style={{ gap: 4, display: 'inline-flex' }}>
                  {c.header}
                  {sort?.key === c.key &&
                    (sort.dir === 1 ? (
                      <ChevronUpIcon style={{ width: 12, height: 12 }} aria-hidden />
                    ) : (
                      <ChevronDownIcon style={{ width: 12, height: 12 }} aria-hidden />
                    ))}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => {
            const k = rowKey(row)
            return (
              <tr
                key={k}
                className={cn(onRowClick && 'click', selectedKey != null && selectedKey === k && 'sel')}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn(c.nowrap && 'nw', c.align === 'right' && 'r')}>
                    {c.render ? c.render(row) : (defaultValue(row, c.key) as ReactNode)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
