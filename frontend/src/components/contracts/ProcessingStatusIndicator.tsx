/**
 * ProcessingStatusIndicator component.
 *
 * Displays real-time processing status with a progress bar and stage indicator.
 * Uses SSE to receive updates from the backend.
 */

import React, { useEffect } from 'react';
import { useProcessingStatus, ProcessingStage } from '../../hooks/useProcessingStatus';

interface ProcessingStatusIndicatorProps {
  contractId: string;
  /** Whether to auto-connect when mounted */
  autoConnect?: boolean;
  /** Callback when processing completes */
  onComplete?: () => void;
  /** Callback when processing fails */
  onError?: (error: string) => void;
  /** Custom class name */
  className?: string;
}

// Stage icons for visual feedback
const stageIcons: Record<ProcessingStage, string> = {
  queued: '\u23F3',      // hourglass
  parsing: '\uD83D\uDCC4',    // document
  chunking: '\u2702\uFE0F',    // scissors
  classifying: '\uD83C\uDFF7\uFE0F', // label
  metadata: '\uD83D\uDCCB',   // clipboard
  custom_fields: '\u2699\uFE0F', // gear
  risk: '\u26A0\uFE0F',       // warning
  knowledge_graph: '\uD83D\uDD17', // link
  completed: '\u2705',   // check mark
  failed: '\u274C',      // X mark
  idle: '\u23F8\uFE0F',       // pause
};

export function ProcessingStatusIndicator({
  contractId,
  autoConnect = false,
  onComplete,
  onError,
  className = '',
}: ProcessingStatusIndicatorProps) {
  const { progress, isProcessing, connect } = useProcessingStatus({
    onComplete: () => onComplete?.(),
    onError: (err) => onError?.(err),
  });

  // Auto-connect if specified
  useEffect(() => {
    if (autoConnect && contractId) {
      connect(contractId);
    }
  }, [autoConnect, contractId, connect]);

  // Don't render if not processing and no progress
  if (!progress || progress.stage === 'idle') {
    return null;
  }

  const icon = stageIcons[progress.stage] || '\uD83D\uDD04';

  return (
    <div className={`processing-status-indicator ${className}`}>
      <div className="processing-status-header">
        <span className="processing-status-icon">{icon}</span>
        <span className="processing-status-title">
          {progress.stage_description || 'Processing...'}
        </span>
      </div>

      {/* Progress bar */}
      <div className="processing-status-progress">
        <div
          className="processing-status-progress-bar"
          style={{ width: `${progress.progress_percent}%` }}
        />
      </div>

      {/* Stage message */}
      <div className="processing-status-message">
        {progress.message}
      </div>

      {/* Error message */}
      {progress.error && (
        <div className="processing-status-error">
          {progress.error}
        </div>
      )}

      <style>{`
        .processing-status-indicator {
          padding: 12px 16px;
          background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
          border-radius: 8px;
          border: 1px solid #e2e8f0;
          margin-bottom: 16px;
        }

        .processing-status-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }

        .processing-status-icon {
          font-size: 18px;
        }

        .processing-status-title {
          font-weight: 600;
          color: #1e293b;
        }

        .processing-status-progress {
          height: 6px;
          background: #e2e8f0;
          border-radius: 3px;
          overflow: hidden;
          margin-bottom: 8px;
        }

        .processing-status-progress-bar {
          height: 100%;
          background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
          border-radius: 3px;
          transition: width 0.3s ease-out;
        }

        .processing-status-message {
          font-size: 13px;
          color: #64748b;
        }

        .processing-status-error {
          margin-top: 8px;
          padding: 8px 12px;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 4px;
          color: #dc2626;
          font-size: 13px;
        }

        /* Completed state */
        .processing-status-indicator:has(.processing-status-progress-bar[style*="100%"]) {
          background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
          border-color: #bbf7d0;
        }

        /* Failed state */
        .processing-status-indicator:has(.processing-status-error) {
          background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
          border-color: #fecaca;
        }
      `}</style>
    </div>
  );
}

/**
 * Compact version for use in contract cards or lists.
 */
export function ProcessingStatusBadge({
  contractId,
  autoConnect = false,
}: {
  contractId: string;
  autoConnect?: boolean;
}) {
  const { progress, connect } = useProcessingStatus();

  useEffect(() => {
    if (autoConnect && contractId) {
      connect(contractId);
    }
  }, [autoConnect, contractId, connect]);

  if (!progress || progress.stage === 'idle' || progress.stage === 'completed') {
    return null;
  }

  const icon = stageIcons[progress.stage] || '\uD83D\uDD04';

  return (
    <span
      className="processing-status-badge"
      title={progress.message}
    >
      <span className="processing-badge-icon">{icon}</span>
      <span className="processing-badge-percent">{progress.progress_percent}%</span>

      <style>{`
        .processing-status-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 2px 8px;
          background: #dbeafe;
          border-radius: 12px;
          font-size: 12px;
          color: #1e40af;
        }

        .processing-badge-icon {
          font-size: 12px;
        }

        .processing-badge-percent {
          font-weight: 500;
        }
      `}</style>
    </span>
  );
}

export default ProcessingStatusIndicator;
