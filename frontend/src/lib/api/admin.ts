import { client } from './client'
import type {
  User,
  UserWithTenant,
  Client,
  ClientSummary,
  ClientCreate,
  Contract,
  AdminDashboard,
  LegalDashboard,
  ProcurementDashboard,
  ContractIntelligence,
  ObligationsSummary,
  ObligationsByTypeResponse,
  ObligationFullDetail,
  ContractsSummaryResponse,
  ClausesSummary,
  ClausesByTypeResponse,
  ClauseFullDetail,
  DashboardTrends,
  Tenant,
  TenantCreate,
  TenantUpdate,
  TenantStats,
  PlatformStats,
  CustomField,
  CustomFieldCreate,
  CustomFieldUpdate,
  EntityType,
} from '@/types'
import type {
  SLAMasterData,
  SLAMasterDataCreate,
  SLAMasterDataUpdate,
  SLAMasterDataListResponse,
  MilestoneMasterData,
  MilestoneMasterDataCreate,
  MilestoneMasterDataUpdate,
  MilestoneMasterDataListResponse,
  SeedResultResponse,
  SchedulerJob,
  SchedulerJobUpdate,
  SchedulerJobListResponse,
  SchedulerJobHistoryListResponse,
  SchedulerStatus,
  SchedulerRunResponse,
  SystemHealthResponse,
} from '@/types/admin'
import type {
  BusinessUnit,
  BusinessUnitTree,
  BusinessUnitCreate,
  BusinessUnitUpdate,
  BusinessUnitListResponse,
} from '@/types/business-unit'

// ============================================================================
// Dashboard endpoints
// ============================================================================

export async function getAdminDashboard(): Promise<AdminDashboard> {
  const response = await client.get<AdminDashboard>('/dashboard/admin')
  return response.data
}

export async function getLegalDashboard(): Promise<LegalDashboard> {
  const response = await client.get<LegalDashboard>('/dashboard/legal')
  return response.data
}

export async function getProcurementDashboard(): Promise<ProcurementDashboard> {
  const response = await client.get<ProcurementDashboard>('/dashboard/procurement')
  return response.data
}

export async function getContractIntelligence(contractId: string): Promise<ContractIntelligence> {
  const response = await client.get<ContractIntelligence>(`/dashboard/intelligence/${contractId}`)
  return response.data
}

export async function getObligationsSummary(contractId?: string, clientId?: string): Promise<ObligationsSummary> {
  const params: Record<string, string> = {}
  if (contractId) params.contract_id = contractId
  if (clientId) params.client_id = clientId
  const response = await client.get<ObligationsSummary>('/dashboard/obligations-summary', {
    params: Object.keys(params).length > 0 ? params : undefined
  })
  return response.data
}

export async function getClausesSummary(contractId?: string, clientId?: string): Promise<ClausesSummary> {
  const params: Record<string, string> = {}
  if (contractId) params.contract_id = contractId
  if (clientId) params.client_id = clientId
  const response = await client.get<ClausesSummary>('/dashboard/clauses-summary', {
    params: Object.keys(params).length > 0 ? params : undefined
  })
  return response.data
}

export async function getClausesByType(clauseType: string, contractId?: string): Promise<ClausesByTypeResponse> {
  const response = await client.get<ClausesByTypeResponse>(`/dashboard/clauses/by-type/${clauseType}`, {
    params: contractId ? { contract_id: contractId } : undefined
  })
  return response.data
}

export async function getClauseDetail(clauseId: string): Promise<ClauseFullDetail> {
  const response = await client.get<ClauseFullDetail>(`/dashboard/clauses/${clauseId}`)
  return response.data
}

export async function getContractsSummary(clientId?: string): Promise<ContractsSummaryResponse> {
  const response = await client.get<ContractsSummaryResponse>('/dashboard/contracts-summary', {
    params: clientId ? { client_id: clientId } : undefined
  })
  return response.data
}

export async function getObligationsByType(obligationType: string): Promise<ObligationsByTypeResponse> {
  const response = await client.get<ObligationsByTypeResponse>(`/dashboard/obligations/by-type/${obligationType}`)
  return response.data
}

export async function getObligationDetail(obligationId: string): Promise<ObligationFullDetail> {
  const response = await client.get<ObligationFullDetail>(`/dashboard/obligations/${obligationId}`)
  return response.data
}

export async function analyzeContract(contractId: string): Promise<{ message: string; contract_id: string; analyses: string[] }> {
  const response = await client.post(`/contracts/${contractId}/analyze`)
  return response.data
}

// ============================================================================
// User endpoints
// ============================================================================

export async function getUsers(): Promise<User[]> {
  const response = await client.get<{ users: User[]; total: number }>('/users')
  return response.data.users
}

export async function createUser(data: { username: string; email: string; full_name?: string; password: string; role: string; business_unit_id?: string }): Promise<User> {
  const response = await client.post<User>('/users', data)
  return response.data
}

export async function updateUser(id: string, data: Partial<User>): Promise<User> {
  const response = await client.put<User>(`/users/${id}`, data)
  return response.data
}

export async function updateUserPassword(id: string, newPassword: string): Promise<User> {
  const response = await client.put<User>(`/users/${id}/password`, { new_password: newPassword })
  return response.data
}

export async function deleteUser(id: string): Promise<void> {
  await client.delete(`/users/${id}`)
}

// ============================================================================
// Client endpoints
// ============================================================================

export async function getClients(): Promise<{ clients: Client[]; total: number }> {
  const response = await client.get<{ clients: Client[]; total: number }>('/clients')
  return response.data
}

export async function getClientsSummary(): Promise<ClientSummary[]> {
  const response = await client.get<ClientSummary[]>('/clients/summary')
  return response.data
}

export async function getClient(id: string): Promise<Client> {
  const response = await client.get<Client>(`/clients/${id}`)
  return response.data
}

export async function createClient(data: ClientCreate): Promise<Client> {
  const response = await client.post<Client>('/clients', data)
  return response.data
}

export async function updateClient(id: string, data: Partial<ClientCreate>): Promise<Client> {
  const response = await client.put<Client>(`/clients/${id}`, data)
  return response.data
}

export async function deleteClient(id: string, force = false): Promise<void> {
  await client.delete(`/clients/${id}`, { params: { force } })
}

// ============================================================================
// Master Data Admin endpoints
// ============================================================================

// SLA Master Data

export async function getSLAMasterData(params?: {
  active_only?: boolean
  category?: string
  service_tower?: string
}): Promise<SLAMasterDataListResponse> {
  const response = await client.get<SLAMasterDataListResponse>('/admin/master-data/slas', { params })
  return response.data
}

export async function getSLAMasterDataById(id: string): Promise<SLAMasterData> {
  const response = await client.get<SLAMasterData>(`/admin/master-data/slas/${id}`)
  return response.data
}

export async function createSLAMasterData(data: SLAMasterDataCreate): Promise<SLAMasterData> {
  const response = await client.post<SLAMasterData>('/admin/master-data/slas', data)
  return response.data
}

export async function updateSLAMasterData(id: string, data: SLAMasterDataUpdate): Promise<SLAMasterData> {
  const response = await client.put<SLAMasterData>(`/admin/master-data/slas/${id}`, data)
  return response.data
}

export async function deleteSLAMasterData(id: string): Promise<void> {
  await client.delete(`/admin/master-data/slas/${id}`)
}

export async function seedSLAMasterData(): Promise<SeedResultResponse> {
  const response = await client.post<SeedResultResponse>('/admin/master-data/slas/seed')
  return response.data
}

// Milestone Master Data

export async function getMilestoneMasterData(params?: {
  active_only?: boolean
}): Promise<MilestoneMasterDataListResponse> {
  const response = await client.get<MilestoneMasterDataListResponse>('/admin/master-data/milestones', { params })
  return response.data
}

export async function getMilestoneMasterDataById(id: string): Promise<MilestoneMasterData> {
  const response = await client.get<MilestoneMasterData>(`/admin/master-data/milestones/${id}`)
  return response.data
}

export async function createMilestoneMasterData(data: MilestoneMasterDataCreate): Promise<MilestoneMasterData> {
  const response = await client.post<MilestoneMasterData>('/admin/master-data/milestones', data)
  return response.data
}

export async function updateMilestoneMasterData(id: string, data: MilestoneMasterDataUpdate): Promise<MilestoneMasterData> {
  const response = await client.put<MilestoneMasterData>(`/admin/master-data/milestones/${id}`, data)
  return response.data
}

export async function deleteMilestoneMasterData(id: string): Promise<void> {
  await client.delete(`/admin/master-data/milestones/${id}`)
}

export async function seedMilestoneMasterData(): Promise<SeedResultResponse> {
  const response = await client.post<SeedResultResponse>('/admin/master-data/milestones/seed')
  return response.data
}

// Seed all master data

export async function seedAllMasterData(): Promise<{
  sla: { seeded: number; skipped: number }
  milestones: { seeded: number; skipped: number }
  message: string
}> {
  const response = await client.post('/admin/master-data/seed-all')
  return response.data
}

// ============================================================================
// System Health endpoints
// ============================================================================

export async function getSystemHealth(): Promise<SystemHealthResponse> {
  const response = await client.get<SystemHealthResponse>('/system-health')
  return response.data
}

// ============================================================================
// Scheduler Admin endpoints
// ============================================================================

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  const response = await client.get<SchedulerStatus>('/admin/scheduler/status')
  return response.data
}

export async function getSchedulerJobs(): Promise<SchedulerJobListResponse> {
  const response = await client.get<SchedulerJobListResponse>('/admin/scheduler/jobs')
  return response.data
}

export async function getSchedulerJob(jobName: string): Promise<SchedulerJob> {
  const response = await client.get<SchedulerJob>(`/admin/scheduler/jobs/${jobName}`)
  return response.data
}

export async function updateSchedulerJob(jobName: string, data: SchedulerJobUpdate): Promise<SchedulerJob> {
  const response = await client.patch<SchedulerJob>(`/admin/scheduler/jobs/${jobName}`, data)
  return response.data
}

export async function triggerSchedulerJob(jobName: string): Promise<SchedulerRunResponse> {
  const response = await client.post<SchedulerRunResponse>(`/admin/scheduler/jobs/${jobName}/run`)
  return response.data
}

export async function getSchedulerJobHistory(jobName: string, limit = 50): Promise<SchedulerJobHistoryListResponse> {
  const response = await client.get<SchedulerJobHistoryListResponse>(
    `/admin/scheduler/jobs/${jobName}/history`,
    { params: { limit } }
  )
  return response.data
}

export async function startScheduler(): Promise<{ status: string; message: string }> {
  const response = await client.post('/admin/scheduler/start')
  return response.data
}

export async function stopScheduler(): Promise<{ status: string; message: string }> {
  const response = await client.post('/admin/scheduler/stop')
  return response.data
}

// ============================================================================
// Metrics endpoints
// ============================================================================

export async function getDashboardTrends(days = 7): Promise<DashboardTrends> {
  const response = await client.get<DashboardTrends>('/metrics/dashboard-trends', {
    params: { days }
  })
  return response.data
}

export async function captureMetricSnapshot(): Promise<{ status: string; date: string; message: string }> {
  const response = await client.post('/metrics/capture')
  return response.data
}

export async function backfillMetrics(days = 30): Promise<{ status: string; created: number; message: string }> {
  const response = await client.post('/metrics/backfill', null, {
    params: { days }
  })
  return response.data
}

// ============================================================================
// Dashboard Insights & Activity
// ============================================================================

export async function getDashboardInsights(): Promise<{
  insights: Array<{
    title: string
    description: string
    action: string
    action_label: string
    variant: 'info' | 'warning' | 'success'
  }>
}> {
  const response = await client.get('/dashboard/insights')
  return response.data
}

export async function getRecentActivity(limit = 10): Promise<{
  activities: Array<{
    icon: string
    title: string
    subtitle: string
    time: string
    color: string
  }>
}> {
  const response = await client.get('/dashboard/activity', {
    params: { limit }
  })
  return response.data
}

// ============================================================================
// Super Admin: Tenant endpoints
// ============================================================================

export async function getTenants(includeInactive = false): Promise<Tenant[]> {
  const response = await client.get<Tenant[]>('/tenants', {
    params: { include_inactive: includeInactive }
  })
  return response.data
}

export async function getTenant(id: string): Promise<Tenant> {
  const response = await client.get<Tenant>(`/tenants/${id}`)
  return response.data
}

export async function createTenant(data: TenantCreate): Promise<Tenant> {
  const response = await client.post<Tenant>('/tenants', data)
  return response.data
}

export async function updateTenant(id: string, data: TenantUpdate): Promise<Tenant> {
  const response = await client.patch<Tenant>(`/tenants/${id}`, data)
  return response.data
}

export async function deactivateTenant(id: string): Promise<void> {
  await client.delete(`/tenants/${id}`)
}

export async function activateTenant(id: string): Promise<void> {
  await client.patch(`/tenants/${id}`, { is_active: true })
}

export async function purgeTenant(id: string): Promise<{ tenant: string; deleted: Record<string, number> }> {
  const response = await client.delete(`/tenants/${id}/purge`, { params: { confirm: true }, timeout: 300000 })
  return response.data
}

export async function getTenantStats(id: string): Promise<TenantStats> {
  const response = await client.get<TenantStats>(`/tenants/${id}/stats`)
  return response.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getTenantConfig(): Promise<any> {
  const response = await client.get('/tenants/current/config')
  return response.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getIndustryProfiles(): Promise<any[]> {
  const response = await client.get('/industry-profiles')
  return response.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getIndustryProfile(profileId: string): Promise<any> {
  const response = await client.get(`/industry-profiles/${profileId}`)
  return response.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function updateIndustryProfile(profileId: string, updates: Record<string, any>): Promise<any> {
  const response = await client.patch(`/industry-profiles/${profileId}/update`, updates)
  return response.data
}

export async function assignIndustryProfile(tenantId: string, profileSlug: string | null): Promise<{ tenant: string; profile: string | null; slug: string | null }> {
  const response = await client.patch(`/industry-profiles/${tenantId}/assign`, null, {
    params: { profile_slug: profileSlug },
  })
  return response.data
}

export async function setMyIndustryProfile(profileSlug: string | null): Promise<{ tenant: string; profile: string | null; slug: string | null; profile_id: string | null }> {
  const response = await client.patch('/industry-profiles/my-profile', null, {
    params: { profile_slug: profileSlug },
  })
  return response.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function getTenantOverrides(): Promise<Record<string, any>> {
  const response = await client.get('/tenants/current/overrides')
  return response.data
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function updateTenantOverrides(overrides: Record<string, any>): Promise<any> {
  const response = await client.patch('/tenants/current/overrides', overrides)
  return response.data
}

// ============================================================================
// Taxonomy Suggestions
// ============================================================================

export interface TaxonomySuggestionItem {
  id: string
  contract_id: string
  business_unit_id: string | null
  category: string
  code: string
  label: string
  details: Record<string, unknown>
  source_agent: string
  confidence: number
  source_text: string | null
  status: string
  created_at: string
}

export interface TaxonomySuggestionStats {
  pending: number
  approved: number
  rejected: number
  by_category: Record<string, number>
}

export async function getTaxonomySuggestions(
  statusFilter = 'pending',
  category?: string,
): Promise<TaxonomySuggestionItem[]> {
  const params: Record<string, string> = { status_filter: statusFilter }
  if (category) params.category = category
  const response = await client.get('/taxonomy-suggestions', { params })
  return response.data
}

export async function getTaxonomySuggestionStats(): Promise<TaxonomySuggestionStats> {
  const response = await client.get('/taxonomy-suggestions/stats')
  return response.data
}

export async function approveTaxonomySuggestion(
  id: string,
  modifications?: { code?: string; label?: string; details?: Record<string, unknown> },
): Promise<{ status: string; category: string; code: string; label: string }> {
  const response = await client.post(`/taxonomy-suggestions/${id}/approve`, modifications || {})
  return response.data
}

export async function rejectTaxonomySuggestion(
  id: string,
): Promise<{ status: string; code: string }> {
  const response = await client.post(`/taxonomy-suggestions/${id}/reject`)
  return response.data
}

export async function approveAllTaxonomySuggestions(
  category?: string,
): Promise<{ approved: number }> {
  const params: Record<string, string> = {}
  if (category) params.category = category
  const response = await client.post('/taxonomy-suggestions/approve-all', null, { params })
  return response.data
}

export async function getPlatformStats(): Promise<PlatformStats> {
  // Aggregate stats from tenants list and individual tenant stats
  const tenants = await getTenants(true)

  // Fetch stats for each tenant in parallel
  const tenantStatsPromises = tenants.map(t =>
    getTenantStats(t.id).catch(() => ({
      tenant_id: t.id,
      user_count: 0,
      contract_count: 0,
      is_active: t.is_active
    }))
  )
  const allTenantStats = await Promise.all(tenantStatsPromises)

  // Aggregate totals
  const totalUsers = allTenantStats.reduce((sum, s) => sum + (s.user_count || 0), 0)
  const totalContracts = allTenantStats.reduce((sum, s) => sum + (s.contract_count || 0), 0)
  const totalValue = allTenantStats.reduce((sum, s: any) => sum + (s.total_value || 0), 0)

  const stats: PlatformStats = {
    total_tenants: tenants.length,
    active_tenants: tenants.filter(t => t.is_active).length,
    total_users: totalUsers,
    total_contracts: totalContracts,
    total_value: totalValue,
    plan_distribution: {
      starter: tenants.filter(t => t.plan === 'starter').length,
      professional: tenants.filter(t => t.plan === 'professional').length,
      enterprise: tenants.filter(t => t.plan === 'enterprise').length,
    }
  }
  return stats
}

// ============================================================================
// Super Admin: Cross-Tenant User endpoints
// ============================================================================

export async function getAllUsers(tenantId?: string): Promise<UserWithTenant[]> {
  const params: Record<string, string> = {}
  if (tenantId) params.tenant_id = tenantId
  const response = await client.get<{ users: User[]; total: number }>('/users', { params })
  return response.data.users.map((u: any) => ({ ...u, tenant_id: u.tenant_id || '' }))
}

export async function createUserForTenant(tenantId: string, data: { username: string; email: string; password: string; role: string; business_unit_id?: string }): Promise<User> {
  const response = await client.post<User>('/users', { ...data, tenant_id: tenantId })
  return response.data
}

export async function getTenantUsers(tenantId: string): Promise<User[]> {
  const params = { tenant_id: tenantId }
  const response = await client.get<{ users: User[]; total: number }>('/users', { params })
  return response.data.users
}

// ============================================================================
// Custom Fields endpoints
// ============================================================================

export async function getCustomFields(tenantId: string, entityType: EntityType): Promise<CustomField[]> {
  const response = await client.get<{ entity_type: string; fields: CustomField[] }>(`/admin/custom-fields/${entityType}`, {
    headers: { 'X-Tenant-ID': tenantId }
  })
  return response.data.fields
}

export async function createCustomField(tenantId: string, entityType: EntityType, data: CustomFieldCreate): Promise<CustomField> {
  const response = await client.post<CustomField>(`/admin/custom-fields/${entityType}`, {
    field: data
  }, {
    headers: { 'X-Tenant-ID': tenantId }
  })
  return response.data
}

export async function updateCustomField(tenantId: string, entityType: EntityType, fieldName: string, data: CustomFieldUpdate): Promise<CustomField> {
  const response = await client.put<CustomField>(`/admin/custom-fields/${entityType}/${fieldName}`, data, {
    headers: { 'X-Tenant-ID': tenantId }
  })
  return response.data
}

export async function deleteCustomField(tenantId: string, entityType: EntityType, fieldName: string): Promise<void> {
  await client.delete(`/admin/custom-fields/${entityType}/${fieldName}`, {
    headers: { 'X-Tenant-ID': tenantId }
  })
}

export async function reorderCustomFields(tenantId: string, entityType: EntityType, order: string[]): Promise<CustomField[]> {
  const response = await client.post<{ entity_type: string; fields: CustomField[] }>(`/admin/custom-fields/${entityType}/reorder`, order, {
    headers: { 'X-Tenant-ID': tenantId }
  })
  return response.data.fields
}

/**
 * Get custom field definitions for the current user's tenant.
 * This is for regular tenant users to see what fields are available.
 */
export async function getTenantCustomFields(entityType: EntityType): Promise<CustomField[]> {
  const response = await client.get<{ entity_type: string; fields: CustomField[] }>(`/custom-fields/${entityType}`)
  return response.data.fields
}

/**
 * Update custom field values on a contract.
 */
export async function updateContractCustomFields(contractId: string, customFields: Record<string, unknown>): Promise<Contract> {
  const response = await client.patch<Contract>(`/contracts/${contractId}`, {
    custom_fields: customFields
  })
  return response.data
}

// ============================================================================
// Business Units
// ============================================================================

/**
 * Get business units list with pagination.
 */
export async function getBusinessUnits(params?: {
  page?: number
  page_size?: number
  active_only?: boolean
  parent_id?: string
}, tenantId?: string): Promise<BusinessUnitListResponse> {
  const config = tenantId ? { params, headers: { 'X-Tenant-ID': tenantId } } : { params }
  const response = await client.get<BusinessUnitListResponse>(
    '/business-units',
    config
  )
  return response.data
}

/**
 * Get business units as a tree structure.
 */
export async function getBusinessUnitsTree(tenantId?: string): Promise<BusinessUnitTree[]> {
  const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
  const response = await client.get<BusinessUnitTree[]>(
    '/business-units/tree',
    config
  )
  return response.data
}

/**
 * Get a single business unit by ID.
 */
export async function getBusinessUnit(id: string, tenantId?: string): Promise<BusinessUnit> {
  const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
  const response = await client.get<BusinessUnit>(
    `/business-units/${id}`,
    config
  )
  return response.data
}

/**
 * Create a new business unit.
 */
export async function createBusinessUnit(data: BusinessUnitCreate, tenantId?: string): Promise<BusinessUnit> {
  const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
  const response = await client.post<BusinessUnit>(
    '/business-units',
    data,
    config
  )
  return response.data
}

/**
 * Update a business unit.
 */
export async function updateBusinessUnit(id: string, data: BusinessUnitUpdate, tenantId?: string): Promise<BusinessUnit> {
  const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
  const response = await client.put<BusinessUnit>(
    `/business-units/${id}`,
    data,
    config
  )
  return response.data
}

/**
 * Delete (deactivate) a business unit.
 */
export async function deleteBusinessUnit(id: string, tenantId?: string): Promise<void> {
  const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
  await client.delete(`/business-units/${id}`, config)
}

/**
 * Assign an industry profile to a business unit.
 * Pass null profileId to clear the override and inherit from tenant.
 */
export async function assignBuProfile(
  buId: string,
  profileId: string | null,
  tenantId?: string
): Promise<{ business_unit: string; profile: string | null; profile_id: string | null; effective_profile: string | null }> {
  const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId }, params: { profile_id: profileId } }
    : { params: { profile_id: profileId } }
  const response = await client.patch(`/business-units/${buId}/profile`, null, config)
  return response.data
}

// ============================================================================
// External Users
// ============================================================================

/**
 * Get external users list.
 */
export async function getExternalUsers(params?: {
  page?: number
  page_size?: number
  search?: string
}): Promise<{
  items: Array<{
    id: string
    email: string
    full_name?: string
    company_name?: string
    title?: string
    phone?: string
    is_active: boolean
    invited_at?: string
    last_access_at?: string
    access_count: number
    created_at: string
  }>
  total: number
  page: number
  page_size: number
  pages: number
}> {
  const response = await client.get('/external-users', { params })
  return response.data
}

/**
 * Create an external user.
 */
export async function createExternalUser(data: {
  email: string
  full_name?: string
  company_name?: string
  title?: string
  phone?: string
}): Promise<unknown> {
  const response = await client.post('/external-users', data)
  return response.data
}

/**
 * Update an external user.
 */
export async function updateExternalUser(id: string, data: {
  email?: string
  full_name?: string
  company_name?: string
  title?: string
  phone?: string
}): Promise<unknown> {
  const response = await client.put(`/external-users/${id}`, data)
  return response.data
}

/**
 * Delete (deactivate) an external user.
 */
export async function deleteExternalUser(id: string): Promise<void> {
  await client.delete(`/external-users/${id}`)
}

// ============================================================================
// Notification Rules
// ============================================================================

export async function getNotificationRules(options?: { eventType?: string; activeOnly?: boolean }): Promise<unknown[]> {
  const response = await client.get('/notification-rules', {
    params: {
      event_type: options?.eventType,
      active_only: options?.activeOnly ?? true,
    },
  })
  return response.data
}

export async function getNotificationRuleTemplates(): Promise<unknown[]> {
  const response = await client.get('/notification-rules/templates')
  return response.data
}

export async function getNotificationRule(ruleId: string): Promise<unknown> {
  const response = await client.get(`/notification-rules/${ruleId}`)
  return response.data
}

export async function createNotificationRule(data: {
  name: string
  description?: string
  event_type: string
  days_before?: number
  repeat_interval_days?: number
  max_repeats?: number
  channels?: string[]
  notify_contract_owner?: boolean
  notify_admin?: boolean
  additional_recipients?: string[]
  contract_types?: string[]
  min_contract_value?: number
  risk_levels?: string[]
  priority?: string
}): Promise<unknown> {
  const response = await client.post('/notification-rules', data)
  return response.data
}

export async function createNotificationRuleFromTemplate(templateIndex: number): Promise<unknown> {
  const response = await client.post(`/notification-rules/from-template/${templateIndex}`)
  return response.data
}

export async function updateNotificationRule(ruleId: string, data: Record<string, unknown>): Promise<unknown> {
  const response = await client.put(`/notification-rules/${ruleId}`, data)
  return response.data
}

export async function deleteNotificationRule(ruleId: string): Promise<void> {
  await client.delete(`/notification-rules/${ruleId}`)
}

export async function toggleNotificationRule(ruleId: string): Promise<unknown> {
  const response = await client.post(`/notification-rules/${ruleId}/toggle`)
  return response.data
}

export async function getNotificationRuleStats(): Promise<unknown> {
  const response = await client.get('/notification-rules/summary/stats')
  return response.data
}

// ============================================================================
// Extraction Quality / Golden Set
// ============================================================================

// Per-taxonomy accuracy
export interface TaxonomyAccuracyItem { correct: number; total: number; accuracy: number }
export type TaxonomyAccuracyResponse = {
  clause_types: Record<string, TaxonomyAccuracyItem>
  obligation_types: Record<string, TaxonomyAccuracyItem>
  sla_metric_types: Record<string, TaxonomyAccuracyItem>
}

export async function getTaxonomyAccuracy(): Promise<TaxonomyAccuracyResponse> {
  const response = await client.get<TaxonomyAccuracyResponse>('/admin/extraction-quality/taxonomy-accuracy')
  return response.data
}

// Quality-driven hints
export interface QualityHint {
  category: string
  agent: string
  code: string
  label: string
  accuracy: number
  total_verified: number
  suggested_hint: string
}

export async function getQualityHints(): Promise<QualityHint[]> {
  const response = await client.get<QualityHint[]>('/admin/extraction-quality/taxonomy-accuracy/hints')
  return response.data
}

export async function getExtractionQualityOverview(): Promise<{
  total_golden: number
  total_global: number
  total_tenant: number
  verified: number
  pending_review: number
  avg_overall_score: number | null
  avg_metadata_score: number | null
  avg_clause_score: number | null
  avg_obligation_score: number | null
  avg_sla_score: number | null
}> {
  const response = await client.get('/admin/extraction-quality/overview')
  return response.data
}

export interface GoldenSetItem {
  id: string
  contract_id: string
  filename: string
  contract_type: string | null
  counterparty: string | null
  status: string | null
  is_baseline: boolean
  is_global: boolean
  notes: string | null
  added_at: string | null
  extraction: {
    metadata_completeness: number
    clause_count: number
    obligation_count: number
    sla_count: number
  }
  verification: {
    pending: number
    correct: number
    incorrect: number
    partial: number
  }
  scores: {
    metadata: number | null
    clause: number | null
    obligation: number | null
    sla: number | null
    overall: number | null
  }
}

export async function getGoldenSetContracts(page = 1, pageSize = 25): Promise<{
  items: GoldenSetItem[]
  total: number
  page: number
  page_size: number
  pages: number
}> {
  const response = await client.get('/admin/extraction-quality/golden-set', { params: { page, page_size: pageSize } })
  return response.data
}

export async function autoApproveAll(): Promise<{ contracts_processed: number; verifications_created: number; total_golden_contracts: number }> {
  const response = await client.post('/admin/extraction-quality/auto-approve-all')
  return response.data
}

export async function addToGoldenSet(contractId: string, notes?: string, isGlobal?: boolean): Promise<{ id: string; contract_id: string; is_global: boolean; status: string }> {
  const response = await client.post(`/admin/extraction-quality/golden-set/${contractId}`, { notes, is_global: isGlobal || false })
  return response.data
}

export async function removeFromGoldenSet(contractId: string, isGlobal?: boolean): Promise<void> {
  await client.delete(`/admin/extraction-quality/golden-set/${contractId}`, { params: isGlobal ? { is_global: true } : undefined })
}

export async function getExtractionDetail(contractId: string): Promise<{
  contract_id: string
  filename: string
  contract_status: string | null
  is_golden: boolean
  is_global: boolean
  golden_set_id: string | null
  extracted_text: string | null
  metadata: Array<{
    field: string
    value: unknown
    verification: { status: string; corrected_value: unknown; notes: string | null; verified_at: string | null } | null
  }>
  clauses: Array<{
    id: string
    clause_type: string | null
    text: string | null
    section_number: string | null
    page_number: number | null
    risk_level: string | null
    confidence: number | null
    verification: { status: string; corrected_value: unknown; notes: string | null; verified_at: string | null } | null
  }>
  obligations: Array<{
    id: string
    description: string | null
    obligation_type: string | null
    obligated_party: string | null
    deadline_type: string | null
    deadline: string | null
    status: string | null
    is_critical: boolean
    verification: { status: string; corrected_value: unknown; notes: string | null; verified_at: string | null } | null
  }>
  slas: Array<{
    id: string
    sla_name: string | null
    metric_type: string | null
    target_value: number | null
    metric_unit: string | null
    severity: string | null
    has_penalty: boolean
    penalty_value: number | null
    verification: { status: string; corrected_value: unknown; notes: string | null; verified_at: string | null } | null
  }>
  summary: {
    metadata_filled: number
    metadata_total: number
    clause_count: number
    obligation_count: number
    sla_count: number
    avg_clause_confidence: number | null
  }
}> {
  const response = await client.get(`/admin/extraction-quality/contracts/${contractId}`)
  return response.data
}

export async function verifyExtraction(data: {
  golden_set_id: string
  entity_type: string
  entity_id: string
  status: 'correct' | 'incorrect' | 'partial'
  corrected_value?: Record<string, unknown>
  notes?: string
}): Promise<{ id: string; status: string; entity_type: string; entity_id: string }> {
  const response = await client.post('/admin/extraction-quality/verify', data)
  return response.data
}

export async function bulkVerifyExtraction(data: {
  golden_set_id: string
  verifications: Array<{
    entity_type: string
    entity_id: string
    status: 'correct' | 'incorrect' | 'partial'
    corrected_value?: Record<string, unknown>
    notes?: string
  }>
}): Promise<{ verified: number; results: Array<{ entity_type: string; entity_id: string; status: string }> }> {
  const response = await client.post('/admin/extraction-quality/verify/bulk', data)
  return response.data
}

// ============ EXTRACTION CONFIDENCE THRESHOLDS ============

export interface ExtractionThresholds {
  default: number
  fields: Record<string, number>
  available_fields: string[]
}

export async function getExtractionThresholds(): Promise<ExtractionThresholds> {
  const response = await client.get<ExtractionThresholds>('/settings/extraction-thresholds')
  return response.data
}

export async function updateExtractionThresholds(data: {
  default?: number | null
  fields?: Record<string, number> | null
}): Promise<ExtractionThresholds> {
  const response = await client.put<ExtractionThresholds>('/settings/extraction-thresholds', data)
  return response.data
}

// ============ DSPY COMPILATION ============

export type DspyAgentType = 'metadata' | 'clause' | 'obligation' | 'sla'

export interface DspyProgramStatus {
  compiled: boolean
  path?: string
  size_bytes?: number
  compiled_at?: number  // unix epoch seconds (file mtime)
  compiling?: boolean   // a compile is currently running (lock file present)
  verifications_since_last_compile?: number
}

export interface DspyCompilationStatus {
  tenant_id: string
  programs: Record<DspyAgentType, DspyProgramStatus>
}

export interface DspyCompileResult {
  status: 'compiled' | 'skipped' | 'error' | 'in_progress'
  message?: string
  examples?: number
  path?: string
}

export interface DspyCompileResponse {
  tenant_id: string
  results: Record<DspyAgentType, DspyCompileResult>
}

export interface DspyAutoRecompileConfig {
  enabled: boolean
  threshold: number
}

export async function getDspyCompilationStatus(): Promise<DspyCompilationStatus> {
  const response = await client.get<DspyCompilationStatus>('/admin/extraction-quality/compile/status')
  return response.data
}

export async function compileDspyPrograms(agentTypes?: DspyAgentType[]): Promise<DspyCompileResponse> {
  const response = await client.post<DspyCompileResponse>(
    '/admin/extraction-quality/compile',
    agentTypes && agentTypes.length > 0 ? agentTypes : null,
  )
  return response.data
}

export async function getDspyAutoRecompileConfig(): Promise<DspyAutoRecompileConfig> {
  const response = await client.get<DspyAutoRecompileConfig>('/settings/dspy-auto-recompile')
  return response.data
}

export async function updateDspyAutoRecompileConfig(
  data: { enabled?: boolean; threshold?: number }
): Promise<DspyAutoRecompileConfig> {
  const response = await client.put<DspyAutoRecompileConfig>('/settings/dspy-auto-recompile', data)
  return response.data
}
