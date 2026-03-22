import { APIRequestContext, expect } from '@playwright/test'
import { endpoints } from '../fixtures/test-data'

/**
 * API helper utilities for E2E tests
 */

export interface ApiOptions {
  token?: string
  tenantId?: string
}

/**
 * Build headers with authentication
 */
export function buildHeaders(options: ApiOptions = {}): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (options.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }

  if (options.tenantId) {
    headers['X-Tenant-ID'] = options.tenantId
  }

  return headers
}

/**
 * Contract API helpers
 */
export const contractApi = {
  async list(request: APIRequestContext, options: ApiOptions & { page?: number; pageSize?: number } = {}) {
    const params = new URLSearchParams()
    if (options.page) params.set('page', options.page.toString())
    if (options.pageSize) params.set('page_size', options.pageSize.toString())

    const url = `${endpoints.contracts.list}${params.toString() ? '?' + params.toString() : ''}`

    const response = await request.get(url, {
      headers: buildHeaders(options),
    })

    if (response.ok()) {
      const rawData = await response.json()
      // Normalize response: API returns 'contracts', tests expect 'items'
      return {
        response,
        data: {
          items: rawData.contracts || rawData.items || [],
          total: rawData.total || 0,
          page: rawData.page || 1,
          page_size: rawData.page_size || 20,
        },
      }
    }

    return { response, data: null }
  },

  async get(request: APIRequestContext, contractId: string, options: ApiOptions = {}) {
    const response = await request.get(endpoints.contracts.detail(contractId), {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async share(
    request: APIRequestContext,
    contractId: string,
    shareData: {
      external_user_id: string
      can_download?: boolean
      can_comment?: boolean
      expires_in_days?: number
      message?: string
    },
    options: ApiOptions = {}
  ) {
    const response = await request.post(endpoints.contracts.share(contractId), {
      headers: buildHeaders(options),
      data: shareData,
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async getShares(request: APIRequestContext, contractId: string, options: ApiOptions = {}) {
    const response = await request.get(endpoints.contracts.shares(contractId), {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },
}

/**
 * Business Unit API helpers
 */
export const businessUnitApi = {
  async list(request: APIRequestContext, options: ApiOptions = {}) {
    const response = await request.get(endpoints.businessUnits.list, {
      headers: buildHeaders(options),
    })

    if (response.ok()) {
      const rawData = await response.json()
      // Normalize: could be { items: [] } or { business_units: [] } or []
      const items = rawData.items || rawData.business_units || (Array.isArray(rawData) ? rawData : [])
      return {
        response,
        data: { items, total: rawData.total || items.length },
      }
    }

    return { response, data: null }
  },

  async create(
    request: APIRequestContext,
    data: { name: string; code: string; description?: string },
    options: ApiOptions = {}
  ) {
    const response = await request.post(endpoints.businessUnits.create, {
      headers: buildHeaders(options),
      data,
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async get(request: APIRequestContext, buId: string, options: ApiOptions = {}) {
    const response = await request.get(endpoints.businessUnits.detail(buId), {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async update(
    request: APIRequestContext,
    buId: string,
    data: { name?: string; code?: string; description?: string },
    options: ApiOptions = {}
  ) {
    const response = await request.put(endpoints.businessUnits.detail(buId), {
      headers: buildHeaders(options),
      data,
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async delete(request: APIRequestContext, buId: string, options: ApiOptions = {}) {
    const response = await request.delete(endpoints.businessUnits.detail(buId), {
      headers: buildHeaders(options),
    })

    return { response }
  },
}

/**
 * External User API helpers
 */
export const externalUserApi = {
  async list(request: APIRequestContext, options: ApiOptions = {}) {
    const response = await request.get(endpoints.externalUsers.list, {
      headers: buildHeaders(options),
    })

    if (response.ok()) {
      const rawData = await response.json()
      // Normalize: could be { items: [] } or { external_users: [] } or []
      const items = rawData.items || rawData.external_users || (Array.isArray(rawData) ? rawData : [])
      return {
        response,
        data: { items, total: rawData.total || items.length },
      }
    }

    return { response, data: null }
  },

  async create(
    request: APIRequestContext,
    data: {
      email: string
      full_name?: string
      company_name?: string
      title?: string
      phone?: string
    },
    options: ApiOptions = {}
  ) {
    const response = await request.post(endpoints.externalUsers.create, {
      headers: buildHeaders(options),
      data,
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async get(request: APIRequestContext, userId: string, options: ApiOptions = {}) {
    const response = await request.get(endpoints.externalUsers.detail(userId), {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async update(
    request: APIRequestContext,
    userId: string,
    data: {
      email?: string
      full_name?: string
      company_name?: string
      title?: string
      phone?: string
    },
    options: ApiOptions = {}
  ) {
    const response = await request.put(endpoints.externalUsers.detail(userId), {
      headers: buildHeaders(options),
      data,
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async delete(request: APIRequestContext, userId: string, options: ApiOptions = {}) {
    const response = await request.delete(endpoints.externalUsers.detail(userId), {
      headers: buildHeaders(options),
    })

    return { response }
  },
}

/**
 * Dashboard API helpers
 */
export const dashboardApi = {
  async getLegal(request: APIRequestContext, options: ApiOptions = {}) {
    const response = await request.get(endpoints.dashboard.legal, {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async getProcurement(request: APIRequestContext, options: ApiOptions = {}) {
    const response = await request.get(endpoints.dashboard.procurement, {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },

  async getAdmin(request: APIRequestContext, options: ApiOptions = {}) {
    const response = await request.get(endpoints.dashboard.admin, {
      headers: buildHeaders(options),
    })

    return {
      response,
      data: response.ok() ? await response.json() : null,
    }
  },
}

/**
 * Query API helper
 */
export async function queryContracts(
  request: APIRequestContext,
  question: string,
  options: ApiOptions & { contractId?: string } = {}
) {
  const response = await request.post(endpoints.query, {
    headers: buildHeaders(options),
    data: {
      question,
      contract_id: options.contractId,
    },
  })

  return {
    response,
    data: response.ok() ? await response.json() : null,
  }
}
