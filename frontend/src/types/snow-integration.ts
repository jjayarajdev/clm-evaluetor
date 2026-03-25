export interface SnowConfig {
  id: string
  tenant_id: string | null
  system: string
  name: string
  description: string | null
  base_url: string
  auth_type: string // 'basic' | 'oauth2'
  is_active: boolean
  health_status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  last_health_check: string | null
  last_health_message: string | null
  last_used_at: string | null
  total_requests: number
  failed_requests: number
  created_at: string
  updated_at: string
}

export interface SnowConfigCreate {
  name: string
  base_url: string
  auth_type: string
  credentials: {
    username?: string
    password?: string
    client_id?: string
    client_secret?: string
    token_url?: string
  }
  config?: Record<string, unknown>
}

export interface SnowSLAMapping {
  id: string
  tenant_id: string
  integration_config_id: string
  snow_sys_id: string
  platform_sla_id: string | null
  snow_sla_name: string
  snow_metric_type: string | null
  snow_target: string | null
  mapping_status: 'pending' | 'mapped' | 'ignored' | 'error'
  last_synced_at: string | null
  sync_metadata: Record<string, unknown> | null
  created_at: string
}

export interface SnowSyncResult {
  fetched: number
  created: number
  updated: number
  errors: number
}

export interface SnowConnectionTest {
  healthy: boolean
  message: string
}

export interface SnowAdminOverview {
  tenant_id: string
  tenant_name: string
  config: SnowConfig | null
  mapping_count: number
  last_sync: string | null
}

export interface SnowIntegrationLog {
  id: string
  operation: string
  method: string
  endpoint: string
  status_code: number | null
  is_success: boolean
  error_message: string | null
  duration_ms: number | null
  started_at: string
  external_id: string | null
}
