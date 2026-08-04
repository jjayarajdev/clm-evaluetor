import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Confidence } from '../Bar'

describe('Confidence', () => {
  it('shows "manual" for null values', () => {
    render(<Confidence value={null} />)
    expect(screen.getByText('manual')).toBeInTheDocument()
  })

  it('shows "manual" for undefined values', () => {
    render(<Confidence />)
    expect(screen.getByText('manual')).toBeInTheDocument()
  })

  it('renders the value with two decimals', () => {
    render(<Confidence value={0.9} />)
    expect(screen.getByText('0.90')).toBeInTheDocument()
  })

  it('bands >=0.90 as ok', () => {
    render(<Confidence value={0.93} />)
    expect(screen.getByText('0.93')).toHaveStyle({ color: 'var(--ok)' })
  })

  it('bands 0.60-0.89 as warning', () => {
    render(<Confidence value={0.6} />)
    expect(screen.getByText('0.60')).toHaveStyle({ color: 'var(--wa)' })
  })

  it('bands <0.60 as danger', () => {
    render(<Confidence value={0.59} />)
    expect(screen.getByText('0.59')).toHaveStyle({ color: 'var(--da)' })
  })

  it('hides the number when showNum is false', () => {
    render(<Confidence value={0.75} showNum={false} />)
    expect(screen.queryByText('0.75')).not.toBeInTheDocument()
  })
})
