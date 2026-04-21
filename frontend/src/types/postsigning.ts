// Post-Signing Dashboard Types

// Obligation Compliance Types
export interface ObligationWidget {
  total: number
  completed: number
  in_progress: number
  overdue: number
  at_risk: number
  compliance_rate: number
  green: number
  amber: number
  red: number
  urgent_items: UrgentItem[]
}

export interface UrgentItem {
  id: string
  title: string
  due_date: string | null
  status: string
  rag: string | null
}

// SLA Types
export interface SLAWidget {
  total_slas: number
  active_slas: number
  compliant: number
  breached: number
  compliance_rate: number
  critical_breaches: number
  total_penalties_mtd: number
  recent_breaches: SLABreachItem[]
}

export interface SLABreachItem {
  sla_id: string
  sla_name: string
  contract_id: string
  contract: string
  breaches: number
  severity: string
  metric_type?: string
  metric_unit?: string
  target_value?: number
  actual_value?: number
  target_display?: string
  actual_display?: string
  deviation?: number
  measured_at?: string
  penalty_amount?: number | null
}

export interface SLADetail {
  id: string
  contract_id: string
  contract_filename?: string
  counterparty?: string | null
  sla_name: string
  sla_description?: string | null
  metric_type: string
  metric_unit?: string
  target_value: number
  target_operator?: string
  warning_threshold?: number | null
  severity: string
  has_penalty: boolean
  penalty_type?: string | null
  penalty_value?: number | null
  penalty_description?: string | null
  max_penalty_cap?: number | null
  measurement_period?: string | null
  is_active?: boolean
  compliance_rate?: number | null
  current_compliance_rate?: number | null
  consecutive_breaches: number
  source_text?: string | null
  compliance_trend?: string | null
  recent_performances?: {
    id: string
    actual_value: number
    measured_at: string
    is_compliant: boolean
    deviation_percentage: number | null
  }[]
}

// Renewal Types
export interface RenewalWidget {
  expiring_30_days: number
  expiring_60_days: number
  expiring_90_days: number
  past_notice_deadline: number
  total_value_at_risk: number
  upcoming_renewals: UpcomingRenewal[]
}

export interface UpcomingRenewal {
  contract_id: string
  filename: string
  counterparty: string | null
  expiration_date: string | null
  value: number | null
  auto_renewal: boolean | null
}

export interface RenewalCalendar {
  as_of_date: string
  total_contracts: number
  expired: ContractRenewalInfo[]
  critical: ContractRenewalInfo[]
  within_30_days: ContractRenewalInfo[]
  within_60_days: ContractRenewalInfo[]
  within_90_days: ContractRenewalInfo[]
  total_value_at_risk: number
  auto_renewal_count: number
  requires_action_count: number
}

export interface ContractRenewalInfo {
  contract_id: string
  filename: string
  counterparty: string | null
  contract_type: string | null
  contract_value: number | null
  effective_date: string | null
  expiration_date: string | null
  notice_deadline: string | null
  auto_renewal: boolean | null
  notice_period_days: number | null
  days_until_expiration: number | null
  days_until_notice_deadline: number | null
  is_past_notice_deadline: boolean
  renewal_window: string
  renewal_status: string | null
  risk_level: string | null
  sla_compliance_rate: number | null
  active_sla_breaches: number
}

// Vendor Types
export interface VendorWidget {
  total_vendors: number
  at_risk_vendors: number
  avg_performance_score: number
  top_performers: VendorScore[]
  bottom_performers: VendorScore[]
}

export interface VendorScore {
  name: string
  score: number
  contracts: number
}

export type CounterpartyType = 'vendor' | 'client' | 'unknown'

export interface VendorListItem {
  vendor_name: string
  normalized_name: string
  party_type: CounterpartyType
  performance_score: number
  risk_level: string
  is_at_risk: boolean
  contract_count: number
  total_exposure: number
  sla_compliance_rate: number | null
  obligation_compliance_rate: number | null
  active_breaches: number
  last_updated: string
}

export interface VendorPerformanceDetail {
  vendor_name: string
  performance_score: number
  risk_level: string
  is_at_risk: boolean
  score_breakdown: {
    obligation_compliance_score: number
    sla_compliance_score: number
    responsiveness_score: number
    issue_rate_score: number
    weighted_total: number
  }
  contracts: {
    total_contracts: number
    active_contracts: number
    total_value: number
  }
  obligations: {
    total_obligations: number
    completed_obligations: number
    overdue_obligations: number
    compliance_rate: number
  }
  slas: {
    total_slas: number
    compliance_rate: number
    total_breaches: number
    total_penalties: number
  }
  risk_factors: string[]
  recommended_actions: string[]
}

// Milestone Types
export interface MilestoneWidget {
  total_milestones: number
  completed: number
  at_risk: number
  overdue: number
  completion_rate: number
  due_this_week: MilestoneItem[]
}

export interface MilestoneItem {
  id: string
  title: string
  due_date: string | null
  status: string
}

export interface MilestoneHealth {
  as_of_date: string
  total_milestones: number
  by_status: {
    pending: number
    in_progress: number
    completed: number
    overdue: number
    waived: number
  }
  at_risk_count: number
  at_risk_milestones: MilestoneDetail[]
  completion_rate: number
  on_track_rate: number
}

export interface MilestoneDetail {
  milestone_id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  title: string
  description: string | null
  category: string | null
  owner: string | null
  due_date: string | null
  status: string
  rag_status: string | null
  is_at_risk: boolean
  days_until_due: number | null
  days_overdue: number | null
  time_bucket: string
}

// Compliance Types
export interface ComplianceWidget {
  overall_compliance_rate: number
  obligation_compliance_rate: number
  sla_compliance_rate: number
  trend: 'improving' | 'stable' | 'declining' | null
  change_from_last_month: number | null
  contracts_at_risk: number
  high_priority_actions: number
}

export interface ComplianceReport {
  summary: {
    report_period_start: string
    report_period_end: string
    total_obligations: number
    obligations_completed: number
    obligations_overdue: number
    obligation_compliance_rate: number
    total_slas: number
    slas_compliant: number
    slas_breached: number
    sla_compliance_rate: number
    total_penalties: number
    overall_compliance_rate: number
    contracts_reviewed: number
    high_risk_contracts: number
  }
  by_contract: Record<string, {
    filename: string
    obligation_rate: number
    sla_rate: number
  }>
}

export interface ComplianceTrend {
  trend_type: 'weekly' | 'monthly'
  data_points: TrendDataPoint[]
  obligation_trend: 'improving' | 'stable' | 'declining'
  sla_trend: 'improving' | 'stable' | 'declining'
  overall_trend: 'improving' | 'stable' | 'declining'
  obligation_change_pct: number
  sla_change_pct: number
  overall_change_pct: number
}

export interface TrendDataPoint {
  period_start: string
  period_end: string
  period_label: string
  obligation_compliance_rate: number
  sla_compliance_rate: number
  overall_compliance_rate: number
  obligations_completed: number
  obligations_overdue: number
  sla_breaches: number
  penalties: number
}

// Full Post-Signing Dashboard
export interface PostSigningDashboard {
  generated_at: string
  as_of_date: string
  obligations: ObligationWidget
  slas: SLAWidget
  renewals: RenewalWidget
  vendors: VendorWidget
  milestones: MilestoneWidget
  compliance: ComplianceWidget
  total_contracts: number
  total_value: number
  contracts_needing_attention: number
  priority_actions: PriorityAction[]
}

export interface PriorityAction {
  type: 'obligation' | 'sla' | 'renewal'
  severity: string
  title: string
  action: string
  due_date?: string
  contract?: string
  expiration?: string
}
