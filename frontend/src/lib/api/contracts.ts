import { client } from './client'
import type {
  Contract,
  ContractListResponse,
  UploadResponse,
  BatchUploadResponse,
  SuggestedLinksListResponse,
  SuggestedLinkReviewResponse,
  BatchReviewResponse,
  PendingSuggestionsResponse,
  ContractHierarchyResponse,
  CreateLinkRequest,
  MoveContractRequest,
  ContractLinksResponse,
  ContractCommentItem,
} from '@/types'
import type {
  ContractShareCreate,
  ShareInviteResponse,
  ContractShareListResponse,
} from '@/types/contract-share'
import type {
  ContractDocument,
  ContractDocumentCreate,
  ContractDocumentUpdate,
  ContractDocumentListResponse,
  DocumentSignature,
  DocumentSignatureCreate,
  DocumentSection,
  DocumentSectionCreate,
} from '@/types/fitgap'

// ============================================================================
// Contract endpoints
// ============================================================================

export async function getContracts(params?: {
  page?: number
  page_size?: number
  contract_type?: string
  counterparty?: string
  risk_level?: string
  status?: string
  search?: string
  client_id?: string
  sort_by?: string
  sort_desc?: boolean
}): Promise<ContractListResponse> {
  const response = await client.get<ContractListResponse>('/contracts', { params })
  return response.data
}

export async function getContract(id: string): Promise<Contract> {
  const response = await client.get<Contract>(`/contracts/${id}`)
  return response.data
}

export async function deleteContract(id: string): Promise<void> {
  await client.delete(`/contracts/${id}`)
}

export async function batchDeleteContracts(contractIds: string[]): Promise<{
  deleted: string[]
  failed: Array<{ contract_id: string; error: string }>
  total_deleted: number
  total_failed: number
}> {
  const response = await client.post('/contracts/batch-delete', {
    contract_ids: contractIds,
  })
  return response.data
}

export async function searchContracts(query: string, limit = 20): Promise<Array<{ contract: Contract; relevance_score: number }>> {
  const response = await client.get('/contracts/search', {
    params: { query, limit },
  })
  return response.data
}

export async function getContractFilterOptions(): Promise<{
  counterparties: string[]
  counterparty_counts: Record<string, number>
  contract_types: string[]
  risk_levels: string[]
  clients: Array<{ id: string; name: string; code: string; contract_count: number }>
}> {
  const response = await client.get('/contracts/filter-options')
  return response.data
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await client.post<UploadResponse>('/contracts/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

export async function uploadFiles(
  files: File[],
  clientId?: string,
  groupName?: string,
  groupId?: string,
): Promise<BatchUploadResponse> {
  const formData = new FormData()
  files.forEach((file) => formData.append('files', file))
  if (clientId) {
    formData.append('client_id', clientId)
  }
  if (groupId) {
    formData.append('group_id', groupId)
  } else if (groupName) {
    formData.append('group_name', groupName)
  }

  const response = await client.post<BatchUploadResponse>('/contracts/upload/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

// ============================================================================
// Contract groups
// ============================================================================

export interface ContractGroupSummary {
  id: string
  name: string
  group_type: 'manual' | 'upload_batch' | 'auto_family'
  parent_group_id?: string | null
  owner_user_id?: string | null
  member_count: number
}

export interface ContractGroupMemberEntry {
  contract_id: string
  filename: string
  contract_type?: string | null
  counterparty?: string | null
  status?: string | null
  risk_level?: string | null
  expiration_date?: string | null
  source: string
  member_id: string
}

export interface ContractGroupResponse {
  id: string
  tenant_id: string
  name: string
  description?: string | null
  group_type: 'manual' | 'upload_batch' | 'auto_family'
  parent_group_id?: string | null
  owner_user_id?: string | null
  owner_name?: string | null
  root_contract_id?: string | null
  member_count: number
  open_finding_count: number
  child_groups: ContractGroupSummary[]
  created_at: string
  updated_at: string
}

export interface ContractGroupDetail extends ContractGroupResponse {
  members: ContractGroupMemberEntry[]
  findings: Array<{
    id: string
    contract_id: string
    finding_type: string
    reference_label: string
    reference_type?: string | null
    status: 'open' | 'resolved' | 'dismissed'
    created_at: string
  }>
}

export interface ContractGroupListResponse {
  items: ContractGroupResponse[]
  total: number
  page: number
  page_size: number
  pages: number
}

export async function getGroups(params?: {
  page?: number
  page_size?: number
  group_type?: string
  search?: string
}): Promise<ContractGroupListResponse> {
  const response = await client.get<ContractGroupListResponse>('/groups', { params })
  return response.data
}

export async function getGroup(groupId: string): Promise<ContractGroupDetail> {
  const response = await client.get<ContractGroupDetail>(`/groups/${groupId}`)
  return response.data
}

export async function createGroup(data: {
  name: string
  description?: string
  parent_group_id?: string
  owner_user_id?: string
}): Promise<ContractGroupResponse> {
  const response = await client.post<ContractGroupResponse>('/groups', data)
  return response.data
}

export async function updateGroup(
  groupId: string,
  data: {
    name?: string
    description?: string
    parent_group_id?: string | null
    owner_user_id?: string | null
  },
): Promise<ContractGroupResponse> {
  const response = await client.patch<ContractGroupResponse>(`/groups/${groupId}`, data)
  return response.data
}

export async function deleteGroup(groupId: string): Promise<void> {
  await client.delete(`/groups/${groupId}`)
}

export async function addGroupMembers(
  groupId: string,
  contractIds: string[],
): Promise<ContractGroupDetail> {
  const response = await client.post<ContractGroupDetail>(`/groups/${groupId}/members`, {
    contract_ids: contractIds,
  })
  return response.data
}

export async function removeGroupMember(groupId: string, contractId: string): Promise<void> {
  await client.delete(`/groups/${groupId}/members/${contractId}`)
}

export async function processContract(id: string): Promise<void> {
  await client.post(`/contracts/${id}/process`)
}

// ============================================================================
// Contract update endpoints (for review pane)
// ============================================================================

export async function updateContract(contractId: string, data: Record<string, unknown>): Promise<unknown> {
  const response = await client.patch(`/contracts/${contractId}`, data)
  return response.data
}

export async function updateClause(contractId: string, clauseId: string, data: Record<string, unknown>): Promise<unknown> {
  const response = await client.patch(`/contracts/${contractId}/clauses/${clauseId}`, data)
  return response.data
}

export async function updateObligation(obligationId: string, data: Record<string, unknown>): Promise<unknown> {
  const response = await client.patch(`/obligations/${obligationId}`, data)
  return response.data
}

export async function downloadContractFile(contractId: string, asPdf = false): Promise<Blob> {
  const params = asPdf ? { as_pdf: true } : {}
  const response = await client.get(`/contracts/${contractId}/download`, { responseType: 'blob', params })
  return response.data
}

export interface HighlightRect {
  page: number
  x0: number
  y0: number
  x1: number
  y1: number
}

export interface ContractHighlights {
  contract_id: string
  highlights: Record<string, {
    clause_type: string
    section_number: string | null
    page_number: number | null
    rects: HighlightRect[]
  }>
  page_dimensions: Record<string, { width: number; height: number }>
  total_clauses: number
}

export async function getContractHighlights(contractId: string): Promise<ContractHighlights> {
  const response = await client.get(`/contracts/${contractId}/highlights`)
  return response.data
}

// ============================================================================
// Amendment/Version endpoints
// ============================================================================

export async function getContractVersions(contractId: string): Promise<unknown> {
  const response = await client.get(`/contracts/${contractId}/versions`)
  return response.data
}

export async function getVersionDiff(contractId: string, compareId: string): Promise<unknown> {
  const response = await client.get(`/contracts/${contractId}/diff/${compareId}`)
  return response.data
}

export async function linkAmendment(contractId: string, data: {
  child_contract_id: string
  link_type?: string
  effective_date?: string
  reference_number?: string
}): Promise<unknown> {
  const response = await client.post(`/contracts/${contractId}/amendments`, data)
  return response.data
}

export async function getContractAuditTrail(contractId: string): Promise<unknown> {
  const response = await client.get(`/contracts/${contractId}/audit-trail`)
  return response.data
}

// ============================================================================
// Contract Hierarchy / Tree
// ============================================================================

export async function getContractHierarchy(): Promise<ContractHierarchyResponse> {
  const response = await client.get<ContractHierarchyResponse>('/contracts/hierarchy')
  return response.data
}

export async function createContractLink(data: CreateLinkRequest): Promise<unknown> {
  const response = await client.post('/contracts/links', data)
  return response.data
}

export async function deleteContractLink(linkId: string): Promise<void> {
  await client.delete(`/contracts/links/${linkId}`)
}

export async function moveContract(data: MoveContractRequest): Promise<unknown> {
  const response = await client.post('/contracts/links/move', data)
  return response.data
}

// ============================================================================
// Established Contract Links
// ============================================================================

/**
 * Get established (approved) contract links for a contract.
 */
export async function getContractLinks(contractId: string): Promise<ContractLinksResponse> {
  const response = await client.get<ContractLinksResponse>(
    `/contracts/${contractId}/links`
  )
  return response.data
}

// ============================================================================
// Suggested Contract Links
// ============================================================================

/**
 * Get suggested links for a specific contract.
 */
export async function getSuggestedLinks(contractId: string, statusFilter?: string): Promise<SuggestedLinksListResponse> {
  const response = await client.get<SuggestedLinksListResponse>(
    `/contracts/${contractId}/suggested-links`,
    { params: statusFilter ? { status_filter: statusFilter } : undefined }
  )
  return response.data
}

/**
 * Review (approve/reject/modify) a suggested link.
 */
export async function reviewSuggestedLink(
  contractId: string,
  suggestionId: string,
  action: 'approve' | 'reject' | 'modify',
  modifiedLinkType?: string
): Promise<SuggestedLinkReviewResponse> {
  const response = await client.post<SuggestedLinkReviewResponse>(
    `/contracts/${contractId}/suggested-links/${suggestionId}/review`,
    {
      action,
      modified_link_type: modifiedLinkType,
    }
  )
  return response.data
}

/**
 * Batch approve or reject multiple suggestions.
 */
export async function batchReviewSuggestedLinks(
  contractId: string,
  suggestionIds: string[],
  action: 'approve' | 'reject',
  notes?: string
): Promise<BatchReviewResponse> {
  const response = await client.post<BatchReviewResponse>(
    `/contracts/${contractId}/suggested-links/batch-review`,
    {
      suggestion_ids: suggestionIds,
      action,
      notes,
    }
  )
  return response.data
}

/**
 * Get all pending suggestions for the current tenant.
 */
export async function getAllPendingSuggestions(limit = 50): Promise<PendingSuggestionsResponse> {
  const response = await client.get<PendingSuggestionsResponse>(
    '/contracts/pending-suggestions',
    { params: { limit } }
  )
  return response.data
}

// ============================================================================
// Contract Sharing
// ============================================================================

/**
 * Share a contract with an external user.
 */
export async function shareContract(
  contractId: string,
  data: ContractShareCreate
): Promise<ShareInviteResponse> {
  const response = await client.post<ShareInviteResponse>(
    `/contracts/${contractId}/share`,
    data
  )
  return response.data
}

/**
 * List all shares for a contract.
 */
export async function getContractShares(
  contractId: string,
  includeRevoked = false
): Promise<ContractShareListResponse> {
  const response = await client.get<ContractShareListResponse>(
    `/contracts/${contractId}/shares`,
    { params: { include_revoked: includeRevoked } }
  )
  return response.data
}

/**
 * Revoke a contract share.
 */
export async function revokeContractShare(contractId: string, shareId: string): Promise<void> {
  await client.delete(`/contracts/${contractId}/shares/${shareId}`)
}

// ============================================================================
// Contract Comments
// ============================================================================

export async function getContractComments(contractId: string): Promise<{ items: ContractCommentItem[]; total: number }> {
  const response = await client.get(`/contracts/${contractId}/comments`)
  return response.data
}

export async function addContractComment(contractId: string, data: { content: string; section_reference?: string; clause_id?: string; is_internal?: boolean }): Promise<ContractCommentItem> {
  const response = await client.post(`/contracts/${contractId}/comments`, data)
  return response.data
}

// ============================================================================
// Contract Documents
// ============================================================================

export async function getContractDocuments(contractId: string, params?: {
  page?: number
  page_size?: number
  document_type?: string
}): Promise<ContractDocumentListResponse> {
  const response = await client.get(`/contracts/${contractId}/documents`, { params })
  return response.data
}

export async function createContractDocument(contractId: string, data: ContractDocumentCreate): Promise<ContractDocument> {
  const response = await client.post(`/contracts/${contractId}/documents`, data)
  return response.data
}

export async function getContractDocument(contractId: string, docId: string): Promise<ContractDocument> {
  const response = await client.get(`/contracts/${contractId}/documents/${docId}`)
  return response.data
}

export async function updateContractDocument(contractId: string, docId: string, data: ContractDocumentUpdate): Promise<ContractDocument> {
  const response = await client.put(`/contracts/${contractId}/documents/${docId}`, data)
  return response.data
}

export async function deleteContractDocument(contractId: string, docId: string): Promise<void> {
  await client.delete(`/contracts/${contractId}/documents/${docId}`)
}

export async function getDocumentSignatures(contractId: string, docId: string): Promise<DocumentSignature[]> {
  const response = await client.get(`/contracts/${contractId}/documents/${docId}/signatures`)
  return response.data
}

export async function createDocumentSignature(contractId: string, docId: string, data: DocumentSignatureCreate): Promise<DocumentSignature> {
  const response = await client.post(`/contracts/${contractId}/documents/${docId}/signatures`, data)
  return response.data
}

export async function getDocumentSections(contractId: string, docId: string): Promise<DocumentSection[]> {
  const response = await client.get(`/contracts/${contractId}/documents/${docId}/sections`)
  return response.data
}

export async function createDocumentSection(contractId: string, docId: string, data: DocumentSectionCreate): Promise<DocumentSection> {
  const response = await client.post(`/contracts/${contractId}/documents/${docId}/sections`, data)
  return response.data
}

// ============ #30 — Re-extract single metadata field ============

export type ReExtractableField =
  | 'counterparty'
  | 'contract_type'
  | 'effective_date'
  | 'expiration_date'
  | 'contract_value'
  | 'currency'
  | 'jurisdiction'

export interface ReExtractMetadataResponse {
  field: string
  applied: boolean
  new_value?: string | number | null
  raw_text?: string | null
  confidence?: number | null
  reason?: string | null
}

export async function reExtractMetadataField(
  contractId: string,
  field: ReExtractableField,
  hint?: string,
): Promise<ReExtractMetadataResponse> {
  const response = await client.post<ReExtractMetadataResponse>(
    `/contracts/${contractId}/re-extract-metadata`,
    { field, hint: hint || null },
  )
  return response.data
}

// ============================================================================
// Knowledge Graph endpoints
// ============================================================================

export async function extractKnowledgeGraph(
  contractId: string,
  forceReextract = false
): Promise<{ status: string; entities_extracted: number; relationships_extracted: number }> {
  const response = await client.post(`/knowledge-graph/contracts/${contractId}/extract`, null, {
    params: { force_reextract: forceReextract }
  })
  return response.data
}

export async function getContractGraph(contractId: string): Promise<any> {
  const response = await client.get(`/knowledge-graph/contracts/${contractId}`)
  return response.data
}
