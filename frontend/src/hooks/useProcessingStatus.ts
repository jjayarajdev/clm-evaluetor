/**
 * React hook for subscribing to contract processing status via SSE.
 *
 * Provides real-time progress updates when a contract is being processed.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export type ProcessingStage =
  | 'queued'
  | 'parsing'
  | 'chunking'
  | 'classifying'
  | 'metadata'
  | 'custom_fields'
  | 'risk'
  | 'knowledge_graph'
  | 'clause_extraction'
  | 'obligation_detection'
  | 'sla_extraction'
  | 'renewal_analysis'
  | 'schema_extraction'
  | 'link_detection'
  | 'compliance_check'
  | 'governance_bridge'
  | 'completed'
  | 'failed'
  | 'idle';

export interface StageInfo {
  id: string;
  label: string;
  weight: number;
}

export interface ProcessingProgress {
  contract_id: string;
  stage: ProcessingStage;
  stage_description: string;
  progress_percent: number;
  message: string;
  error: string | null;
  started_at?: string;
  updated_at?: string;
  details?: Record<string, unknown>;
  stages?: StageInfo[];
}

interface UseProcessingStatusOptions {
  /** Auto-connect when contractId is provided */
  autoConnect?: boolean;
  /** Callback when processing completes */
  onComplete?: (progress: ProcessingProgress) => void;
  /** Callback when processing fails */
  onError?: (error: string) => void;
  /** Callback for each progress update */
  onProgress?: (progress: ProcessingProgress) => void;
}

interface UseProcessingStatusReturn {
  /** Current processing progress */
  progress: ProcessingProgress | null;
  /** Whether currently connected to SSE stream */
  isConnected: boolean;
  /** Whether processing is in progress */
  isProcessing: boolean;
  /** Connect to SSE stream for a contract */
  connect: (contractId: string) => void;
  /** Disconnect from SSE stream */
  disconnect: () => void;
  /** Reset state */
  reset: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Hook to subscribe to contract processing status updates.
 *
 * @example
 * ```tsx
 * const { progress, isProcessing, connect } = useProcessingStatus({
 *   onComplete: () => toast.success('Processing complete!'),
 *   onError: (err) => toast.error(err),
 * });
 *
 * // Trigger processing and connect
 * const handleAnalyze = async () => {
 *   await api.analyzeContract(contractId);
 *   connect(contractId);
 * };
 *
 * // Show progress bar
 * {isProcessing && (
 *   <ProgressBar value={progress?.progress_percent} />
 * )}
 * ```
 */
export function useProcessingStatus(
  options: UseProcessingStatusOptions = {}
): UseProcessingStatusReturn {
  const { onComplete, onError, onProgress } = options;

  const [progress, setProgress] = useState<ProcessingProgress | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const contractIdRef = useRef<string | null>(null);

  // Cleanup function
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    contractIdRef.current = null;
  }, []);

  // Connect to SSE stream
  const connect = useCallback(
    (contractId: string) => {
      // Disconnect existing connection
      disconnect();

      contractIdRef.current = contractId;
      const token = localStorage.getItem('access_token');
      const url = `${API_BASE_URL}/api/contracts/${contractId}/processing-status`;

      // Create EventSource
      // Note: EventSource doesn't support custom headers, so we use query param
      // For production, consider using fetch-event-source package
      const eventSource = new EventSource(
        token ? `${url}?token=${token}` : url,
        { withCredentials: true }
      );

      eventSource.onopen = () => {
        setIsConnected(true);
      };

      eventSource.onmessage = (event) => {
        try {
          const data: ProcessingProgress = JSON.parse(event.data);
          setProgress(data);

          // Call progress callback
          onProgress?.(data);

          // Handle completion
          if (data.stage === 'completed') {
            onComplete?.(data);
            disconnect();
          }

          // Handle failure
          if (data.stage === 'failed') {
            onError?.(data.error || 'Processing failed');
            disconnect();
          }
        } catch (e) {
          console.error('Failed to parse SSE message:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        setIsConnected(false);

        // Attempt to reconnect after a delay if still processing
        if (contractIdRef.current && progress?.stage !== 'completed' && progress?.stage !== 'failed') {
          setTimeout(() => {
            if (contractIdRef.current) {
              connect(contractIdRef.current);
            }
          }, 3000);
        }
      };

      eventSourceRef.current = eventSource;
    },
    [disconnect, onComplete, onError, onProgress, progress?.stage]
  );

  // Reset state
  const reset = useCallback(() => {
    disconnect();
    setProgress(null);
  }, [disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Compute isProcessing
  const isProcessing =
    progress !== null &&
    progress.stage !== 'completed' &&
    progress.stage !== 'failed' &&
    progress.stage !== 'idle';

  return {
    progress,
    isConnected,
    isProcessing,
    connect,
    disconnect,
    reset,
  };
}

/**
 * Fetch current processing status (non-streaming).
 * Useful for initial state check before connecting to SSE.
 */
export async function getProcessingStatus(
  contractId: string
): Promise<ProcessingProgress> {
  const token = localStorage.getItem('access_token');
  const response = await fetch(
    `${API_BASE_URL}/api/contracts/${contractId}/processing-status/current`,
    {
      headers: {
        Authorization: token ? `Bearer ${token}` : '',
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch processing status: ${response.statusText}`);
  }

  return response.json();
}

export default useProcessingStatus;
