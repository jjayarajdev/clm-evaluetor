/**
 * API client re-export shim.
 *
 * The monolithic ApiClient class has been split into domain modules
 * under src/lib/api/. This file re-exports the unified api object
 * for backward compatibility — existing imports continue to work:
 *
 *   import api from '@/lib/api'         // default import
 *   import { api } from '@/lib/api'     // named import
 *
 * New code should import from domain modules directly:
 *   import { getContracts } from '@/lib/api/contracts'
 *   import { getAdminDashboard } from '@/lib/api/admin'
 */

export { api, default } from './api/index'
