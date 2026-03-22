import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import StatCard, { StatusBadge, FilterPill } from '../StatCard'
import { DocumentIcon } from '@heroicons/react/24/outline'

describe('StatCard', () => {
  it('renders title and value', () => {
    render(<StatCard title="Total Contracts" value={42} />)

    expect(screen.getByText('Total Contracts')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders subtitle when provided', () => {
    render(<StatCard title="Contracts" value={10} subtitle="Updated today" />)

    expect(screen.getByText('Updated today')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    const { container } = render(
      <StatCard title="Documents" value={5} icon={DocumentIcon} />
    )

    // Check for icon container
    const iconContainer = container.querySelector('.rounded-lg')
    expect(iconContainer).toBeInTheDocument()
  })

  it('renders positive trend indicator', () => {
    render(<StatCard title="Revenue" value="$100K" trend={{ value: 15, label: 'vs last month' }} />)

    expect(screen.getByText(/↑ 15%/)).toBeInTheDocument()
    expect(screen.getByText('vs last month')).toBeInTheDocument()
  })

  it('renders negative trend indicator', () => {
    render(<StatCard title="Costs" value="$50K" trend={{ value: -10 }} />)

    expect(screen.getByText(/↓ 10%/)).toBeInTheDocument()
  })

  it('renders neutral trend indicator', () => {
    render(<StatCard title="Stable" value={100} trend={{ value: 0 }} />)

    expect(screen.getByText(/→ 0%/)).toBeInTheDocument()
  })

  it('handles click when onClick is provided', () => {
    const handleClick = vi.fn()
    render(<StatCard title="Clickable" value={1} onClick={handleClick} />)

    const card = screen.getByText('Clickable').closest('div[class*="rounded-xl"]')
    fireEvent.click(card!)

    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('applies correct size classes', () => {
    const { container, rerender } = render(<StatCard title="Small" value={1} size="sm" />)
    expect(container.firstChild).toHaveClass('p-4')

    rerender(<StatCard title="Medium" value={1} size="md" />)
    expect(container.firstChild).toHaveClass('p-5')

    rerender(<StatCard title="Large" value={1} size="lg" />)
    expect(container.firstChild).toHaveClass('p-6')
  })

  it('renders mini bar chart when data provided', () => {
    const { container } = render(
      <StatCard title="Chart" value={100} chart={[10, 20, 30, 40, 50]} />
    )

    const chartBars = container.querySelectorAll('.w-2')
    expect(chartBars.length).toBe(5)
  })

  it('applies color variants', () => {
    const { container, rerender } = render(
      <StatCard title="Success" value={1} color="success" variant="filled" />
    )
    expect(container.firstChild).toHaveClass('bg-emerald-50')

    rerender(<StatCard title="Warning" value={1} color="warning" variant="filled" />)
    expect(container.firstChild).toHaveClass('bg-amber-50')

    rerender(<StatCard title="Danger" value={1} color="danger" variant="filled" />)
    expect(container.firstChild).toHaveClass('bg-red-50')
  })
})

describe('StatusBadge', () => {
  it('renders active status', () => {
    render(<StatusBadge status="active" />)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('renders pending status with correct styling', () => {
    render(<StatusBadge status="pending" />)
    expect(screen.getByText('Pending')).toHaveClass('bg-amber-100', 'text-amber-700')
  })

  it('renders breached status with correct styling', () => {
    render(<StatusBadge status="breached" />)
    expect(screen.getByText('Breached')).toHaveClass('bg-red-100', 'text-red-700')
  })

  it('applies correct size classes', () => {
    const { rerender } = render(<StatusBadge status="active" size="xs" />)
    expect(screen.getByText('Active')).toHaveClass('px-1.5', 'text-xs')

    rerender(<StatusBadge status="active" size="md" />)
    expect(screen.getByText('Active')).toHaveClass('px-2.5', 'text-sm')
  })
})

describe('FilterPill', () => {
  it('renders label', () => {
    render(<FilterPill label="Contract Type" />)
    expect(screen.getByText('Contract Type')).toBeInTheDocument()
  })

  it('renders remove button when onRemove is provided', () => {
    const handleRemove = vi.fn()
    render(<FilterPill label="Filter" onRemove={handleRemove} />)

    const removeButton = screen.getByRole('button')
    fireEvent.click(removeButton)

    expect(handleRemove).toHaveBeenCalledTimes(1)
  })

  it('does not render remove button when onRemove is not provided', () => {
    render(<FilterPill label="Static Filter" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
