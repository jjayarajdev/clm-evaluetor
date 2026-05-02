import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { getTenantConfig } from '@/lib/api/admin'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContractTypeConfig {
  code: string
  label: string
  description?: string
  icon?: string
}

export interface ClauseTypeConfig {
  code: string
  label: string
  category?: string
  risk_weight?: number
  description?: string
}

export interface RiskCategoryConfig {
  code: string
  label: string
  severity?: string
  weight?: number
  description?: string
}

export interface SLAMetricConfig {
  code: string
  label: string
  unit?: string
  direction?: 'higher_is_better' | 'lower_is_better'
  default_target?: number
  description?: string
}

export interface FieldDef {
  key: string
  label: string
  type: string
  suffix?: string
}

export interface FieldSection {
  section: string
  fields: FieldDef[]
}

export interface TableColumn {
  key: string
  label: string
  width?: number
  format?: string
}

export interface DashboardWidget {
  key: string
  label: string
  icon?: string
  color?: string
  format?: string
}

export interface DetailTab {
  id: string
  label: string
  icon?: string
}

export interface UIConfig {
  table_columns?: TableColumn[]
  dashboard_widgets?: DashboardWidget[]
  detail_tabs?: DetailTab[]
  filters?: string[]
  labels?: Record<string, string>
}

export interface TenantConfig {
  industry: string | null
  industry_name: string | null
  contract_types: ContractTypeConfig[]
  clause_types: ClauseTypeConfig[]
  risk_categories: RiskCategoryConfig[]
  sla_metrics: SLAMetricConfig[]
  field_definitions: Record<string, FieldSection[]>
  extraction_hints: Record<string, string>
  ui: UIConfig
  tenant_id?: string
  tenant_name?: string
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface TenantConfigContextType {
  config: TenantConfig | null
  isLoading: boolean
  error: string | null
  refresh: () => Promise<void>

  // Convenience accessors
  contractTypeLabel: (code: string) => string
  clauseTypeLabel: (code: string) => string
  riskCategoryLabel: (code: string) => string
  uiLabel: (key: string, fallback?: string) => string
}

const TenantConfigContext = createContext<TenantConfigContextType | undefined>(undefined)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function TenantConfigProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [config, setConfig] = useState<TenantConfig | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchConfig = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getTenantConfig()
      setConfig(data)
    } catch (err: any) {
      console.error('Failed to load tenant config:', err)
      setError(err?.message || 'Failed to load tenant configuration')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Fetch config when user logs in (or changes)
  useEffect(() => {
    if (user) {
      fetchConfig()
    } else {
      setConfig(null)
    }
  }, [user, fetchConfig])

  // Convenience: map code → label
  const contractTypeLabel = useCallback(
    (code: string) => {
      const ct = config?.contract_types?.find((t) => t.code === code)
      return ct?.label || code?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    },
    [config]
  )

  const clauseTypeLabel = useCallback(
    (code: string) => {
      const ct = config?.clause_types?.find((t) => t.code === code)
      return ct?.label || code?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    },
    [config]
  )

  const riskCategoryLabel = useCallback(
    (code: string) => {
      const rc = config?.risk_categories?.find((r) => r.code === code)
      return rc?.label || code?.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
    },
    [config]
  )

  const uiLabel = useCallback(
    (key: string, fallback?: string) => {
      return config?.ui?.labels?.[key] || fallback || key
    },
    [config]
  )

  const value: TenantConfigContextType = {
    config,
    isLoading,
    error,
    refresh: fetchConfig,
    contractTypeLabel,
    clauseTypeLabel,
    riskCategoryLabel,
    uiLabel,
  }

  return <TenantConfigContext.Provider value={value}>{children}</TenantConfigContext.Provider>
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useTenantConfig() {
  const context = useContext(TenantConfigContext)
  if (context === undefined) {
    throw new Error('useTenantConfig must be used within a TenantConfigProvider')
  }
  return context
}
