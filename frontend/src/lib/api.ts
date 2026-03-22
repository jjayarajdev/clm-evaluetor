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
  ChatSession,
  ChatSessionDetail,
  ChatMessageOut,
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
          // Don't redirect on login failure — let the login page handle the error
          const url = error.config?.url || ''
          if (!url.includes('/auth/login')) {
            this.clearToken()
            window.location.href = '/login'
          }
        }
        // Extract API error message for display
        const detail = (error.response?.data as Record<string, string>)?.detail
        if (detail) {
          return Promise.reject(new Error(detail))
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

  // Chat session endpoints
  async getChatSessions(): Promise<ChatSession[]> {
    const response = await this.client.get<ChatSession[]>('/chat/sessions')
    return response.data
  }

  async createChatSession(title?: string, contractId?: string): Promise<ChatSessionDetail> {
    const response = await this.client.post<ChatSessionDetail>('/chat/sessions', {
      title: title || 'New Chat',
      contract_id: contractId || null,
    })
    return response.data
  }

  async getChatSession(sessionId: string): Promise<ChatSessionDetail> {
    const response = await this.client.get<ChatSessionDetail>(`/chat/sessions/${sessionId}`)
    return response.data
  }

  async deleteChatSession(sessionId: string): Promise<void> {
    await this.client.delete(`/chat/sessions/${sessionId}`)
  }

  async updateChatSessionTitle(sessionId: string, title: string): Promise<ChatSession> {
    const response = await this.client.patch<ChatSession>(`/chat/sessions/${sessionId}`, { title })
    return response.data
  }

  async addChatMessage(sessionId: string, message: {
    role: string
    content: string
    sources?: unknown[]
    follow_ups?: string[]
    visualizations?: unknown[]
  }): Promise<ChatMessageOut> {
    const response = await this.client.post<ChatMessageOut>(
      `/chat/sessions/${sessionId}/messages`,
      message,
    )
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

  async updateUserPassword(id: string, newPassword: string): Promise<User> {
    const response = await this.client.put<User>(`/users/${id}/password`, { new_password: newPassword })
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

  async uploadObligationEvidence(obligationId: string, data: {
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
    const response = await this.client.post(`/obligations/${obligationId}/evidence`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
    return response.data
  }

  // Calendar export
  async exportCalendarICS(options?: {
    include_expirations?: boolean
    include_notice_deadlines?: boolean
    include_obligations?: boolean
    include_key_dates?: boolean
    days_ahead?: number
  }): Promise<Blob> {
    const response = await this.client.get('/renewals/export/calendar.ics', {
      params: options,
      responseType: 'blob',
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

  // ============ SUPER ADMIN: CROSS-TENANT USER ENDPOINTS ============

  async getAllUsers(tenantId?: string): Promise<UserWithTenant[]> {
    const params: Record<string, string> = {}
    if (tenantId) params.tenant_id = tenantId
    const response = await this.client.get<{ users: User[]; total: number }>('/users', { params })
    return response.data.users.map((u: any) => ({ ...u, tenant_id: u.tenant_id || '' }))
  }

  async createUserForTenant(tenantId: string, data: { username: string; email: string; password: string; role: string }): Promise<User> {
    const response = await this.client.post<User>('/users', { ...data, tenant_id: tenantId })
    return response.data
  }

  async getTenantUsers(tenantId: string): Promise<User[]> {
    const params = { tenant_id: tenantId }
    const response = await this.client.get<{ users: User[]; total: number }>('/users', { params })
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

  // ============ ESTABLISHED CONTRACT LINKS ============

  /**
   * Get established (approved) contract links for a contract.
   */
  async getContractLinks(contractId: string): Promise<import('@/types').ContractLinksResponse> {
    const response = await this.client.get<import('@/types').ContractLinksResponse>(
      `/contracts/${contractId}/links`
    )
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

  // ============ BUSINESS UNITS ============

  /**
   * Get business units list with pagination.
   */
  async getBusinessUnits(params?: {
    page?: number
    page_size?: number
    active_only?: boolean
    parent_id?: string
  }, tenantId?: string): Promise<import('@/types/business-unit').BusinessUnitListResponse> {
    const config = tenantId ? { params, headers: { 'X-Tenant-ID': tenantId } } : { params }
    const response = await this.client.get<import('@/types/business-unit').BusinessUnitListResponse>(
      '/business-units',
      config
    )
    return response.data
  }

  /**
   * Get business units as a tree structure.
   */
  async getBusinessUnitsTree(tenantId?: string): Promise<import('@/types/business-unit').BusinessUnitTree[]> {
    const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
    const response = await this.client.get<import('@/types/business-unit').BusinessUnitTree[]>(
      '/business-units/tree',
      config
    )
    return response.data
  }

  /**
   * Get a single business unit by ID.
   */
  async getBusinessUnit(id: string, tenantId?: string): Promise<import('@/types/business-unit').BusinessUnit> {
    const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
    const response = await this.client.get<import('@/types/business-unit').BusinessUnit>(
      `/business-units/${id}`,
      config
    )
    return response.data
  }

  /**
   * Create a new business unit.
   */
  async createBusinessUnit(data: import('@/types/business-unit').BusinessUnitCreate, tenantId?: string): Promise<import('@/types/business-unit').BusinessUnit> {
    const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
    const response = await this.client.post<import('@/types/business-unit').BusinessUnit>(
      '/business-units',
      data,
      config
    )
    return response.data
  }

  /**
   * Update a business unit.
   */
  async updateBusinessUnit(id: string, data: import('@/types/business-unit').BusinessUnitUpdate, tenantId?: string): Promise<import('@/types/business-unit').BusinessUnit> {
    const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
    const response = await this.client.put<import('@/types/business-unit').BusinessUnit>(
      `/business-units/${id}`,
      data,
      config
    )
    return response.data
  }

  /**
   * Delete (deactivate) a business unit.
   */
  async deleteBusinessUnit(id: string, tenantId?: string): Promise<void> {
    const config = tenantId ? { headers: { 'X-Tenant-ID': tenantId } } : {}
    await this.client.delete(`/business-units/${id}`, config)
  }

  // ============ EXTERNAL USERS ============

  /**
   * Get external users list.
   */
  async getExternalUsers(params?: {
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
    const response = await this.client.get('/external-users', { params })
    return response.data
  }

  /**
   * Create an external user.
   */
  async createExternalUser(data: {
    email: string
    full_name?: string
    company_name?: string
    title?: string
    phone?: string
  }): Promise<unknown> {
    const response = await this.client.post('/external-users', data)
    return response.data
  }

  /**
   * Update an external user.
   */
  async updateExternalUser(id: string, data: {
    email?: string
    full_name?: string
    company_name?: string
    title?: string
    phone?: string
  }): Promise<unknown> {
    const response = await this.client.put(`/external-users/${id}`, data)
    return response.data
  }

  /**
   * Delete (deactivate) an external user.
   */
  async deleteExternalUser(id: string): Promise<void> {
    await this.client.delete(`/external-users/${id}`)
  }

  // ============ CONTRACT SHARING ============

  /**
   * Share a contract with an external user.
   */
  async shareContract(
    contractId: string,
    data: import('@/types/contract-share').ContractShareCreate
  ): Promise<import('@/types/contract-share').ShareInviteResponse> {
    const response = await this.client.post<import('@/types/contract-share').ShareInviteResponse>(
      `/contracts/${contractId}/share`,
      data
    )
    return response.data
  }

  /**
   * List all shares for a contract.
   */
  async getContractShares(
    contractId: string,
    includeRevoked = false
  ): Promise<import('@/types/contract-share').ContractShareListResponse> {
    const response = await this.client.get<import('@/types/contract-share').ContractShareListResponse>(
      `/contracts/${contractId}/shares`,
      { params: { include_revoked: includeRevoked } }
    )
    return response.data
  }

  /**
   * Revoke a contract share.
   */
  async revokeContractShare(contractId: string, shareId: string): Promise<void> {
    await this.client.delete(`/contracts/${contractId}/shares/${shareId}`)
  }

  // ============================================================================
  // Notification Rules endpoints
  // ============================================================================

  async getNotificationRules(options?: { eventType?: string; activeOnly?: boolean }): Promise<unknown[]> {
    const response = await this.client.get('/notification-rules', {
      params: {
        event_type: options?.eventType,
        active_only: options?.activeOnly ?? true,
      },
    })
    return response.data
  }

  async getNotificationRuleTemplates(): Promise<unknown[]> {
    const response = await this.client.get('/notification-rules/templates')
    return response.data
  }

  async getNotificationRule(ruleId: string): Promise<unknown> {
    const response = await this.client.get(`/notification-rules/${ruleId}`)
    return response.data
  }

  async createNotificationRule(data: {
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
    const response = await this.client.post('/notification-rules', data)
    return response.data
  }

  async createNotificationRuleFromTemplate(templateIndex: number): Promise<unknown> {
    const response = await this.client.post(`/notification-rules/from-template/${templateIndex}`)
    return response.data
  }

  async updateNotificationRule(ruleId: string, data: Record<string, unknown>): Promise<unknown> {
    const response = await this.client.put(`/notification-rules/${ruleId}`, data)
    return response.data
  }

  async deleteNotificationRule(ruleId: string): Promise<void> {
    await this.client.delete(`/notification-rules/${ruleId}`)
  }

  async toggleNotificationRule(ruleId: string): Promise<unknown> {
    const response = await this.client.post(`/notification-rules/${ruleId}/toggle`)
    return response.data
  }

  async getNotificationRuleStats(): Promise<unknown> {
    const response = await this.client.get('/notification-rules/summary/stats')
    return response.data
  }

  // ============================================================================
  // Relationship Governance: Organizations
  // ============================================================================

  async getOrganizations(params?: {
    org_type?: string
    search?: string
    active_only?: boolean
  }): Promise<import('@/types/governance').Organization[]> {
    const response = await this.client.get('/organizations', { params })
    return response.data.items ?? response.data
  }

  async getOrganization(id: string): Promise<import('@/types/governance').Organization> {
    const response = await this.client.get(`/organizations/${id}`)
    return response.data
  }

  async createOrganization(data: import('@/types/governance').OrganizationCreate): Promise<import('@/types/governance').Organization> {
    const response = await this.client.post('/organizations', data)
    return response.data
  }

  async updateOrganization(id: string, data: import('@/types/governance').OrganizationUpdate): Promise<import('@/types/governance').Organization> {
    const response = await this.client.put(`/organizations/${id}`, data)
    return response.data
  }

  async deleteOrganization(id: string): Promise<void> {
    await this.client.delete(`/organizations/${id}`)
  }

  // ============================================================================
  // Relationship Governance: Relationships
  // ============================================================================

  async getRelationships(params?: {
    status?: string
    relationship_type?: string
  }): Promise<import('@/types/governance').BusinessRelationship[]> {
    const response = await this.client.get('/relationships', { params })
    return response.data.items ?? response.data
  }

  async getRelationship(id: string): Promise<import('@/types/governance').BusinessRelationship> {
    const response = await this.client.get(`/relationships/${id}`)
    return response.data
  }

  async createRelationship(data: import('@/types/governance').RelationshipCreate): Promise<import('@/types/governance').BusinessRelationship> {
    const response = await this.client.post('/relationships', data)
    return response.data
  }

  async updateRelationship(id: string, data: import('@/types/governance').RelationshipUpdate): Promise<import('@/types/governance').BusinessRelationship> {
    const response = await this.client.put(`/relationships/${id}`, data)
    return response.data
  }

  async getRelationshipTeam(id: string): Promise<import('@/types/governance').RelationshipTeamMember[]> {
    const response = await this.client.get(`/relationships/${id}/team`)
    return response.data.items ?? response.data
  }

  async addTeamMember(relationshipId: string, data: import('@/types/governance').TeamMemberCreate): Promise<import('@/types/governance').RelationshipTeamMember> {
    const response = await this.client.post(`/relationships/${relationshipId}/team`, data)
    return response.data
  }

  async removeTeamMember(relationshipId: string, memberId: string): Promise<void> {
    await this.client.delete(`/relationships/${relationshipId}/team/${memberId}`)
  }

  // ============================================================================
  // Relationship Governance: KPIs & Perception
  // ============================================================================

  async getKPIs(params?: {
    relationship_id?: string
    category?: string
    active_only?: boolean
  }): Promise<import('@/types/governance').KPI[]> {
    const response = await this.client.get('/kpis', { params })
    return response.data.items ?? response.data
  }

  async getKPI(id: string): Promise<import('@/types/governance').KPI> {
    const response = await this.client.get(`/kpis/${id}`)
    return response.data
  }

  async createKPI(data: import('@/types/governance').KPICreate): Promise<import('@/types/governance').KPI> {
    const response = await this.client.post('/kpis', data)
    return response.data
  }

  async updateKPI(id: string, data: import('@/types/governance').KPIUpdate): Promise<import('@/types/governance').KPI> {
    const response = await this.client.put(`/kpis/${id}`, data)
    return response.data
  }

  async deleteKPI(id: string): Promise<void> {
    await this.client.delete(`/kpis/${id}`)
  }

  async getPerceptionScores(kpiId: string): Promise<import('@/types/governance').PerceptionScore[]> {
    const response = await this.client.get(`/kpis/${kpiId}/scores`)
    return response.data
  }

  async submitPerceptionScore(kpiId: string, data: import('@/types/governance').PerceptionScoreCreate): Promise<import('@/types/governance').PerceptionScore> {
    const response = await this.client.post(`/kpis/${kpiId}/scores`, data)
    return response.data
  }

  async getPerceptionGaps(kpiId: string): Promise<import('@/types/governance').PerceptionGap[]> {
    const response = await this.client.get(`/kpis/${kpiId}/gaps`)
    return response.data
  }

  async getRelationshipGapSummary(relationshipId: string, period?: string): Promise<import('@/types/governance').GapSummary> {
    const response = await this.client.get(`/kpis/relationship/${relationshipId}/gaps`, {
      params: period ? { period } : undefined
    })
    return response.data
  }

  // ============================================================================
  // Relationship Governance: Improvements
  // ============================================================================

  async getImprovements(params?: {
    relationship_id?: string
    status?: string
    priority?: string
  }): Promise<import('@/types/governance').ImprovementPoint[]> {
    const response = await this.client.get('/improvements', { params })
    return response.data.items ?? response.data
  }

  async getImprovement(id: string): Promise<import('@/types/governance').ImprovementPoint> {
    const response = await this.client.get(`/improvements/${id}`)
    return response.data
  }

  async createImprovement(data: import('@/types/governance').ImprovementCreate): Promise<import('@/types/governance').ImprovementPoint> {
    const response = await this.client.post('/improvements', data)
    return response.data
  }

  async updateImprovement(id: string, data: Partial<import('@/types/governance').ImprovementCreate> & { status?: string }): Promise<import('@/types/governance').ImprovementPoint> {
    const response = await this.client.put(`/improvements/${id}`, data)
    return response.data
  }

  async deleteImprovement(id: string): Promise<void> {
    await this.client.delete(`/improvements/${id}`)
  }

  async generateImprovementsFromGaps(relationshipId: string, minSeverity?: string): Promise<import('@/types/governance').ImprovementPoint[]> {
    const response = await this.client.post('/improvements/generate-from-gaps', {
      relationship_id: relationshipId,
      min_severity: minSeverity || 'significant',
    })
    return response.data
  }

  async getImprovementActions(improvementId: string): Promise<import('@/types/governance').ImprovementAction[]> {
    const response = await this.client.get(`/improvements/${improvementId}/actions`)
    return response.data
  }

  async createImprovementAction(improvementId: string, data: import('@/types/governance').ImprovementActionCreate): Promise<import('@/types/governance').ImprovementAction> {
    const response = await this.client.post(`/improvements/${improvementId}/actions`, data)
    return response.data
  }

  // ============================================================================
  // Relationship Governance: Surveys
  // ============================================================================

  async getSurveyTemplates(): Promise<import('@/types/governance').SurveyTemplate[]> {
    const response = await this.client.get('/surveys/templates')
    return response.data.items ?? response.data
  }

  async getSurveyTemplate(id: string): Promise<import('@/types/governance').SurveyTemplate> {
    const response = await this.client.get(`/surveys/templates/${id}`)
    return response.data
  }

  async createSurveyTemplate(data: import('@/types/governance').SurveyTemplateCreate): Promise<import('@/types/governance').SurveyTemplate> {
    const response = await this.client.post('/surveys/templates', data)
    return response.data
  }

  async addSurveyQuestion(templateId: string, data: import('@/types/governance').SurveyQuestionCreate): Promise<import('@/types/governance').SurveyQuestion> {
    const response = await this.client.post(`/surveys/templates/${templateId}/questions`, data)
    return response.data
  }

  async getSurveyInstances(params?: {
    relationship_id?: string
    status?: string
  }): Promise<import('@/types/governance').SurveyInstance[]> {
    const response = await this.client.get('/surveys/instances', { params })
    return response.data.items ?? response.data
  }

  async createSurveyInstance(data: import('@/types/governance').SurveyInstanceCreate): Promise<import('@/types/governance').SurveyInstance> {
    const response = await this.client.post('/surveys/instances', data)
    return response.data
  }

  async sendSurvey(instanceId: string): Promise<import('@/types/governance').SurveyInstance> {
    const response = await this.client.post(`/surveys/instances/${instanceId}/send`)
    return response.data
  }

  async getSurveyResponses(instanceId: string): Promise<import('@/types/governance').SurveyResponse[]> {
    const response = await this.client.get(`/surveys/instances/${instanceId}/responses`)
    return response.data
  }

  async generateSurveyToken(instanceId: string): Promise<{ token: string; url: string }> {
    const response = await this.client.post(`/surveys/instances/${instanceId}/generate-token`)
    return response.data
  }
}

export const api = new ApiClient()
export default api
