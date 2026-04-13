// ============================================================================
// Fit-Gap Feature Types (Service Portfolio, Officers, Hierarchy, Documents,
// KPI Approval, Performance History)
// ============================================================================

// --- Service Portfolio ---
export type ServiceType = 'it_services' | 'consulting' | 'legal' | 'financial' | 'logistics' | 'manufacturing' | 'marketing' | 'hr' | 'procurement' | 'other'
export type ServiceStatus = 'active' | 'inactive' | 'planned' | 'deprecated'

export interface ServicePortfolio {
  id: string
  tenant_id: string
  organization_id: string
  name: string
  code: string
  description: string | null
  service_type: ServiceType
  status: ServiceStatus
  created_at: string
  updated_at: string
  organization?: { id: string; name: string; code: string }
}

export interface ServicePortfolioCreate {
  organization_id: string
  name: string
  code: string
  description?: string
  service_type: ServiceType
  status?: ServiceStatus
}

export interface ServicePortfolioUpdate {
  name?: string
  description?: string
  service_type?: ServiceType
  status?: ServiceStatus
}

export interface ServicePortfolioListResponse {
  items: ServicePortfolio[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface RelationshipService {
  id: string
  relationship_id: string
  service_portfolio_id: string
  scope: string | null
  start_date: string | null
  end_date: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  service_portfolio?: ServicePortfolio
}

export interface RelationshipServiceCreate {
  service_portfolio_id: string
  scope?: string
  start_date?: string
  end_date?: string
}

// --- Organization Officers ---
export type GovernanceRole = 'account_manager' | 'service_delivery_manager' | 'relationship_owner' | 'executive_sponsor' | 'commercial_manager' | 'technical_lead' | 'operations_lead' | 'compliance_officer' | 'other'
export type OfficerSide = 'internal' | 'external'

export interface OrganizationOfficer {
  id: string
  tenant_id: string
  organization_id: string
  name: string
  title: string | null
  email: string | null
  phone: string | null
  department: string | null
  governance_role: GovernanceRole | null
  side: OfficerSide | null
  is_primary: boolean
  is_active: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface OfficerCreate {
  name: string
  title?: string
  email?: string
  phone?: string
  department?: string
  governance_role?: GovernanceRole
  side?: OfficerSide
  is_primary?: boolean
  notes?: string
}

export interface OfficerUpdate {
  name?: string
  title?: string
  email?: string
  phone?: string
  department?: string
  governance_role?: GovernanceRole
  side?: OfficerSide
  is_primary?: boolean
  is_active?: boolean
  notes?: string
}

// --- Organization Hierarchy ---
export type OrganizationLevel = 'holding' | 'subsidiary' | 'division' | 'branch' | 'department'

export interface OrganizationTreeNode {
  id: string
  name: string
  code: string
  org_type: string
  organization_level: OrganizationLevel | null
  parent_organization_id: string | null
  is_active: boolean
  children: OrganizationTreeNode[]
}

export interface OrganizationHierarchy {
  organization: {
    id: string
    name: string
    code: string
    org_type: string
    organization_level: OrganizationLevel | null
  }
  parent: { id: string; name: string; code: string } | null
  parent_chain: Array<{ id: string; name: string; code: string; organization_level: OrganizationLevel | null }>
  children: Array<{ id: string; name: string; code: string; organization_level: OrganizationLevel | null }>
}

// --- Contract Documents ---
export type DocumentType = 'main_agreement' | 'amendment' | 'addendum' | 'schedule' | 'exhibit' | 'statement_of_work' | 'side_letter' | 'appendix' | 'certificate' | 'other'
export type SignatureType = 'wet_ink' | 'digital' | 'electronic' | 'stamp'
export type SignatureStatus = 'pending' | 'signed' | 'declined' | 'expired'

export interface ContractDocument {
  id: string
  tenant_id: string
  contract_id: string
  document_type: DocumentType
  title: string
  description: string | null
  language: string
  version: string | null
  file_path: string | null
  file_size: number | null
  mime_type: string | null
  upload_date: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ContractDocumentCreate {
  document_type: DocumentType
  title: string
  description?: string
  language?: string
  version?: string
  file_path?: string
  file_size?: number
  mime_type?: string
}

export interface ContractDocumentUpdate {
  document_type?: DocumentType
  title?: string
  description?: string
  language?: string
  version?: string
  is_active?: boolean
}

export interface ContractDocumentListResponse {
  items: ContractDocument[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface DocumentSignature {
  id: string
  document_id: string
  signer_name: string
  signer_title: string | null
  signer_organization: string | null
  signer_email: string | null
  signed_date: string | null
  valid_until: string | null
  signature_type: SignatureType
  signature_status: SignatureStatus
  notes: string | null
  created_at: string
}

export interface DocumentSignatureCreate {
  signer_name: string
  signer_title?: string
  signer_organization?: string
  signer_email?: string
  signed_date?: string
  valid_until?: string
  signature_type?: SignatureType
  signature_status?: SignatureStatus
  notes?: string
}

export interface DocumentSection {
  id: string
  document_id: string
  parent_section_id: string | null
  section_number: string | null
  title: string
  content_summary: string | null
  page_start: number | null
  page_end: number | null
  order_index: number
  created_at: string
  children?: DocumentSection[]
}

export interface DocumentSectionCreate {
  parent_section_id?: string
  section_number?: string
  title: string
  content_summary?: string
  page_start?: number
  page_end?: number
  order_index?: number
}

// --- KPI Approval ---
export type ScoreApprovalStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected'

export interface PendingApproval {
  id: string
  score_id: string
  kpi_id: string
  kpi_name: string
  kpi_category: string | null
  relationship_id: string
  relationship_name: string
  scorer_org_id: string | null
  scored_by_user_id: string | null
  perspective: 'internal' | 'external'
  is_internal: boolean
  score: number
  period: string | null
  comments: string | null
  scored_by: string | null
  scored_at: string | null
  approval_status: ScoreApprovalStatus
  scorer_org_name: string | null
  scored_by_name: string | null
  created_at: string
}

// --- Relationship Performance History ---
export type PerformanceStatus = 'excellent' | 'good' | 'acceptable' | 'concerning' | 'poor' | 'critical'

export interface RelationshipHistoryEntry {
  id: string
  tenant_id: string
  relationship_id: string
  status: PerformanceStatus
  previous_status: PerformanceStatus | null
  overall_score: number | null
  period: string
  recorded_date: string
  recorded_by: string | null
  notes: string | null
  trigger: string | null
  created_at: string
}

export interface RelationshipHistoryCreate {
  status: PerformanceStatus
  overall_score?: number
  period: string
  notes?: string
  trigger?: string
}

export interface PerformanceTrendPoint {
  period: string
  status: PerformanceStatus
  overall_score: number | null
  recorded_date: string
}

export interface PerformanceTrendResponse {
  relationship_id: string
  trend: PerformanceTrendPoint[]
  current_status: PerformanceStatus | null
  total_entries: number
}
