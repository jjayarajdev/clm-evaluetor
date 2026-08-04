import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Pill } from '../Pill'

describe('Pill', () => {
  it.each([
    ['Active', 'pill-ok'],
    ['Overdue', 'pill-da'],
    ['Due soon', 'pill-wa'],
    ['In review', 'pill-p'],
    ['Open', 'pill-in'],
    ['Draft', 'pill-n'],
  ])('maps known status "%s" to %s', (label, cls) => {
    render(<Pill>{label}</Pill>)
    expect(screen.getByText(label)).toHaveClass('pill', cls)
  })

  it('falls back to neutral for unknown labels', () => {
    render(<Pill>Something else</Pill>)
    expect(screen.getByText('Something else')).toHaveClass('pill-n')
  })

  it('explicit tone overrides the status map', () => {
    render(<Pill tone="da">Active</Pill>)
    expect(screen.getByText('Active')).toHaveClass('pill-da')
  })

  it('renders a dot by default and omits it when dot=false', () => {
    const { container, rerender } = render(<Pill>Active</Pill>)
    expect(container.querySelector('.dot')).not.toBeNull()
    rerender(<Pill dot={false}>Active</Pill>)
    expect(container.querySelector('.dot')).toBeNull()
  })
})
