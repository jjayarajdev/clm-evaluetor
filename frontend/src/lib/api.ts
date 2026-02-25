import axios, { AxiosError, AxiosInstance } from 'axios'
import type {
  TokenResponse,
  LoginRequest,
  User,
  UserWithTenant,
  Client,
  ClientSummary,
  ClientCreate,
  Contract,
  ContractListResponse,
  UploadResponse,
  BatchUploadResponse,
  QueryRequest,
  QueryResponse,
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
  SuggestedLinksListResponse,
  SuggestedLinkReviewResponse,
  BatchReviewResponse,
  PendingSuggestionsResponse,
} from '@/types'
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

// When VITE_API_URL is set (e.g., http://localhost:8000), append /api
// When not set, use /api for Vite proxy
const API_BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

class ApiClient {
  private client: AxiosInstance
  private token: string | null = null

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Load token from storage
    this.token = localStorage.getItem('access_token')

    // Request interceptor to add auth header
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`
      }
      return config
    })

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          this.clearToken()
          window.location.href = '/login'
        }
        return Promise.reject(error)
      }
    )
  }

  setToken(token: string) {
    this.token = token
    localStorage.setItem('access_token', token)
  }

  clearToken() {
    this.token = null
    localStorage.removeItem('access_token')
  }

  getToken() {
    return this.token
  }

  // Auth endpoints
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>('/auth/login', {
      username: credentials.username,
      password: credentials.password,
    })
    this.setToken(response.data.access_token)
    return response.data
  }

  async getCurrentUser(): Promise<User> {
    const response = await this.client.get<User>('/auth/me')
    return response.data
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/auth/logout')
    } finally {
      this.clearToken()
    }
  }

  // Contract endpoints
  async getContracts(params?: {
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
    const response = await this.client.get<ContractListResponse>('/contracts', { params })
    return response.data
  }

  async getContract(id: string): Promise<Contract> {
    const response = await this.client.get<Contract>(`/contracts/${id}`)
    return response.data
  }

  async deleteContract(id: string): Promise<void> {
    await this.client.delete(`/contracts/${id}`)
  }

  async batchDeleteContracts(contractIds: string[]): Promise<{
    deleted: string[]
    failed: Array<{ contract_id: string; error: string }>
    total_deleted: number
    total_failed: number
  }> {
    const response = await this.client.post('/contracts/batch-delete', {
      contract_ids: contractIds,
    })
    return response.data
  }

  async searchContracts(query: string, limit = 20): Promise<Array<{ contract: Contract; relevance_score: number }>> {
    const response = await this.client.get('/contracts/search', {
      params: { query, limit },
    })
    return response.data
  }

  async getContractFilterOptions(): Promise<{
    counterparties: string[]
    counterparty_counts: Record<string, number>
    contract_types: string[]
    risk_levels: string[]
    clients: Array<{ id: string; name: string; code: string; contract_count: number }>
  }> {
    const response = await this.client.get('/contracts/filter-options')
    return response.data
  }

  async uploadFile(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await this.client.post<UploadResponse>('/contracts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  }

  async uploadFiles(files: File[], clientId?: string): Promise<BatchUploadResponse> {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (clientId) {
      formData.append('client_id', clientId)
    }

    const response = await this.client.post<BatchUploadResponse>('/contracts/upload/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  }

  async processContract(id: string): Promise<void> {
    await this.client.post(`/contracts/${id}/process`)
  }

  // Query endpoints
  async query(request: QueryRequest): Promise<QueryResponse> {
    const response = await this.client.post<QueryResponse>('/query', request)
    return response.data
  }

  async getSuggestedQuestions(contractId?: string): Promise<{ questions: string[] }> {
    const response = await this.client.get('/query/suggestions', {
      params: { contract_id: contractId },
    })
    return response.data
  }

  async queryAnalyze(contractId: string, analysisType = 'full'): Promise<Record<string, unknown>> {
    const response = await this.client.post('/query/analyze', null, {
      params: { contract_id: contractId, analysis_type: analysisType },
    })
    return response.data
  }

  // Dashboard endpoints
  async getAdminDashboard(): Promise<AdminDashboard> {
    const response = await this.client.get<AdminDashboard>('/dashboard/admin')
    return response.data
  }

  async getLegalDashboard(): Promise<LegalDashboard> {
    const response = await this.client.get<LegalDashboard>('/dashboard/legal')
    return response.data
  }

  async getProcurementDashboard(): Promise<ProcurementDashboard> {
    const response = await this.client.get<ProcurementDashboard>('/dashboard/procurement')
    return response.data
  }

  async getContractIntelligence(contractId: string): Promise<ContractIntelligence> {
    const response = await this.client.get<ContractIntelligence>(`/dashboard/intelligence/${contractId}`)
    return response.data
  }

  async getObligationsSummary(contractId?: string, clientId?: string): Promise<ObligationsSummary> {
    const params: Record<string, string> = {}
    if (contractId) params.contract_id = contractId
    if (clientId) params.client_id = clientId
    const response = await this.client.get<ObligationsSummary>('/dashboard/obligations-summary', {
      params: Object.keys(params).length > 0 ? params : undefined
    })
    return response.data
  }

  async getClausesSummary(contractId?: string, clientId?: string): Promise<ClausesSummary> {
    const params: Record<string, string> = {}
    if (contractId) params.contract_id = contractId
    if (clientId) params.client_id = clientId
    const response = await this.client.get<ClausesSummary>('/dashboard/clauses-summary', {
      params: Object.keys(params).length > 0 ? params : undefined
    })
    return response.data
  }

  async getClausesByType(clauseType: string, contractId?: string): Promise<ClausesByTypeResponse> {
    const response = await this.client.get<ClausesByTypeResponse>(`/dashboard/clauses/by-type/${clauseType}`, {
      params: contractId ? { contract_id: contractId } : undefined
    })
    return response.data
  }

  async getClauseDetail(clauseId: string): Promise<ClauseFullDetail> {
    const response = await this.client.get<ClauseFullDetail>(`/dashboard/clauses/${clauseId}`)
    return response.data
  }

  async getContractsSummary(clientId?: string): Promise<ContractsSummaryResponse> {
    const response = await this.client.get<ContractsSummaryResponse>('/dashboard/contracts-summary', {
      params: clientId ? { client_id: clientId } : undefined
    })
    return response.data
  }

  async getObligationsByType(obligationType: string): Promise<ObligationsByTypeResponse> {
    const response = await this.client.get<ObligationsByTypeResponse>(`/dashboard/obligations/by-type/${obligationType}`)
    return response.data
  }

  async getObligationDetail(obligationId: string): Promise<ObligationFullDetail> {
    const response = await this.client.get<ObligationFullDetail>(`/dashboard/obligations/${obligationId}`)
    return response.data
  }

  async analyzeContract(contractId: string): Promise<{ message: string; contract_id: string; analyses: string[] }> {
    const response = await this.client.post(`/contracts/${contractId}/analyze`)
    return response.data
  }

  // User endpoints
  async getUsers(): Promise<User[]> {
    const response = await this.client.get<{ users: User[]; total: number }>('/users')
    return response.data.users
  }

  async createUser(data: { username: string; email: string; password: string; role: string }): Promise<User> {
    const response = await this.client.post<User>('/users', data)
    return response.data
  }

  async updateUser(id: string, data: Partial<User>): Promise<User> {
    const response = await this.client.put<User>(`/users/${id}`, data)
    return response.data
  }

  async deleteUser(id: string): Promise<void> {
    await this.client.delete(`/users/${id}`)
  }

  // ============ CLIENT ENDPOINTS ============

  async getClients(): Promise<{ clients: Client[]; total: number }> {
    const response = await this.client.get<{ clients: Client[]; total: number }>('/clients')
    return response.data
  }

  async getClientsSummary(): Promise<ClientSummary[]> {
    const response = await this.client.get<ClientSummary[]>('/clients/summary')
    return response.data
  }

  async getClient(id: string): Promise<Client> {
    const response = await this.client.get<Client>(`/clients/${id}`)
    return response.data
  }

  async createClient(data: ClientCreate): Promise<Client> {
    const response = await this.client.post<Client>('/clients', data)
    return response.data
  }

  async updateClient(id: string, data: Partial<ClientCreate>): Promise<Client> {
    const response = await this.client.put<Client>(`/clients/${id}`, data)
    return response.data
  }

  async deleteClient(id: string, force = false): Promise<void> {
    await this.client.delete(`/clients/${id}`, { params: { force } })
  }

  // ============ POST-SIGNING ENDPOINTS ============

  // Post-Signing Dashboard
  async getPostSigningDashboard(): Promise<PostSigningDashboard> {
    const response = await this.client.get<PostSigningDashboard>('/dashboard/postsigning')
    return response.data
  }

  // Renewal endpoints
  async getRenewalCalendar(): Promise<RenewalCalendar> {
    const response = await this.client.get<RenewalCalendar>('/renewals/calendar')
    return response.data
  }

  async getAtRiskRenewals(): Promise<{ total_at_risk: number; total_value_at_risk: number; contracts: unknown[] }> {
    const response = await this.client.get('/renewals/at-risk')
    return response.data
  }

  async getRenewalSummary(): Promise<unknown> {
    const response = await this.client.get('/renewals/summary')
    return response.data
  }

  async updateRenewalStatus(contractId: string, data: {
    renewal_status: string
    decision_notes?: string
    new_expiration_date?: string
  }): Promise<unknown> {
    const response = await this.client.put(`/renewals/${contractId}/status`, data)
    return response.data
  }

  async getRenewalRecommendation(contractId: string): Promise<unknown> {
    const response = await this.client.get(`/renewals/${contractId}/recommendation`)
    return response.data
  }

  // Vendor/Counterparty endpoints
  async getVendors(params?: {
    sort_by?: string
    sort_order?: string
    party_type?: 'all' | 'vendor' | 'client'
  }): Promise<{
    total_vendors: number
    at_risk_count: number
    total_exposure: number
    vendors: VendorListItem[]
  }> {
    const response = await this.client.get('/vendors', { params })
    return response.data
  }

  async getVendorPerformance(vendorName: string): Promise<VendorPerformanceDetail> {
    const response = await this.client.get<VendorPerformanceDetail>(`/vendors/${encodeURIComponent(vendorName)}/performance`)
    return response.data
  }

  async getAtRiskVendors(): Promise<{ total_at_risk: number; vendors: unknown[] }> {
    const response = await this.client.get('/vendors/at-risk')
    return response.data
  }

  async compareVendors(vendorNames: string[]): Promise<unknown> {
    const response = await this.client.get('/vendors/compare', {
      params: { vendors: vendorNames.join(',') }
    })
    return response.data
  }

  async getVendorScorecards(limit = 10): Promise<unknown[]> {
    const response = await this.client.get('/vendors/scorecard', { params: { limit } })
    return response.data
  }

  // SLA endpoints
  async getContractSLAs(contractId: string): Promise<SLADetail[]> {
    const response = await this.client.get<SLADetail[]>(`/sla/${contractId}`)
    return response.data
  }

  async getSLAComplianceSummary(): Promise<unknown> {
    const response = await this.client.get('/sla/compliance/summary')
    return response.data
  }

  async getActiveSLABreaches(): Promise<unknown> {
    const response = await this.client.get('/sla/breaches/active')
    return response.data
  }

  async logSLAPerformance(contractId: string, slaId: string, data: {
    actual_value: number
    notes?: string
  }): Promise<unknown> {
    const response = await this.client.post(`/sla/${contractId}/performance/${slaId}`, data)
    return response.data
  }

  async updateSLA(contractId: string, slaId: string, data: {
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
    const response = await this.client.put<SLADetail>(`/sla/${contractId}/${slaId}`, data)
    return response.data
  }

  async deleteSLA(contractId: string, slaId: string): Promise<void> {
    await this.client.delete(`/sla/${contractId}/${slaId}`)
  }

  async createSLA(contractId: string, data: {
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
    const response = await this.client.post<SLADetail>(`/sla/${contractId}`, data)
    return response.data
  }

  // Milestone endpoints
  async getMilestoneHealth(): Promise<MilestoneHealth> {
    const response = await this.client.get<MilestoneHealth>('/milestones/health')
    return response.data
  }

  async getAtRiskContracts(): Promise<unknown> {
    const response = await this.client.get('/milestones/at-risk-contracts')
    return response.data
  }

  async getPortfolioCompliance(): Promise<unknown> {
    const response = await this.client.get('/milestones/portfolio-compliance')
    return response.data
  }

  async assignMilestoneOwner(milestoneId: string, owner: string, notes?: string): Promise<unknown> {
    const response = await this.client.put(`/milestones/${milestoneId}/owner`, { owner, notes })
    return response.data
  }

  // Compliance Report endpoints
  async getComplianceReport(startDate: string, endDate: string): Promise<ComplianceReport> {
    const response = await this.client.get<ComplianceReport>('/reports/compliance', {
      params: { start_date: startDate, end_date: endDate }
    })
    return response.data
  }

  async getComplianceTrend(period: 'weekly' | 'monthly' = 'weekly', lookback = 4): Promise<ComplianceTrend> {
    const response = await this.client.get<ComplianceTrend>('/reports/compliance/trend', {
      params: { period, lookback }
    })
    return response.data
  }

  async exportComplianceReport(startDate: string, endDate: string, format: 'csv' | 'excel' = 'csv'): Promise<Blob> {
    const response = await this.client.get('/reports/compliance/export', {
      params: { start_date: startDate, end_date: endDate, format },
      responseType: 'blob'
    })
    return response.data
  }

  // Obligation status updates
  async updateObligationStatus(obligationId: string, data: {
    status: string
    notes?: string
  }): Promise<unknown> {
    const response = await this.client.put(`/obligations/${obligationId}/status`, data)
    return response.data
  }

  async updateObligationRAG(obligationId: string, data: {
    rag_status: string
    compliance_notes?: string
  }): Promise<unknown> {
    const response = await this.client.put(`/obligations/${obligationId}/rag`, data)
    return response.data
  }

  async getObligationComplianceRates(contractId?: string): Promise<unknown> {
    const response = await this.client.get('/obligations/compliance/rates', {
      params: contractId ? { contract_id: contractId } : undefined
    })
    return response.data
  }

  // Amendment/Version endpoints
  async getContractVersions(contractId: string): Promise<unknown> {
    const response = await this.client.get(`/contracts/${contractId}/versions`)
    return response.data
  }

  async getVersionDiff(contractId: string, compareId: string): Promise<unknown> {
    const response = await this.client.get(`/contracts/${contractId}/diff/${compareId}`)
    return response.data
  }

  async linkAmendment(contractId: string, data: {
    child_contract_id: string
    link_type?: string
    effective_date?: string
    reference_number?: string
  }): Promise<unknown> {
    const response = await this.client.post(`/contracts/${contractId}/amendments`, data)
    return response.data
  }

  async getContractAuditTrail(contractId: string): Promise<unknown> {
    const response = await this.client.get(`/contracts/${contractId}/audit-trail`)
    return response.data
  }

  // ============================================================================
  // Master Data Admin endpoints
  // ============================================================================

  // SLA Master Data
  async getSLAMasterData(params?: {
    active_only?: boolean
    category?: string
    service_tower?: string
  }): Promise<SLAMasterDataListResponse> {
    const response = await this.client.get<SLAMasterDataListResponse>('/admin/master-data/slas', { params })
    return response.data
  }

  async getSLAMasterDataById(id: string): Promise<SLAMasterData> {
    const response = await this.client.get<SLAMasterData>(`/admin/master-data/slas/${id}`)
    return response.data
  }

  async createSLAMasterData(data: SLAMasterDataCreate): Promise<SLAMasterData> {
    const response = await this.client.post<SLAMasterData>('/admin/master-data/slas', data)
    return response.data
  }

  async updateSLAMasterData(id: string, data: SLAMasterDataUpdate): Promise<SLAMasterData> {
    const response = await this.client.put<SLAMasterData>(`/admin/master-data/slas/${id}`, data)
    return response.data
  }

  async deleteSLAMasterData(id: string): Promise<void> {
    await this.client.delete(`/admin/master-data/slas/${id}`)
  }

  async seedSLAMasterData(): Promise<SeedResultResponse> {
    const response = await this.client.post<SeedResultResponse>('/admin/master-data/slas/seed')
    return response.data
  }

  // Milestone Master Data
  async getMilestoneMasterData(params?: {
    active_only?: boolean
  }): Promise<MilestoneMasterDataListResponse> {
    const response = await this.client.get<MilestoneMasterDataListResponse>('/admin/master-data/milestones', { params })
    return response.data
  }

  async getMilestoneMasterDataById(id: string): Promise<MilestoneMasterData> {
    const response = await this.client.get<MilestoneMasterData>(`/admin/master-data/milestones/${id}`)
    return response.data
  }

  async createMilestoneMasterData(data: MilestoneMasterDataCreate): Promise<MilestoneMasterData> {
    const response = await this.client.post<MilestoneMasterData>('/admin/master-data/milestones', data)
    return response.data
  }

  async updateMilestoneMasterData(id: string, data: MilestoneMasterDataUpdate): Promise<MilestoneMasterData> {
    const response = await this.client.put<MilestoneMasterData>(`/admin/master-data/milestones/${id}`, data)
    return response.data
  }

  async deleteMilestoneMasterData(id: string): Promise<void> {
    await this.client.delete(`/admin/master-data/milestones/${id}`)
  }

  async seedMilestoneMasterData(): Promise<SeedResultResponse> {
    const response = await this.client.post<SeedResultResponse>('/admin/master-data/milestones/seed')
    return response.data
  }

  // Seed all master data
  async seedAllMasterData(): Promise<{
    sla: { seeded: number; skipped: number }
    milestones: { seeded: number; skipped: number }
    message: string
  }> {
    const response = await this.client.post('/admin/master-data/seed-all')
    return response.data
  }

  // ============================================================================
  // System Health endpoints
  // ============================================================================

  async getSystemHealth(): Promise<SystemHealthResponse> {
    const response = await this.client.get<SystemHealthResponse>('/system-health')
    return response.data
  }

  // ============================================================================
  // Scheduler Admin endpoints
  // ============================================================================

  async getSchedulerStatus(): Promise<SchedulerStatus> {
    const response = await this.client.get<SchedulerStatus>('/admin/scheduler/status')
    return response.data
  }

  async getSchedulerJobs(): Promise<SchedulerJobListResponse> {
    const response = await this.client.get<SchedulerJobListResponse>('/admin/scheduler/jobs')
    return response.data
  }

  async getSchedulerJob(jobName: string): Promise<SchedulerJob> {
    const response = await this.client.get<SchedulerJob>(`/admin/scheduler/jobs/${jobName}`)
    return response.data
  }

  async updateSchedulerJob(jobName: string, data: SchedulerJobUpdate): Promise<SchedulerJob> {
    const response = await this.client.patch<SchedulerJob>(`/admin/scheduler/jobs/${jobName}`, data)
    return response.data
  }

  async triggerSchedulerJob(jobName: string): Promise<SchedulerRunResponse> {
    const response = await this.client.post<SchedulerRunResponse>(`/admin/scheduler/jobs/${jobName}/run`)
    return response.data
  }

  async getSchedulerJobHistory(jobName: string, limit = 50): Promise<SchedulerJobHistoryListResponse> {
    const response = await this.client.get<SchedulerJobHistoryListResponse>(
      `/admin/scheduler/jobs/${jobName}/history`,
      { params: { limit } }
    )
    return response.data
  }

  async startScheduler(): Promise<{ status: string; message: string }> {
    const response = await this.client.post('/admin/scheduler/start')
    return response.data
  }

  async stopScheduler(): Promise<{ status: string; message: string }> {
    const response = await this.client.post('/admin/scheduler/stop')
    return response.data
  }

  // ============ METRICS ENDPOINTS ============

  async getDashboardTrends(days = 7): Promise<DashboardTrends> {
    const response = await this.client.get<DashboardTrends>('/metrics/dashboard-trends', {
      params: { days }
    })
    return response.data
  }

  async captureMetricSnapshot(): Promise<{ status: string; date: string; message: string }> {
    const response = await this.client.post('/metrics/capture')
    return response.data
  }

  async backfillMetrics(days = 30): Promise<{ status: string; created: number; message: string }> {
    const response = await this.client.post('/metrics/backfill', null, {
      params: { days }
    })
    return response.data
  }

  // ============ DASHBOARD INSIGHTS & ACTIVITY ============

  async getDashboardInsights(): Promise<{
    insights: Array<{
      title: string
      description: string
      action: string
      action_label: string
      variant: 'info' | 'warning' | 'success'
    }>
  }> {
    const response = await this.client.get('/dashboard/insights')
    return response.data
  }

  async getRecentActivity(limit = 10): Promise<{
    activities: Array<{
      icon: string
      title: string
      subtitle: string
      time: string
      color: string
    }>
  }> {
    const response = await this.client.get('/dashboard/activity', {
      params: { limit }
    })
    return response.data
  }

  // ============ SUPER ADMIN: TENANT ENDPOINTS ============

  async getTenants(includeInactive = false): Promise<Tenant[]> {
    const response = await this.client.get<Tenant[]>('/tenants', {
      params: { include_inactive: includeInactive }
    })
    return response.data
  }

  async getTenant(id: string): Promise<Tenant> {
    const response = await this.client.get<Tenant>(`/tenants/${id}`)
    return response.data
  }

  async createTenant(data: TenantCreate): Promise<Tenant> {
    const response = await this.client.post<Tenant>('/tenants', data)
    return response.data
  }

  async updateTenant(id: string, data: TenantUpdate): Promise<Tenant> {
    const response = await this.client.patch<Tenant>(`/tenants/${id}`, data)
    return response.data
  }

  async deactivateTenant(id: string): Promise<void> {
    await this.client.delete(`/tenants/${id}`)
  }

  async activateTenant(id: string): Promise<void> {
    await this.client.patch(`/tenants/${id}`, { is_active: true })
  }

  async getTenantStats(id: string): Promise<TenantStats> {
    const response = await this.client.get<TenantStats>(`/tenants/${id}/stats`)
    return response.data
  }

  async getPlatformStats(): Promise<PlatformStats> {
    // Aggregate stats from tenants list and individual tenant stats
    const tenants = await this.getTenants(true)

    // Fetch stats for each tenant in parallel
    const tenantStatsPromises = tenants.map(t =>
      this.getTenantStats(t.id).catch(() => ({
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

    const stats: PlatformStats = {
      total_tenants: tenants.length,
      active_tenants: tenants.filter(t => t.is_active).length,
      total_users: totalUsers,
      total_contracts: totalContracts,
      total_value: 0, // Would need a dedicated endpoint for total value
      plan_distribution: {
        starter: tenants.filter(t => t.plan === 'starter').length,
        professional: tenants.filter(t => t.plan === 'professional').length,
        enterprise: tenants.filter(t => t.plan === 'enterprise').length,
      }
    }
    return stats
  }

  // ============ SUPER ADMIN: CROSS-TENANT USER ENDPOINTS ============

  async getAllUsers(_tenantId?: string): Promise<UserWithTenant[]> {
    // Uses existing users endpoint - super admin can see all users
    const response = await this.client.get<{ users: User[]; total: number }>('/users')
    // Add tenant_id placeholder - actual implementation needs backend support
    return response.data.users.map(u => ({ ...u, tenant_id: '' }))
  }

  async createUserForTenant(_tenantId: string, data: { username: string; email: string; password: string; role: string }): Promise<User> {
    // Uses existing create user endpoint
    const response = await this.client.post<User>('/users', data)
    return response.data
  }

  async getTenantUsers(_tenantId: string): Promise<User[]> {
    // For now, return all users - needs backend filtering support
    const response = await this.client.get<{ users: User[]; total: number }>('/users')
    return response.data.users
  }

  // ============ SUPER ADMIN: CUSTOM FIELDS ENDPOINTS ============

  async getCustomFields(tenantId: string, entityType: EntityType): Promise<CustomField[]> {
    const response = await this.client.get<{ entity_type: string; fields: CustomField[] }>(`/admin/custom-fields/${entityType}`, {
      headers: { 'X-Tenant-ID': tenantId }
    })
    return response.data.fields
  }

  async createCustomField(tenantId: string, entityType: EntityType, data: CustomFieldCreate): Promise<CustomField> {
    const response = await this.client.post<CustomField>(`/admin/custom-fields/${entityType}`, {
      field: data
    }, {
      headers: { 'X-Tenant-ID': tenantId }
    })
    return response.data
  }

  async updateCustomField(tenantId: string, entityType: EntityType, fieldName: string, data: CustomFieldUpdate): Promise<CustomField> {
    const response = await this.client.put<CustomField>(`/admin/custom-fields/${entityType}/${fieldName}`, data, {
      headers: { 'X-Tenant-ID': tenantId }
    })
    return response.data
  }

  async deleteCustomField(tenantId: string, entityType: EntityType, fieldName: string): Promise<void> {
    await this.client.delete(`/admin/custom-fields/${entityType}/${fieldName}`, {
      headers: { 'X-Tenant-ID': tenantId }
    })
  }

  async reorderCustomFields(tenantId: string, entityType: EntityType, order: string[]): Promise<CustomField[]> {
    const response = await this.client.post<{ entity_type: string; fields: CustomField[] }>(`/admin/custom-fields/${entityType}/reorder`, order, {
      headers: { 'X-Tenant-ID': tenantId }
    })
    return response.data.fields
  }

  // ============ TENANT USER: CUSTOM FIELDS (READ-ONLY) ============

  /**
   * Get custom field definitions for the current user's tenant.
   * This is for regular tenant users to see what fields are available.
   */
  async getTenantCustomFields(entityType: EntityType): Promise<CustomField[]> {
    const response = await this.client.get<{ entity_type: string; fields: CustomField[] }>(`/custom-fields/${entityType}`)
    return response.data.fields
  }

  /**
   * Update custom field values on a contract.
   */
  async updateContractCustomFields(contractId: string, customFields: Record<string, unknown>): Promise<Contract> {
    const response = await this.client.patch<Contract>(`/contracts/${contractId}`, {
      custom_fields: customFields
    })
    return response.data
  }

  // ============ SUGGESTED CONTRACT LINKS ============

  /**
   * Get suggested links for a specific contract.
   */
  async getSuggestedLinks(contractId: string, statusFilter?: string): Promise<SuggestedLinksListResponse> {
    const response = await this.client.get<SuggestedLinksListResponse>(
      `/contracts/${contractId}/suggested-links`,
      { params: statusFilter ? { status_filter: statusFilter } : undefined }
    )
    return response.data
  }

  /**
   * Review (approve/reject/modify) a suggested link.
   */
  async reviewSuggestedLink(
    contractId: string,
    suggestionId: string,
    action: 'approve' | 'reject' | 'modify',
    modifiedLinkType?: string
  ): Promise<SuggestedLinkReviewResponse> {
    const response = await this.client.post<SuggestedLinkReviewResponse>(
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
  async batchReviewSuggestedLinks(
    contractId: string,
    suggestionIds: string[],
    action: 'approve' | 'reject',
    notes?: string
  ): Promise<BatchReviewResponse> {
    const response = await this.client.post<BatchReviewResponse>(
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
  async getAllPendingSuggestions(limit = 50): Promise<PendingSuggestionsResponse> {
    const response = await this.client.get<PendingSuggestionsResponse>(
      '/contracts/pending-suggestions',
      { params: { limit } }
    )
    return response.data
  }
}

export const api = new ApiClient()
export default api
