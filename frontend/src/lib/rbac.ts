// Role-based access control — FALLBACK ONLY. The source of truth is the
// DB-backed matrix served by the backend on /auth/login and /auth/me
// (user.permissions), edited by super admins at /super-admin/role-permissions.
// permissionsForUser() below prefers that list; this static map applies only
// when the backend didn't provide one (stale session, older backend).
// Keep it mirroring backend DEFAULT_ROLE_PERMISSIONS (app/core/permissions.py).
import type { Role, User } from '@/types'

// A capability. Nav/route permissions gate navigation + routes; action
// permissions gate in-page edit controls.
export type Permission =
  // Nav / route access
  | 'dashboard'
  | 'contracts'
  | 'groups'
  | 'postSigning'
  | 'renewals'
  | 'vendors'
  | 'reports'
  | 'upload'
  | 'organizations'
  | 'relationships'
  | 'kpiApprovals'
  | 'surveys'
  | 'askAi'
  | 'usage' // usage meters page; pages for everyone, tokens+cost admin-only (API-enforced)
  | 'settings'
  | 'admin' // tenant-admin section + routes (/users, /admin/*, /kpi-approvals)
  | 'superadmin' // platform super-admin routes (/super-admin/*)
  // Actions
  | 'contract.edit' // edit core contract metadata (counterparty, type, dates, value)
  | 'contract.editFields' // edit tenant custom fields
  | 'sla.edit'
  | 'extraction.configure'

// THE config. Each role → the capabilities it has. Edit here to change access.
export const ROLE_PERMISSIONS: Record<Role, Permission[]> = {
  super_admin: [
    'superadmin',
    // super-admin curates the shared extraction/industry-profile tools and can
    // edit contract data, but manages tenant users via the /super-admin pages
    // (not the tenant 'admin' section).
    'extraction.configure',
    'contract.edit', 'contract.editFields',
  ],
  admin: [
    'dashboard', 'contracts', 'groups', 'postSigning', 'renewals',
    'vendors', 'reports', 'upload',
    'organizations', 'relationships', 'kpiApprovals', 'surveys',
    'askAi', 'usage', 'settings', 'admin',
    'contract.edit', 'contract.editFields', 'sla.edit', 'extraction.configure',
  ],
  legal: [
    'dashboard', 'contracts', 'groups', 'postSigning', 'renewals',
    'reports', 'upload',
    'organizations', 'relationships', 'surveys', 'askAi', 'usage',
    'contract.edit', 'contract.editFields', 'sla.edit',
  ],
  procurement: [
    'dashboard', 'contracts', 'groups', 'postSigning', 'renewals',
    'vendors', 'upload',
    'organizations', 'relationships', 'askAi', 'usage',
    // procurement can set custom fields but not core contract metadata
    'contract.editFields',
  ],
  bu_head: [
    'dashboard', 'contracts', 'groups', 'postSigning', 'renewals',
    'vendors', 'reports', 'usage',
  ],
  // Read-only role — was previously locked out of the entire UI. Sees the
  // portfolio, no create/edit/upload/admin.
  viewer: [
    'dashboard', 'contracts', 'groups', 'postSigning', 'renewals', 'reports', 'usage',
  ],
}

// Resolve a user's effective permissions. Prefers a backend-provided list when
// present (future tenant-customizable RBAC); otherwise the static role map.
export function permissionsForUser(user: User | null): Permission[] {
  if (!user) return []
  if (user.permissions && user.permissions.length > 0) {
    return user.permissions as Permission[]
  }
  return ROLE_PERMISSIONS[user.role] ?? []
}

export function can(user: User | null, permission: Permission): boolean {
  return permissionsForUser(user).includes(permission)
}

// Where a role should land after login / when redirected from a forbidden route.
export function defaultLandingFor(user: User | null): string {
  if (user?.role === 'super_admin') return '/super-admin'
  return '/dashboard'
}
