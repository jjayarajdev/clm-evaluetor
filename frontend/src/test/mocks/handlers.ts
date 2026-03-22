import { http, HttpResponse } from 'msw'

// Mock data
export const mockUser = {
  id: 'user-1',
  email: 'admin@example.com',
  full_name: 'Admin User',
  role: 'ADMIN',
  tenant_id: 'tenant-1',
  is_active: true,
}

export const mockTenant = {
  id: 'tenant-1',
  name: 'Acme Corp',
  slug: 'acme',
  is_active: true,
}

export const mockContracts = [
  {
    id: 'contract-1',
    filename: 'Master Service Agreement.pdf',
    contract_type: 'master_service_agreement',
    status: 'active',
    counterparty: 'Vendor Corp',
    effective_date: '2024-01-01',
    expiration_date: '2025-01-01',
    total_value: 100000,
    currency: 'USD',
    risk_level: 'medium',
    created_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'contract-2',
    filename: 'NDA Agreement.pdf',
    contract_type: 'nda',
    status: 'active',
    counterparty: 'Partner Inc',
    effective_date: '2024-02-01',
    expiration_date: '2025-02-01',
    total_value: 0,
    currency: 'USD',
    risk_level: 'low',
    created_at: '2024-02-01T00:00:00Z',
  },
]

export const mockDashboardStats = {
  total_contracts: 10,
  active_contracts: 8,
  expiring_soon: 2,
  high_risk_contracts: 1,
  total_value: 500000,
  pending_obligations: 5,
  overdue_obligations: 1,
}

export const mockBusinessUnits = [
  { id: 'bu-1', name: 'Legal', code: 'LEGAL', is_active: true },
  { id: 'bu-2', name: 'Procurement', code: 'PROC', is_active: true },
]

export const mockExternalUsers = [
  {
    id: 'ext-1',
    email: 'vendor@external.com',
    full_name: 'Vendor Contact',
    company_name: 'Vendor Corp',
    is_active: true,
  },
]

// API handlers
export const handlers = [
  // Auth endpoints
  http.post('/api/auth/login', async ({ request }) => {
    const body = await request.json() as { email: string; password: string }
    if (body.email && body.password) {
      return HttpResponse.json({
        access_token: 'mock-token-123',
        token_type: 'bearer',
        user: mockUser,
        tenant: mockTenant,
      })
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
  }),

  http.get('/api/auth/me', () => {
    return HttpResponse.json(mockUser)
  }),

  http.post('/api/auth/logout', () => {
    return HttpResponse.json({ message: 'Logged out' })
  }),

  // Contracts endpoints
  http.get('/api/contracts', ({ request }) => {
    const url = new URL(request.url)
    const page = parseInt(url.searchParams.get('page') || '1')
    const pageSize = parseInt(url.searchParams.get('page_size') || '10')

    return HttpResponse.json({
      items: mockContracts,
      total: mockContracts.length,
      page,
      page_size: pageSize,
      pages: 1,
    })
  }),

  http.get('/api/contracts/:id', ({ params }) => {
    const contract = mockContracts.find(c => c.id === params.id)
    if (contract) {
      return HttpResponse.json({
        ...contract,
        clauses: [],
        obligations: [],
        key_dates: [],
      })
    }
    return HttpResponse.json({ detail: 'Contract not found' }, { status: 404 })
  }),

  http.post('/api/contracts/upload', () => {
    return HttpResponse.json({
      id: 'new-contract-1',
      filename: 'uploaded.pdf',
      status: 'processing',
    })
  }),

  // Dashboard endpoints
  http.get('/api/dashboard/legal', () => {
    return HttpResponse.json({
      ...mockDashboardStats,
      recent_contracts: mockContracts.slice(0, 5),
      upcoming_renewals: [],
      risk_distribution: { low: 5, medium: 3, high: 2 },
    })
  }),

  http.get('/api/dashboard/procurement', () => {
    return HttpResponse.json({
      ...mockDashboardStats,
      vendor_performance: [],
      pending_approvals: [],
    })
  }),

  http.get('/api/dashboard/admin', () => {
    return HttpResponse.json({
      ...mockDashboardStats,
      user_activity: [],
      system_health: { status: 'healthy' },
    })
  }),

  // Business Units endpoints
  http.get('/api/business-units', () => {
    return HttpResponse.json({
      items: mockBusinessUnits,
      total: mockBusinessUnits.length,
    })
  }),

  http.post('/api/business-units', async ({ request }) => {
    const body = await request.json() as { name: string; code: string }
    return HttpResponse.json({
      id: 'new-bu-1',
      ...body,
      is_active: true,
    })
  }),

  // External Users endpoints
  http.get('/api/external-users', () => {
    return HttpResponse.json({
      items: mockExternalUsers,
      total: mockExternalUsers.length,
    })
  }),

  http.post('/api/external-users', async ({ request }) => {
    const body = await request.json() as { email: string; full_name: string }
    return HttpResponse.json({
      id: 'new-ext-1',
      ...body,
      is_active: true,
    })
  }),

  // Users endpoint
  http.get('/api/users', () => {
    return HttpResponse.json({
      items: [mockUser],
      total: 1,
    })
  }),

  // Tenants endpoint (for super admin)
  http.get('/api/tenants', () => {
    return HttpResponse.json({
      items: [mockTenant],
      total: 1,
    })
  }),

  // Query endpoint
  http.post('/api/query', async ({ request }) => {
    const body = await request.json() as { question: string }
    return HttpResponse.json({
      answer: `This is a mock answer to: ${body.question}`,
      sources: [],
      confidence: 0.95,
    })
  }),
]
