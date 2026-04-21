import { client } from './client'
import type {
  PostSigningDashboard,
  RenewalCalendar,
  VendorListItem,
  VendorPerformanceDetail,
  MilestoneHealth,
  ComplianceReport,
  ComplianceTrend,
  SLADetail,
} from '@/types/postsigning'

// ============ POST-SIGNING DASHBOARD ============

export async function getPostSigningDashboard(): Promise<PostSigningDashboard> {
  const response = await client.get<PostSigningDashboard>('/dashboard/postsigning')
  return response.data
}

export async function getPostSigningObligations(filters?: { status?: string; rag?: string }): Promise<unknown[]> {
  const response = await client.get('/dashboard/postsigning/obligations', { params: filters })
  return response.data
}

export async function getPostSigningSLAs(filters?: { breached_only?: boolean }): Promise<unknown[]> {
  const response = await client.get('/dashboard/postsigning/slas', { params: filters })
  return response.data
}

// ============ RENEWAL ENDPOINTS ============

export async function getRenewalCalendar(): Promise<RenewalCalendar> {
  const response = await client.get<RenewalCalendar>('/renewals/calendar')
  return response.data
}

export async function getAtRiskRenewals(): Promise<{ total_at_risk: number; total_value_at_risk: number; contracts: unknown[] }> {
  const response = await client.get('/renewals/at-risk')
  return response.data
}

export async function getRenewalSummary(): Promise<unknown> {
  const response = await client.get('/renewals/summary')
  return response.data
}

export async function updateRenewalStatus(contractId: string, data: {
  renewal_status: string
  decision_notes?: string
  new_expiration_date?: string
}): Promise<unknown> {
  const response = await client.put(`/renewals/${contractId}/status`, data)
  return response.data
}

export async function getRenewalRecommendation(contractId: string): Promise<unknown> {
  const response = await client.get(`/renewals/${contractId}/recommendation`)
  return response.data
}

// ============ VENDOR/COUNTERPARTY ENDPOINTS ============

export async function getVendors(params?: {
  sort_by?: string
  sort_order?: string
  party_type?: 'all' | 'vendor' | 'client'
}): Promise<{
  total_vendors: number
  at_risk_count: number
  total_exposure: number
  vendors: VendorListItem[]
}> {
  const response = await client.get('/vendors', { params })
  return response.data
}

export async function getVendorPerformance(vendorName: string): Promise<VendorPerformanceDetail> {
  const response = await client.get<VendorPerformanceDetail>(`/vendors/${encodeURIComponent(vendorName)}/performance`)
  return response.data
}

export async function getAtRiskVendors(): Promise<{ total_at_risk: number; vendors: unknown[] }> {
  const response = await client.get('/vendors/at-risk')
  return response.data
}

export async function compareVendors(vendorNames: string[]): Promise<unknown> {
  const response = await client.get('/vendors/compare', {
    params: { vendors: vendorNames.join(',') }
  })
  return response.data
}

export async function getVendorScorecards(limit = 10): Promise<unknown[]> {
  const response = await client.get('/vendors/scorecard', { params: { limit } })
  return response.data
}

// ============ SLA ENDPOINTS ============

export async function getContractSLAs(contractId: string): Promise<SLADetail[]> {
  const response = await client.get<SLADetail[]>(`/sla/${contractId}`)
  return response.data
}

export async function getSLAComplianceSummary(): Promise<unknown> {
  const response = await client.get('/sla/compliance/summary')
  return response.data
}

export async function getActiveSLABreaches(): Promise<unknown> {
  const response = await client.get('/sla/breaches/active')
  return response.data
}

export async function logSLAPerformance(contractId: string, slaId: string, data: {
  actual_value: number
  notes?: string
}): Promise<unknown> {
  const response = await client.post(`/sla/${contractId}/performance/${slaId}`, data)
  return response.data
}

export async function updateSLA(contractId: string, slaId: string, data: {
  sla_name?: string
  sla_description?: string
  metric_type?: string
  metric_unit?: string
  target_value?: number
  target_operator?: string
  warning_threshold?: number | null
  severity?: string
  has_penalty?: boolean
  penalty_type?: string | null
  penalty_value?: number | null
  penalty_description?: string | null
  max_penalty_cap?: number | null
  measurement_period?: string | null
  is_active?: boolean
}): Promise<SLADetail> {
  const response = await client.put<SLADetail>(`/sla/${contractId}/${slaId}`, data)
  return response.data
}

export async function deleteSLA(contractId: string, slaId: string): Promise<void> {
  await client.delete(`/sla/${contractId}/${slaId}`)
}

export async function createSLA(contractId: string, data: {
  sla_name: string
  sla_description?: string
  metric_type: string
  metric_unit: string
  target_value: number
  target_operator?: string
  warning_threshold?: number
  severity?: string
  has_penalty?: boolean
  penalty_type?: string
  penalty_value?: number
  penalty_description?: string
  max_penalty_cap?: number
  measurement_period?: string
  source_text?: string
}): Promise<SLADetail> {
  const response = await client.post<SLADetail>(`/sla/${contractId}`, data)
  return response.data
}

// ============ SLA LIBRARY ============

export interface SLALibraryItem {
  id: string
  reference_code: string
  name: string
  description: string | null
  target_value: number | null
  minimum_value: number | null
  typical_performance: number | null
  category: string | null
  service_tower: string | null
}

export async function getAvailableLibrarySLAs(contractId: string, params?: { category?: string; search?: string }): Promise<SLALibraryItem[]> {
  const response = await client.get(`/sla/${contractId}/library-available`, { params })
  return response.data
}

export async function createSLAFromLibrary(contractId: string, masterDataId: string): Promise<SLADetail> {
  const response = await client.post<SLADetail>(`/sla/${contractId}/from-library/${masterDataId}`)
  return response.data
}

// ============ MILESTONE ENDPOINTS ============

export async function getMilestoneHealth(): Promise<MilestoneHealth> {
  const response = await client.get<MilestoneHealth>('/milestones/health')
  return response.data
}

export async function getAtRiskContracts(): Promise<unknown> {
  const response = await client.get('/milestones/at-risk-contracts')
  return response.data
}

export async function getPortfolioCompliance(): Promise<unknown> {
  const response = await client.get('/milestones/portfolio-compliance')
  return response.data
}

export async function assignMilestoneOwner(milestoneId: string, owner: string, notes?: string): Promise<unknown> {
  const response = await client.put(`/milestones/${milestoneId}/owner`, { owner, notes })
  return response.data
}

// ============ COMPLIANCE REPORT ENDPOINTS ============

export async function getComplianceReport(startDate: string, endDate: string): Promise<ComplianceReport> {
  const response = await client.get<ComplianceReport>('/reports/compliance', {
    params: { start_date: startDate, end_date: endDate }
  })
  return response.data
}

export async function getComplianceTrend(period: 'weekly' | 'monthly' = 'weekly', lookback = 4): Promise<ComplianceTrend> {
  const response = await client.get<ComplianceTrend>('/reports/compliance/trend', {
    params: { period, lookback }
  })
  return response.data
}

export async function exportComplianceReport(startDate: string, endDate: string, format: 'csv' | 'excel' = 'csv'): Promise<Blob> {
  const response = await client.get('/reports/compliance/export', {
    params: { start_date: startDate, end_date: endDate, format },
    responseType: 'blob'
  })
  return response.data
}

// ============ OBLIGATION STATUS UPDATES ============

export async function updateObligationStatus(obligationId: string, data: {
  status: string
  notes?: string
}): Promise<unknown> {
  const response = await client.put(`/obligations/${obligationId}/status`, data)
  return response.data
}

export async function updateObligationRAG(obligationId: string, data: {
  rag_status: string
  compliance_notes?: string
}): Promise<unknown> {
  const response = await client.put(`/obligations/${obligationId}/rag`, data)
  return response.data
}

export async function getObligationComplianceRates(contractId?: string): Promise<unknown> {
  const response = await client.get('/obligations/compliance/rates', {
    params: contractId ? { contract_id: contractId } : undefined
  })
  return response.data
}

export async function uploadObligationEvidence(obligationId: string, data: {
  evidence_description: string
  evidence_date?: string
  file?: File
}): Promise<unknown> {
  const formData = new FormData()
  formData.append('evidence_description', data.evidence_description)
  if (data.evidence_date) {
    formData.append('evidence_date', data.evidence_date)
  }
  if (data.file) {
    formData.append('file', data.file)
  }
  const response = await client.post(`/obligations/${obligationId}/evidence`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

// ============ CALENDAR EXPORT ============

export async function exportCalendarICS(options?: {
  include_expirations?: boolean
  include_notice_deadlines?: boolean
  include_obligations?: boolean
  include_key_dates?: boolean
  days_ahead?: number
}): Promise<Blob> {
  const response = await client.get('/renewals/export/calendar.ics', {
    params: options,
    responseType: 'blob',
  })
  return response.data
}
