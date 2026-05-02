// User types
export type Role = 'admin' | 'legal' | 'procurement' | 'viewer' | 'super_admin' | 'bu_head'

export interface User {
  id: string
  username: string
  email: string
  full_name?: string | null
  role: Role
  is_active: boolean
  tenant_id?: string | null
  tenant_name?: string | null
  business_unit_id?: string | null
  business_unit_name?: string | null
  created_at: string
  updated_at?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

// Client types
export interface Client {
  id: string
  name: string
  code: string
  industry: string | null
  website: string | null
  address: string | null
  city: string | null
  country: string | null
  contact_name: string | null
  contact_email: string | null
  contact_phone: string | null
  contact_title: string | null
  notes: string | null
  contract_count: number
  created_at: string
  updated_at: string
}

export interface ClientSummary {
  id: string
  name: string
  code: string
  contract_count: number
}

export interface ClientCreate {
  name: string
  code: string
  industry?: string
  website?: string
  address?: string
  city?: string
  country?: string
  contact_name?: string
  contact_email?: string
  contact_phone?: string
  contact_title?: string
  notes?: string
}

// Contract types
export type ContractType = string
export type ContractStatus = 'pending' | 'processing' | 'completed' | 'failed'
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface ContractSummary {
  id: string
  filename: string
  contract_type: ContractType | null
  counterparty: string | null
  status: ContractStatus
  risk_level: RiskLevel | null
  contract_value: number | null
  currency: string | null
  expiration_date: string | null
  uploaded_at: string
}

export interface Contract extends ContractSummary {
  file_path: string
  file_size: number | null
  mime_type: string | null
  effective_date: string | null
  jurisdiction: string | null
  risk_score: number | null
  auto_renewal: boolean | null
  notice_period_days: number | null
  renewal_term_months: number | null
  processing_error: string | null
  uploaded_by: string
  clause_count: number
  obligation_count: number
  sla_count: number
  custom_fields: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface ContractListResponse {
  items: ContractSummary[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Upload types
export interface UploadResponse {
  id: string
  filename: string
  status: string
  message: string
}

export interface BatchUploadResponse {
  batch_id: string
  total_files: number
  accepted: number
  rejected: number
  files: UploadResponse[]
}

// Query types
export interface QueryRequest {
  question: string
  contract_id?: string
  contract_ids?: string[]
  session_id?: string
}

export interface SourceReference {
  contract_id: string
  filename?: string
  chunk_index?: number
  excerpt?: string
  section_number: string | null
  page_start: number | null
  page_end: number | null
  relevance_score: number | null
}

export interface Visualization {
  chart_type: 'bar' | 'pie' | 'timeline' | 'table' | 'stat_cards'
  title: string
  data: any
}

export interface QueryResponse {
  answer: string
  confidence: number
  sources: SourceReference[]
  follow_up_questions: string[]
  session_id: string
  visualizations?: Visualization[]
}

// Additional role type with viewer
export type UserRole = 'admin' | 'legal' | 'procurement' | 'viewer' | 'super_admin' | 'bu_head'

// Dashboard types
export interface AdminDashboard {
  contract_stats: {
    by_type: Record<string, number>
    by_status: Record<string, number>
    total: number
  }
  user_stats: {
    by_role: Record<string, number>
    active: number
    inactive: number
    total: number
  }
  activity: {
    queries_7d: number
    queries_30d: number
    uploads_7d: number
    uploads_30d: number
  }
  ingestion: {
    pending: number
    processing: number
    completed: number
    failed: number
  }
  recent_failures: Array<{
    id: string
    filename: string
    error: string
    timestamp: string
  }>
}

export interface LegalDashboard {
  risk_overview: {
    by_level: Record<string, number>
    high_risk_contracts: Array<{
      id: string
      filename: string
      counterparty: string | null
      risk_score: number
      risk_level: RiskLevel
    }>
  }
  expiration_timeline: {
    next_30_days: ExpirationItem[]
    next_60_days: ExpirationItem[]
    next_90_days: ExpirationItem[]
  }
  high_risk_clauses: HighRiskClause[]
  recent_activity: Array<{
    action: string
    resource_type: string
    resource_id: string
    timestamp: string
  }>
}

export interface ExpirationItem {
  contract_id: string
  filename: string
  counterparty: string | null
  expiration_date: string
  days_remaining: number
}

export interface HighRiskClause {
  clause_id: string
  contract_id: string
  contract_filename: string
  clause_type: string
  risk_level: string
  excerpt: string
}

export interface ProcurementDashboard {
  spend_commitments: SpendCommitment[]
  upcoming_obligations: VendorObligation[]
  auto_renewal_risks: AutoRenewalRisk[]
  vendor_summary: Record<string, number>
}

export interface SpendCommitment {
  counterparty: string
  total_value: number
  contract_count: number
  currency: string | null
}

export interface VendorObligation {
  obligation_id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  description: string
  deadline: string | null
  days_remaining: number | null
  status: string
}

export interface AutoRenewalRisk {
  contract_id: string
  filename: string
  counterparty: string | null
  expiration_date: string | null
  notice_period_days: number | null
  notice_deadline: string | null
  days_until_notice: number | null
  urgency: 'IMMEDIATE' | 'SOON' | 'UPCOMING' | 'FUTURE'
}

// Contract Intelligence types
export interface ClauseBreakdown {
  clause_type: string
  count: number
  high_risk_count: number
}

export interface ObligationItem {
  id: string
  description: string
  obligation_type: string
  obligated_party: string | null
  beneficiary_party: string | null
  deadline: string | null
  status: string
  source_text: string | null
}

export interface ObligationsMatrix {
  provider_obligations: ObligationItem[]
  client_obligations: ObligationItem[]
  total_count: number
}

export interface ContractKeyTerms {
  contract_type: string | null
  counterparty: string | null
  effective_date: string | null
  expiration_date: string | null
  contract_value: number | null
  currency: string | null
  jurisdiction: string | null
  notice_period_days: number | null
  auto_renewal: boolean | null
}

export interface RiskClauseDetail {
  id: string
  clause_type: string
  excerpt: string
  risk_reason: string | null
}

export interface RiskSummary {
  risk_level: string | null
  risk_score: number | null
  high_risk_clauses: RiskClauseDetail[]
}

export interface ContractIntelligence {
  contract_id: string
  filename: string
  key_terms: ContractKeyTerms
  clause_breakdown: ClauseBreakdown[]
  obligations_matrix: ObligationsMatrix
  risk_summary: RiskSummary
  extraction_status: {
    total_clauses: number
    classified_clauses: number
    total_obligations: number
  }
}

export interface ObligationsByType {
  obligation_type: string
  count: number
  by_party: Record<string, number>
}

export interface ObligationsSummary {
  by_type: ObligationsByType[]
  by_status: Record<string, number>
  by_party: Record<string, number>
  total: number
}

// Clauses Summary types
export interface ClauseByType {
  clause_type: string
  count: number
  high_risk_count: number
}

export interface ClausesSummary {
  by_type: ClauseByType[]
  total: number
  classified: number
  high_risk_total: number
}

// Clauses drill-down types
export interface ClauseDetail {
  id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  clause_type: string
  text: string
  risk_level: string | null
  page_number: number | null
  section_number: string | null
}

export interface ClausesByTypeResponse {
  clause_type: string
  clauses: ClauseDetail[]
  total: number
  high_risk_count: number
}

// Full clause detail for detail page
export interface ClauseFullDetail {
  id: string
  contract_id: string
  contract_filename: string
  contract_type: string | null
  counterparty: string | null
  clause_type: string
  text: string
  risk_level: string | null
  risk_reason: string | null
  page_number: number | null
  section_number: string | null
  related_clauses: Array<{
    id: string
    clause_type: string
    text: string
    risk_level: string | null
    page_number: number | null
  }>
}

// Obligation drill-down types
export interface ObligationDetail {
  id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  description: string
  obligation_type: string
  obligated_party: string | null
  beneficiary_party: string | null
  deadline: string | null
  status: string
  source_clause_text: string | null
}

export interface ObligationsByTypeResponse {
  obligation_type: string
  obligations: ObligationDetail[]
  total: number
  by_party: Record<string, number>
  by_status: Record<string, number>
}

// Contract summary for dashboard cards
export interface ContractSummaryCard {
  id: string
  filename: string
  contract_type: string | null
  counterparty: string | null
  status: string
  risk_level: string | null
  risk_score: number | null
  clause_count: number
  obligation_count: number
  expiration_date: string | null
  days_until_expiration: number | null
}

export interface ContractsSummaryResponse {
  contracts: ContractSummaryCard[]
  total_contracts: number
  by_status: Record<string, number>
  by_risk: Record<string, number>
  expiring_soon: number
}

// Full obligation detail for detail page
export interface ObligationFullDetail {
  id: string
  contract_id: string
  contract_filename: string
  counterparty: string | null
  contract_type: string | null

  description: string
  obligation_type: string
  obligated_party: string | null
  beneficiary_party: string | null
  deadline: string | null
  deadline_type: string | null
  recurrence_pattern: string | null
  relative_deadline_text: string | null
  status: string
  consequence_of_breach: string | null
  trigger_condition: string | null
  source_text: string | null

  // Compliance tracking fields
  rag_status: string | null
  is_critical: boolean
  compliance_notes: string | null
  compliance_evidence: string | null
  last_compliance_date: string | null
  next_compliance_due: string | null

  clause_id: string | null
  clause_type: string | null
  clause_text: string | null
  clause_page_number: number | null
  clause_section_number: string | null
  clause_risk_level: string | null
}

// Dashboard Trends for sparklines
export interface DashboardTrends {
  total_contracts: number[]
  contracts_at_risk: number[]
  compliance_rate: number[]
  total_contract_value: number[]
  sla_compliance_rate: number[]
  obligations_overdue: number[]
}

// ============ TENANT TYPES (Super Admin) ============

export type TenantPlan = 'starter' | 'professional' | 'enterprise'

export interface Tenant {
  id: string
  name: string
  slug: string
  plan: TenantPlan
  contract_limit: number | null
  contact_email: string | null
  is_active: boolean
  created_at: string
  updated_at?: string
}

export interface TenantCreate {
  name: string
  slug: string
  plan: TenantPlan
  contract_limit?: number | null
  contact_email?: string | null
}

export interface TenantUpdate {
  name?: string
  slug?: string
  plan?: TenantPlan
  contract_limit?: number | null
  contact_email?: string | null
  is_active?: boolean
}

export interface TenantStats {
  tenant_id: string
  tenant_name?: string | null
  plan?: string | null
  contract_count: number
  contract_limit?: number | null
  user_count: number
  is_active: boolean
  // Frontend-only fields (calculated or estimated)
  total_value?: number
  storage_used_mb?: number
}

export interface PlatformStats {
  total_tenants: number
  active_tenants: number
  total_users: number
  total_contracts: number
  total_value: number
  plan_distribution: Record<TenantPlan, number>
}

// ============ CUSTOM FIELD TYPES ============

export type FieldType = 'text' | 'number' | 'date' | 'dropdown' | 'multi_select' | 'checkbox' | 'url' | 'email' | 'currency'
export type EntityType = 'contract' | 'obligation' | 'clause' | 'client'

export interface CustomField {
  name: string
  label: string
  field_type: FieldType
  required: boolean
  options?: string[]
  help_text?: string
  extraction_hints?: string
  extraction_examples?: string[]
  display_order: number
  is_visible: boolean
  is_archived: boolean
  created_at?: string
  updated_at?: string
}

export interface CustomFieldCreate {
  name: string
  label: string
  field_type: FieldType
  required?: boolean
  options?: string[]
  help_text?: string
  extraction_hints?: string
  extraction_examples?: string[]
  display_order?: number
  is_visible?: boolean
}

export interface CustomFieldUpdate {
  label?: string
  required?: boolean
  options?: string[]
  help_text?: string
  extraction_hints?: string
  extraction_examples?: string[]
  display_order?: number
  is_visible?: boolean
  is_archived?: boolean
}

// Extended user type with tenant info for cross-tenant management
export interface UserWithTenant extends User {
  tenant_id: string
  tenant_name?: string
}

// ============ ESTABLISHED CONTRACT LINKS ============

export interface ContractLinkBrief {
  id: string
  filename: string
  contract_type: string | null
  counterparty: string | null
  effective_date: string | null
  expiration_date: string | null
  risk_level: string | null
  status: string | null
}

export interface ContractLinkOut {
  id: string
  link_type: string
  link_description: string | null
  direction: 'parent' | 'child'
  effective_date: string | null
  reference_number: string | null
  is_active: boolean
  linked_contract: ContractLinkBrief
  created_at: string | null
}

export interface ContractLinksResponse {
  links: ContractLinkOut[]
  total: number
}

// ============ SUGGESTED CONTRACT LINKS ============

export type LinkType =
  | 'sow'
  | 'work_order'
  | 'service_order'
  | 'purchase_order'
  | 'amendment'
  | 'addendum'
  | 'change_order'
  | 'modification'
  | 'renewal'
  | 'exhibit'
  | 'schedule'
  | 'appendix'
  | 'attachment'
  | 'supersedes'
  | 'references'
  | 'related'

export type SuggestionStatus = 'pending' | 'approved' | 'rejected' | 'expired'

export interface ContractBrief {
  id: string
  filename: string
  contract_type: string | null
  counterparty: string | null
  effective_date: string | null
  expiration_date: string | null
  risk_level: string | null
}

export interface SuggestedLink {
  id: string
  source_contract_id: string
  target_contract_id: string
  suggested_link_type: LinkType
  suggested_direction: 'source_is_child' | 'source_is_parent'
  confidence_score: number
  reasoning: string | null
  matching_signals: Record<string, number> | null
  status: SuggestionStatus
  reviewed_by: string | null
  reviewed_at: string | null
  created_link_id: string | null
  batch_id: string | null
  created_at: string
  updated_at: string
  target_contract: ContractBrief | null
  source_contract: ContractBrief | null
}

export interface SuggestedLinksListResponse {
  suggestions: SuggestedLink[]
  total: number
  pending_count: number
}

export interface SuggestedLinkReviewResponse {
  suggestion_id: string
  action: string
  status: string
  created_link_id: string | null
  message: string
}

export interface BatchReviewResponse {
  processed: number
  succeeded: number
  failed: number
  results: SuggestedLinkReviewResponse[]
}

export interface PendingSuggestionsResponse {
  total_pending: number
  by_contract: Record<string, number>
  suggestions: SuggestedLink[]
}

// ============ CONTRACT HIERARCHY / TREE ============

export interface ContractTreeNode {
  id: string
  filename: string
  contract_type: string | null
  counterparty: string | null
  status: string | null
  risk_level: string | null
  uploaded_at: string | null
  link_type: string | null
  link_id: string | null
  children: ContractTreeNode[]
}

export interface ContractHierarchyResponse {
  roots: ContractTreeNode[]
  total_contracts: number
  total_links: number
}

export interface CreateLinkRequest {
  parent_contract_id: string
  child_contract_id: string
  link_type?: string
}

export interface MoveContractRequest {
  contract_id: string
  new_parent_id: string | null
  link_type?: string
}

// ============ CHAT SESSION TYPES ============

export interface ChatSession {
  id: string
  title: string
  contract_id: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatMessageOut {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: unknown[]
  follow_ups?: string[]
  visualizations?: Visualization[]
  created_at: string
}

export interface ChatSessionDetail extends ChatSession {
  messages: ChatMessageOut[]
}

// Contract comments
export interface ContractCommentItem {
  id: string
  contract_id: string
  user_id?: string | null
  external_user_id?: string | null
  parent_id?: string | null
  content: string
  clause_id?: string | null
  section_reference?: string | null
  is_internal: boolean
  is_resolved: boolean
  author_name?: string | null
  author_email?: string | null
  is_internal_author: boolean
  created_at: string
  updated_at?: string | null
  reply_count: number
}
