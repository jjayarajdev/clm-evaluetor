import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import LoadingSpinner from '../LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders with default medium size', () => {
    const { container } = render(<LoadingSpinner />)
    const spinner = container.firstChild as HTMLElement

    expect(spinner).toBeInTheDocument()
    expect(spinner).toHaveClass('h-8', 'w-8')
    expect(spinner).toHaveClass('animate-spin')
  })

  it('renders small size when size="sm"', () => {
    const { container } = render(<LoadingSpinner size="sm" />)
    const spinner = container.firstChild as HTMLElement

    expect(spinner).toHaveClass('h-4', 'w-4')
  })

  it('renders large size when size="lg"', () => {
    const { container } = render(<LoadingSpinner size="lg" />)
    const spinner = container.firstChild as HTMLElement

    expect(spinner).toHaveClass('h-12', 'w-12')
  })

  it('applies custom className', () => {
    const { container } = render(<LoadingSpinner className="custom-class" />)
    const spinner = container.firstChild as HTMLElement

    expect(spinner).toHaveClass('custom-class')
  })

  it('has proper styling for animation', () => {
    const { container } = render(<LoadingSpinner />)
    const spinner = container.firstChild as HTMLElement

    expect(spinner).toHaveClass('rounded-full')
    expect(spinner).toHaveClass('animate-spin')
  })
})
