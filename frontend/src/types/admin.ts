// SLA Master Data types
export interface SLAMasterData {
  id: string
  reference_code: string
  name: string
  description: string | null
  target_value: number
  minimum_value: number | null
  typical_performance: number | null
  volatility: number | null
  category: string | null
  service_tower: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SLAMasterDataCreate {
  reference_code: string
  name: string
  description?: string
  target_value: number
  minimum_value?: number
  typical_performance?: number
  volatility?: number
  category?: string
  service_tower?: string
  is_active?: boolean
}

export interface SLAMasterDataUpdate {
  reference_code?: string
  name?: string
  description?: string
  target_value?: number
  minimum_value?: number
  typical_performance?: number
  volatility?: number
  category?: string
  service_tower?: string
  is_active?: boolean
}

export interface SLAMasterDataListResponse {
  items: SLAMasterData[]
  total: number
}

// Milestone Master Data types
export interface MilestoneMasterData {
  id: string
  milestone_code: string
  name: string
  description: string | null
  baseline_days_from_start: number
  dependencies: string[]
  credit_at_risk: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MilestoneMasterDataCreate {
  milestone_code: string
  name: string
  description?: string
  baseline_days_from_start: number
  dependencies?: string[]
  credit_at_risk?: number
  is_active?: boolean
}

export interface MilestoneMasterDataUpdate {
  milestone_code?: string
  name?: string
  description?: string
  baseline_days_from_start?: number
  dependencies?: string[]
  credit_at_risk?: number
  is_active?: boolean
}

export interface MilestoneMasterDataListResponse {
  items: MilestoneMasterData[]
  total: number
}

// Seed result
export interface SeedResultResponse {
  seeded: number
  skipped: number
  message: string
}

// Scheduler types
export type SchedulerJobStatus = 'success' | 'failed' | 'running' | 'skipped'

export interface SchedulerJob {
  id: string
  job_name: string
  job_type: string
  description: string | null
  interval_seconds: number
  is_enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  last_run_status: SchedulerJobStatus | null
  last_run_duration_ms: number | null
  last_run_error: string | null
  total_runs: number
  successful_runs: number
  failed_runs: number
  created_at: string
  updated_at: string
}

export interface SchedulerJobUpdate {
  interval_seconds?: number
  is_enabled?: boolean
  description?: string
}

export interface SchedulerJobListResponse {
  items: SchedulerJob[]
  total: number
}

export interface SchedulerJobHistory {
  id: string
  job_id: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  status: SchedulerJobStatus
  error_message: string | null
  items_processed: number | null
  run_metadata: Record<string, unknown> | null
}

export interface SchedulerJobHistoryListResponse {
  items: SchedulerJobHistory[]
  total: number
}

export interface SchedulerStatus {
  is_running: boolean
  started_at: string | null
  total_jobs: number
  enabled_jobs: number
  disabled_jobs: number
  jobs_running: number
  next_job_run: string | null
  next_job_name: string | null
}

export interface SchedulerRunResponse {
  job_name: string
  triggered: boolean
  message: string
  execution_id: string | null
}
