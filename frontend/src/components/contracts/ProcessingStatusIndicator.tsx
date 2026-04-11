/**
 * ProcessingStatusIndicator component.
 *
 * Displays real-time processing status with a full pipeline visualization.
 * Uses SSE to receive updates from the backend.
 */

import { useEffect, useMemo } from 'react'
import { useProcessingStatus, type ProcessingStage, type StageInfo } from '../../hooks/useProcessingStatus'
import {
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ClockIcon,
} from '@heroicons/react/24/solid'
import { cn } from '@/lib/utils'

interface ProcessingStatusIndicatorProps {
  contractId: string
  autoConnect?: boolean
  onComplete?: () => void
  onError?: (error: string) => void
  className?: string
  /** Compact mode — just progress bar, no stage list */
  compact?: boolean
}

// Group stages into logical phases for cleaner display
const STAGE_GROUPS: { label: string; stages: string[] }[] = [
  {
    label: 'Document Ingestion',
    stages: ['queued', 'parsing', 'chunking', 'classifying'],
  },
  {
    label: 'Metadata & Risk',
    stages: ['metadata', 'custom_fields', 'risk', 'knowledge_graph'],
  },
  {
    label: 'Deep Analysis',
    stages: ['clause_extraction', 'obligation_detection', 'sla_extraction', 'renewal_analysis'],
  },
  {
    label: 'Intelligence',
    stages: ['schema_extraction', 'link_detection', 'compliance_check', 'governance_bridge'],
  },
]

function getStageStatus(
  stageId: string,
  currentStage: ProcessingStage,
  stages: StageInfo[]
): 'completed' | 'active' | 'pending' | 'failed' {
  if (currentStage === 'failed') {
    const currentIdx = stages.findIndex((s) => s.id === currentStage)
    const stageIdx = stages.findIndex((s) => s.id === stageId)
    if (stageIdx < currentIdx) return 'completed'
    if (stageId === currentStage) return 'failed'
    return 'pending'
  }

  if (currentStage === 'completed') return 'completed'

  const currentIdx = stages.findIndex((s) => s.id === currentStage)
  const stageIdx = stages.findIndex((s) => s.id === stageId)

  if (stageIdx < currentIdx) return 'completed'
  if (stageIdx === currentIdx) return 'active'
  return 'pending'
}

function StageIcon({ status }: { status: 'completed' | 'active' | 'pending' | 'failed' }) {
  if (status === 'completed') {
    return <CheckCircleIcon className="h-4 w-4 text-green-500" />
  }
  if (status === 'active') {
    return <ArrowPathIcon className="h-4 w-4 text-violet-600 animate-spin" />
  }
  if (status === 'failed') {
    return <XCircleIcon className="h-4 w-4 text-red-500" />
  }
  return <ClockIcon className="h-4 w-4 text-gray-300" />
}

export function ProcessingStatusIndicator({
  contractId,
  autoConnect = false,
  onComplete,
  onError,
  className = '',
  compact = false,
}: ProcessingStatusIndicatorProps) {
  const { progress, connect } = useProcessingStatus({
    onComplete: () => onComplete?.(),
    onError: (err) => onError?.(err),
  })

  useEffect(() => {
    if (autoConnect && contractId) {
      connect(contractId)
    }
  }, [autoConnect, contractId, connect])

  const stages = useMemo(() => progress?.stages || [], [progress?.stages])

  if (!progress || progress.stage === 'idle') {
    return null
  }

  const isFailed = progress.stage === 'failed'
  const isCompleted = progress.stage === 'completed'
  const percent = progress.progress_percent

  return (
    <div
      className={cn(
        'rounded-lg border p-4',
        isFailed
          ? 'bg-red-50 border-red-200'
          : isCompleted
            ? 'bg-green-50 border-green-200'
            : 'bg-white border-gray-200',
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {isFailed ? (
            <XCircleIcon className="h-5 w-5 text-red-500" />
          ) : isCompleted ? (
            <CheckCircleIcon className="h-5 w-5 text-green-500" />
          ) : (
            <ArrowPathIcon className="h-5 w-5 text-violet-600 animate-spin" />
          )}
          <span
            className={cn(
              'text-sm font-semibold',
              isFailed ? 'text-red-800' : isCompleted ? 'text-green-800' : 'text-gray-900'
            )}
          >
            {progress.stage_description || 'Processing...'}
          </span>
        </div>
        <span
          className={cn(
            'text-sm font-medium',
            isFailed ? 'text-red-600' : isCompleted ? 'text-green-600' : 'text-violet-600'
          )}
        >
          {percent}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-2">
        <div
          className={cn(
            'h-full rounded-full transition-all duration-500 ease-out',
            isFailed
              ? 'bg-red-500'
              : isCompleted
                ? 'bg-green-500'
                : 'bg-gradient-to-r from-violet-500 to-violet-400'
          )}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Status message */}
      <p
        className={cn(
          'text-xs',
          isFailed ? 'text-red-600' : isCompleted ? 'text-green-600' : 'text-gray-500'
        )}
      >
        {progress.message}
      </p>

      {/* Error details */}
      {progress.error && (
        <div className="mt-2 p-2 bg-red-100 rounded text-xs text-red-700">{progress.error}</div>
      )}

      {/* Stage pipeline (non-compact only) */}
      {!compact && stages.length > 0 && !isCompleted && (
        <div className="mt-4 space-y-3">
          {STAGE_GROUPS.map((group) => {
            const groupStages = group.stages.filter((s) => stages.some((st) => st.id === s))
            if (groupStages.length === 0) return null

            return (
              <div key={group.label}>
                <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-1">
                  {group.label}
                </p>
                <div className="grid grid-cols-4 gap-1">
                  {groupStages.map((stageId) => {
                    const stage = stages.find((s) => s.id === stageId)
                    const status = getStageStatus(stageId, progress.stage, stages)
                    return (
                      <div
                        key={stageId}
                        className={cn(
                          'flex items-center gap-1 px-2 py-1 rounded text-[11px]',
                          status === 'completed' && 'bg-green-50 text-green-700',
                          status === 'active' && 'bg-violet-50 text-violet-700 font-medium',
                          status === 'pending' && 'bg-gray-50 text-gray-400',
                          status === 'failed' && 'bg-red-50 text-red-600'
                        )}
                      >
                        <StageIcon status={status} />
                        <span className="truncate">{stage?.label || stageId}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * Compact badge for use in file list items.
 */
export function ProcessingStatusBadge({
  contractId,
  autoConnect = false,
}: {
  contractId: string
  autoConnect?: boolean
}) {
  const { progress, connect } = useProcessingStatus()

  useEffect(() => {
    if (autoConnect && contractId) {
      connect(contractId)
    }
  }, [autoConnect, contractId, connect])

  if (!progress || progress.stage === 'idle' || progress.stage === 'completed') {
    return null
  }

  const isFailed = progress.stage === 'failed'

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
        isFailed ? 'bg-red-100 text-red-700' : 'bg-violet-100 text-violet-700'
      )}
      title={progress.message}
    >
      {isFailed ? (
        <XCircleIcon className="h-3 w-3" />
      ) : (
        <ArrowPathIcon className="h-3 w-3 animate-spin" />
      )}
      {progress.progress_percent}%
    </span>
  )
}

export default ProcessingStatusIndicator
