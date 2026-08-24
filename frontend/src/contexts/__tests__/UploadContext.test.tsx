/* Focused unit tests for the UploadContext job-state lifecycle:
   upload result mapping (accepted / duplicate / rejected), processing poll
   transitions (completed / failed), and queue maintenance actions. */
import { render, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ToastProvider } from '@/components/ui/Toast'
import { UploadProvider, useUploads } from '@/contexts/UploadContext'

vi.mock('@/lib/api', () => ({
  default: {
    uploadFile: vi.fn(),
    uploadFiles: vi.fn(),
    getContract: vi.fn(),
    getProcessingStatusCurrent: vi.fn(),
    getProcessingQueueStatus: vi.fn(),
    getSuggestedLinks: vi.fn(),
    processContract: vi.fn(),
  },
}))

import api from '@/lib/api'

const mocked = api as unknown as {
  uploadFile: ReturnType<typeof vi.fn>
  uploadFiles: ReturnType<typeof vi.fn>
  getContract: ReturnType<typeof vi.fn>
  getProcessingStatusCurrent: ReturnType<typeof vi.fn>
  getProcessingQueueStatus: ReturnType<typeof vi.fn>
  getSuggestedLinks: ReturnType<typeof vi.fn>
  processContract: ReturnType<typeof vi.fn>
}

/** Captures the context value so tests can drive it directly. */
let ctx: ReturnType<typeof useUploads>
function Capture() {
  ctx = useUploads()
  return null
}

function renderProvider() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <UploadProvider>
            <Capture />
          </UploadProvider>
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const file = (name: string, size = 100) =>
  new File([new Uint8Array(size)], name, { type: 'application/pdf' })

beforeEach(() => {
  vi.clearAllMocks()
  // Quiet defaults for the polling endpoints
  mocked.getProcessingStatusCurrent.mockResolvedValue({
    contract_id: 'c1',
    stage: 'idle',
    stage_description: '',
    progress_percent: 0,
  })
  mocked.getProcessingQueueStatus.mockResolvedValue({
    queue_depth: 0,
    processing: 0,
    avg_job_seconds: 0,
    jobs: [],
  })
  mocked.getSuggestedLinks.mockResolvedValue({ pending_count: 0 })
})

describe('UploadContext', () => {
  it('maps batch upload results to queued / duplicate / failed jobs', async () => {
    mocked.uploadFiles.mockResolvedValue({
      batch_id: 'b1',
      total_files: 3,
      accepted: 2,
      rejected: 1,
      files: [
        { id: 'c1', filename: 'a.pdf', status: 'accepted', message: 'ok' },
        {
          id: 'c2',
          filename: 'b.pdf',
          status: 'accepted',
          message: 'ok',
          duplicate_of_filename: 'old-b.pdf',
        },
        { id: '', filename: 'c.pdf', status: 'rejected', message: 'unsupported' },
      ],
    })
    // Keep tracked jobs in-flight so mapping states are observable
    mocked.getContract.mockResolvedValue({ id: 'c1', status: 'processing' })

    renderProvider()
    await act(async () => {
      await ctx.startUploads([file('a.pdf'), file('b.pdf'), file('c.pdf')], {
        clientId: 'client-1',
        groupName: 'Q3 uploads',
      })
    })

    expect(mocked.uploadFiles).toHaveBeenCalledWith(
      [expect.any(File), expect.any(File), expect.any(File)],
      'client-1',
      'Q3 uploads',
      undefined,
    )

    const [a, b, c] = ctx.jobs
    expect(a.contractId).toBe('c1')
    expect(['queued', 'processing']).toContain(a.state)
    expect(b.contractId).toBe('c2')
    expect(b.warning).toBeTruthy()
    expect(['duplicate', 'processing']).toContain(b.state)
    expect(c.state).toBe('failed')
    expect(c.error).toBeTruthy()
  })

  it('prefers an existing group id over creating one by name', async () => {
    mocked.uploadFiles.mockResolvedValue({
      batch_id: 'b1',
      total_files: 1,
      accepted: 1,
      rejected: 0,
      files: [{ id: 'c1', filename: 'a.pdf', status: 'accepted', message: 'ok' }],
    })
    mocked.getContract.mockResolvedValue({ id: 'c1', status: 'processing' })

    renderProvider()
    await act(async () => {
      await ctx.startUploads([file('a.pdf')], { groupName: 'ignored', groupId: 'g1' })
    })

    expect(mocked.uploadFiles).toHaveBeenCalledWith([expect.any(File)], undefined, undefined, 'g1')
  })

  it('completes jobs from the contract poll with extraction counts and suggestions', async () => {
    mocked.uploadFiles.mockResolvedValue({
      batch_id: 'b1',
      total_files: 1,
      accepted: 1,
      rejected: 0,
      files: [{ id: 'c1', filename: 'a.pdf', status: 'accepted', message: 'ok' }],
    })
    mocked.getContract.mockResolvedValue({
      id: 'c1',
      status: 'completed',
      clause_count: 5,
      obligation_count: 2,
    })
    mocked.getSuggestedLinks.mockResolvedValue({ pending_count: 3 })

    renderProvider()
    await act(async () => {
      await ctx.startUploads([file('a.pdf')])
    })

    await waitFor(() => expect(ctx.jobs[0].state).toBe('completed'))
    expect(ctx.jobs[0].clauseCount).toBe(5)
    expect(ctx.jobs[0].obligationCount).toBe(2)
    expect(ctx.jobs[0].progressPercent).toBe(100)
    await waitFor(() => expect(ctx.jobs[0].hasSuggestions).toBe(true))
    expect(ctx.jobs[0].suggestionCount).toBe(3)
  })

  it('marks jobs failed when processing fails, and clearFinished removes them', async () => {
    mocked.uploadFiles.mockResolvedValue({
      batch_id: 'b1',
      total_files: 1,
      accepted: 1,
      rejected: 0,
      files: [{ id: 'c1', filename: 'a.pdf', status: 'accepted', message: 'ok' }],
    })
    mocked.getContract.mockResolvedValue({
      id: 'c1',
      status: 'failed',
      processing_error: 'boom',
    })

    renderProvider()
    await act(async () => {
      await ctx.startUploads([file('a.pdf')])
    })

    await waitFor(() => expect(ctx.jobs[0].state).toBe('failed'))
    expect(ctx.jobs[0].error).toBe('boom')

    act(() => ctx.clearFinished())
    expect(ctx.jobs).toHaveLength(0)
  })

  it('fails single uploads on network error and supports dismissJob', async () => {
    mocked.uploadFile.mockRejectedValue(new Error('network down'))

    renderProvider()
    await act(async () => {
      await ctx.startUploads([file('a.pdf')], { single: true })
    })

    expect(mocked.uploadFile).toHaveBeenCalledTimes(1)
    expect(ctx.jobs[0].state).toBe('failed')
    expect(ctx.jobs[0].error).toBe('network down')

    const id = ctx.jobs[0].id
    act(() => ctx.dismissJob(id))
    expect(ctx.jobs).toHaveLength(0)
  })

  it('re-queues a failed contract via retryProcessing', async () => {
    mocked.uploadFiles.mockResolvedValue({
      batch_id: 'b1',
      total_files: 1,
      accepted: 1,
      rejected: 0,
      files: [{ id: 'c1', filename: 'a.pdf', status: 'accepted', message: 'ok' }],
    })
    mocked.getContract.mockResolvedValue({
      id: 'c1',
      status: 'failed',
      processing_error: 'boom',
    })
    mocked.processContract.mockResolvedValue(undefined)

    renderProvider()
    await act(async () => {
      await ctx.startUploads([file('a.pdf')])
    })
    await waitFor(() => expect(ctx.jobs[0].state).toBe('failed'))

    // Stop the poll from immediately re-failing the retried job
    mocked.getContract.mockResolvedValue({ id: 'c1', status: 'processing' })
    await act(async () => {
      await ctx.retryProcessing('c1')
    })

    expect(mocked.processContract).toHaveBeenCalledWith('c1')
    expect(['queued', 'processing']).toContain(ctx.jobs[0].state)
    expect(ctx.jobs[0].error).toBeUndefined()
  })
})
