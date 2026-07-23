const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api'

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  headers?: Record<string, string>
}

export class APIClient {
  private static token: string | null = null

  static setToken(token: string) {
    this.token = token
  }

  static getToken(): string | null {
    return this.token
  }

  private static async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...options.headers,
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    })

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`API Error: ${response.status} - ${error}`)
    }

    return response.json()
  }

  // Dashboard Endpoints
  static async getDashboardSummary() {
    return this.request('/dashboard/summary')
  }

  static async getDashboardMetrics() {
    return this.request('/dashboard/metrics')
  }

  // SLA Endpoints
  static async getSLACompliance(contractId?: string) {
    const params = contractId ? `?contract_id=${contractId}` : ''
    return this.request(`/sla/compliance/summary${params}`)
  }

  static async getActiveSLABreaches() {
    return this.request('/sla/breaches/active')
  }

  static async getContractSLAs(contractId: string, includeInactive = false) {
    const params = includeInactive ? '?include_inactive=true' : ''
    return this.request(`/sla/${contractId}${params}`)
  }

  static async getAllSLAs(filters?: {
    metricType?: string
    severity?: string
    hasBreach?: boolean
    limit?: number
    offset?: number
  }) {
    const params = new URLSearchParams()
    if (filters) {
      if (filters.metricType) params.append('metric_type', filters.metricType)
      if (filters.severity) params.append('severity', filters.severity)
      if (filters.hasBreach !== undefined) params.append('has_breach', String(filters.hasBreach))
      if (filters.limit) params.append('limit', String(filters.limit))
      if (filters.offset) params.append('offset', String(filters.offset))
    }
    const query = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/sla/${query}`)
  }

  static async createSLA(contractId: string, slaData: {
    sla_name: string
    sla_description: string
    metric_type: string
    metric_unit: string
    target_value: number
    target_operator: string
    warning_threshold: number
    severity: string
    has_penalty: boolean
    penalty_type?: string
    penalty_value?: number
    penalty_description?: string
    max_penalty_cap?: number
    measurement_period: string
    source_text?: string
    source_clause_id?: string
  }) {
    return this.request(`/sla/${contractId}`, {
      method: 'POST',
      body: slaData,
    })
  }

  static async logSLAPerformance(
    contractId: string,
    slaId: string,
    performanceData: {
      actual_value: number
      measured_at: string
      measurement_period_start: string
      measurement_period_end: string
      notes?: string
      recorded_by?: string
    }
  ) {
    return this.request(`/sla/${contractId}/performance/${slaId}`, {
      method: 'POST',
      body: performanceData,
    })
  }

  // Vendor Endpoints
  static async getVendors(filters?: {
    page?: number
    page_size?: number
    search?: string
    status?: string
  }) {
    const params = new URLSearchParams()
    if (filters) {
      if (filters.page) params.append('page', String(filters.page))
      if (filters.page_size) params.append('page_size', String(filters.page_size))
      if (filters.search) params.append('search', filters.search)
      if (filters.status) params.append('status', filters.status)
    }
    const query = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/vendors${query}`)
  }

  static async getVendor(vendorId: string) {
    return this.request(`/vendors/${vendorId}`)
  }

  static async getVendorScoring(vendorId: string) {
    return this.request(`/vendors/${vendorId}/scoring`)
  }

  static async getVendorScorecard(vendorId: string) {
    return this.request(`/vendors/${vendorId}/scorecard`)
  }

  static async getAllVendorScores(filters?: {
    page?: number
    page_size?: number
    sortBy?: string
  }) {
    const params = new URLSearchParams()
    if (filters) {
      if (filters.page) params.append('page', String(filters.page))
      if (filters.page_size) params.append('page_size', String(filters.page_size))
      if (filters.sortBy) params.append('sort_by', filters.sortBy)
    }
    const query = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/vendors/scores${query}`)
  }

  // Contracts Endpoints
  static async getContracts(filters?: {
    page?: number
    page_size?: number
    contractType?: string
    counterparty?: string
    riskLevel?: string
    statusFilter?: string
    search?: string
    sortBy?: string
    sortDesc?: boolean
  }) {
    const params = new URLSearchParams()
    if (filters) {
      if (filters.page) params.append('page', String(filters.page))
      if (filters.page_size) params.append('page_size', String(filters.page_size))
      if (filters.contractType) params.append('contract_type', filters.contractType)
      if (filters.counterparty) params.append('counterparty', filters.counterparty)
      if (filters.riskLevel) params.append('risk_level', filters.riskLevel)
      if (filters.statusFilter) params.append('status_filter', filters.statusFilter)
      if (filters.search) params.append('search', filters.search)
      if (filters.sortBy) params.append('sort_by', filters.sortBy)
      if (filters.sortDesc !== undefined) params.append('sort_desc', String(filters.sortDesc))
    }
    const query = params.toString() ? `?${params.toString()}` : ''
    return this.request(`/contracts${query}`)
  }

  static async getContract(contractId: string) {
    return this.request(`/contracts/${contractId}`)
  }

  // Authentication Endpoints
  static async login(username: string, password: string) {
    return this.request('/auth/login', {
      method: 'POST',
      body: { username, password },
    })
  }

  static async getCurrentUser() {
    return this.request('/auth/me')
  }

  static async logout() {
    return this.request('/auth/logout', {
      method: 'POST',
    })
  }
}
