// Regulatory-compliance engine types (mirror backend app/schemas/compliance.py)

export interface ComplianceDashboardSummary {
  total_contracts: number
  contracts_by_industry: Record<string, number>
  total_gaps: number
  gaps_by_severity: Record<string, number>
  gaps_by_status: Record<string, number>
  overdue_gaps: number
  average_compliance_score: number
  critical_gaps_count: number
  regulatory_obligations_count: number
  obligations_needing_attention: number
}

export interface RegulatoryObligationSummary {
  id: string
  contract_id: string
  regulation_type: string
  obligation_category: string
  title: string
  compliance_status: string
  next_due_date: string | null
  is_overdue: boolean
}

export interface RegulatoryObligationUpdateStatus {
  compliance_status: string
  compliance_notes?: string | null
  compliance_evidence?: string | null
  next_due_date?: string | null
  last_completed_date?: string | null
}

export interface IndustryComplianceSummary {
  industry: string
  contract_count: number
  average_compliance_score: number
  total_gaps: number
  critical_gaps: number
  high_gaps: number
  open_gaps: number
  resolved_gaps: number
}

export interface ContractComplianceSummary {
  contract_id: string
  filename: string
  counterparty: string | null
  detected_industry: string | null
  industry_confidence: number | null
  compliance_score: number | null
  last_compliance_check: string | null
  open_gaps_count: number
  critical_gaps_count: number
  regulatory_obligations_count: number
}
