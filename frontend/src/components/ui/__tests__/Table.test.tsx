import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Table, TableColumn } from '../Table'
import { EmptyState } from '../EmptyState'

interface Row {
  id: string
  name: string
  value: number
}

const rows: Row[] = [
  { id: 'b', name: 'Bravo', value: 2 },
  { id: 'a', name: 'Alpha', value: 3 },
  { id: 'c', name: 'Charlie', value: 1 },
]

const columns: TableColumn<Row>[] = [
  { key: 'name', header: 'Name', sortable: true },
  { key: 'value', header: 'Value', sortable: true, sortValue: (r) => r.value, align: 'right' },
]

function bodyText() {
  return screen.getAllByRole('row').slice(1).map((r) => within(r).getAllByRole('cell')[0].textContent)
}

describe('Table', () => {
  it('renders rows in given order by default', () => {
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} />)
    expect(bodyText()).toEqual(['Bravo', 'Alpha', 'Charlie'])
  })

  it('sorts ascending, descending, then resets on header clicks', async () => {
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} />)
    const header = screen.getByText('Name')
    await userEvent.click(header)
    expect(bodyText()).toEqual(['Alpha', 'Bravo', 'Charlie'])
    await userEvent.click(header)
    expect(bodyText()).toEqual(['Charlie', 'Bravo', 'Alpha'])
    await userEvent.click(header)
    expect(bodyText()).toEqual(['Bravo', 'Alpha', 'Charlie'])
  })

  it('sorts numerically via sortValue', async () => {
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} />)
    await userEvent.click(screen.getByText('Value'))
    expect(bodyText()).toEqual(['Charlie', 'Bravo', 'Alpha'])
  })

  it('invokes onRowClick and marks the selected row', async () => {
    const onRowClick = vi.fn()
    render(
      <Table columns={columns} rows={rows} rowKey={(r) => r.id} onRowClick={onRowClick} selectedKey="a" />
    )
    await userEvent.click(screen.getByText('Bravo'))
    expect(onRowClick).toHaveBeenCalledWith(rows[0])
    const selectedRow = screen.getByText('Alpha').closest('tr')!
    expect(selectedRow).toHaveClass('sel')
  })

  it('renders the empty slot when there are no rows', () => {
    render(
      <Table
        columns={columns}
        rows={[]}
        rowKey={(r: Row) => r.id}
        empty={<EmptyState title="No contracts yet" />}
      />
    )
    expect(screen.getByText('No contracts yet')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
