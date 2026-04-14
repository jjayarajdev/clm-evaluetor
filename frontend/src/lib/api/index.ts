/**
 * Unified API client — backward-compatible re-export.
 *
 * Domain modules:
 *   client.ts     — Axios instance, auth interceptor, token management
 *   contracts.ts  — Contract CRUD, upload, search, links, documents
 *   compliance.ts — Post-signing, renewals, vendors, SLAs, obligations
 *   governance.ts — Organizations, relationships, KPIs, surveys, improvements
 *   admin.ts      — Dashboards, users, tenants, BUs, settings, scheduler
 *   ai.ts         — Chat, Q&A, ServiceNow integration
 *
 * Pages can import from domain modules directly:
 *   import { getContracts } from '@/lib/api/contracts'
 *
 * Or use the unified api object for backward compatibility:
 *   import { api } from '@/lib/api'
 *   api.getContracts(...)
 */

import * as clientModule from './client'
import * as contracts from './contracts'
import * as compliance from './compliance'
import * as governance from './governance'
import * as admin from './admin'
import * as ai from './ai'

export const api = {
  // Client / auth
  setToken: clientModule.setToken,
  clearToken: clientModule.clearToken,
  getToken: clientModule.getToken,
  login: clientModule.login,
  getCurrentUser: clientModule.getCurrentUser,
  logout: clientModule.logout,

  // Contracts
  ...contracts,

  // Compliance / post-signing
  ...compliance,

  // Governance
  ...governance,

  // Admin / dashboards
  ...admin,

  // AI / chat / integrations
  ...ai,
}

export default api

// Re-export domain modules for direct imports
export { clientModule as client }
export * from './contracts'
export * from './compliance'
export * from './governance'
export * from './admin'
export * from './ai'
export { setToken, clearToken, getToken, login, getCurrentUser, logout } from './client'
