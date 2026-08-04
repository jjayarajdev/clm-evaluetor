import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from '../ConfirmDialog'

const baseProps = {
  title: 'Delete contract?',
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
}

describe('ConfirmDialog', () => {
  it('renders nothing when closed', () => {
    const { container } = render(<ConfirmDialog {...baseProps} open={false} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('states what is affected and what is safe', () => {
    render(
      <ConfirmDialog
        {...baseProps}
        open
        affected={['Extracted metadata', 'Contract links']}
        safe={['Source document']}
      />
    )
    expect(screen.getByText('This removes')).toBeInTheDocument()
    expect(screen.getByText('Extracted metadata')).toBeInTheDocument()
    expect(screen.getByText('Contract links')).toBeInTheDocument()
    expect(screen.getByText('This does not touch')).toBeInTheDocument()
    expect(screen.getByText('Source document')).toBeInTheDocument()
  })

  it('fires onConfirm from the confirm button', async () => {
    const onConfirm = vi.fn()
    render(<ConfirmDialog {...baseProps} open onConfirm={onConfirm} />)
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('fires onCancel when clicking the scrim but not the dialog', async () => {
    const onCancel = vi.fn()
    const { container } = render(<ConfirmDialog {...baseProps} open onCancel={onCancel} />)
    await userEvent.click(screen.getByRole('dialog'))
    expect(onCancel).not.toHaveBeenCalled()
    await userEvent.click(container.querySelector('.scrim')!)
    expect(onCancel).toHaveBeenCalledOnce()
  })
})
