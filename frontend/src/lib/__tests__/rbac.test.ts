import { describe, it, expect } from 'vitest'
import { can, permissionsForUser, defaultLandingFor, ROLE_PERMISSIONS, type Permission } from '../rbac'
import type { Role, User } from '@/types'

const user = (role: Role, permissions?: string[]): User => ({
  id: '1',
  username: 'u',
  email: 'u@example.com',
  role,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  permissions,
})

describe('rbac ROLE_PERMISSIONS matrix', () => {
  it('viewer is read-only: sees portfolio, no upload/edit/admin', () => {
    const v = user('viewer')
    // read-only nav present
    for (const p of ['dashboard', 'contracts', 'groups', 'postSigning', 'renewals', 'reports'] as Permission[]) {
      expect(can(v, p)).toBe(true)
    }
    // no writes / admin
    for (const p of ['upload', 'contract.edit', 'contract.editFields', 'sla.edit', 'admin', 'superadmin'] as Permission[]) {
      expect(can(v, p)).toBe(false)
    }
  })

  it('viewer is NOT locked out entirely (regression: empty sidebar bug)', () => {
    expect(permissionsForUser(user('viewer')).length).toBeGreaterThan(0)
  })

  it('procurement can edit custom fields but NOT core metadata', () => {
    const p = user('procurement')
    expect(can(p, 'contract.editFields')).toBe(true)
    expect(can(p, 'contract.edit')).toBe(false)
    expect(can(p, 'vendors')).toBe(true)
    expect(can(p, 'admin')).toBe(false)
  })

  it('legal can edit metadata + SLAs, but not vendors or admin', () => {
    const l = user('legal')
    expect(can(l, 'contract.edit')).toBe(true)
    expect(can(l, 'sla.edit')).toBe(true)
    expect(can(l, 'surveys')).toBe(true)
    expect(can(l, 'vendors')).toBe(false)
    expect(can(l, 'admin')).toBe(false)
    expect(can(l, 'superadmin')).toBe(false)
  })

  it('admin has the admin section but NOT the super-admin platform', () => {
    const a = user('admin')
    expect(can(a, 'admin')).toBe(true)
    expect(can(a, 'settings')).toBe(true)
    expect(can(a, 'kpiApprovals')).toBe(true)
    expect(can(a, 'contract.edit')).toBe(true)
    expect(can(a, 'superadmin')).toBe(false)
  })

  it('super_admin has the platform + shared curation, but NOT tenant admin/kpi', () => {
    const s = user('super_admin')
    expect(can(s, 'superadmin')).toBe(true)
    expect(can(s, 'extraction.configure')).toBe(true)
    expect(can(s, 'contract.edit')).toBe(true)
    // manages tenants via /super-admin, not the tenant admin section
    expect(can(s, 'admin')).toBe(false)
    expect(can(s, 'kpiApprovals')).toBe(false)
  })

  it('bu_head is view-oriented: no upload/edit/admin', () => {
    const b = user('bu_head')
    expect(can(b, 'vendors')).toBe(true)
    expect(can(b, 'reports')).toBe(true)
    expect(can(b, 'upload')).toBe(false)
    expect(can(b, 'contract.edit')).toBe(false)
    expect(can(b, 'admin')).toBe(false)
  })

  it('every role only holds valid, non-duplicated permissions', () => {
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      expect(new Set(perms).size).toBe(perms.length) // no duplicates
    }
  })
})

describe('permissionsForUser (backend-ready override)', () => {
  it('prefers a backend-provided permission list when present', () => {
    const custom = user('viewer', ['admin', 'superadmin'])
    expect(can(custom, 'admin')).toBe(true)
    expect(can(custom, 'superadmin')).toBe(true)
  })

  it('falls back to the role map when no backend permissions', () => {
    expect(permissionsForUser(user('admin'))).toEqual(ROLE_PERMISSIONS.admin)
  })

  it('returns nothing for a null user', () => {
    expect(permissionsForUser(null)).toEqual([])
    expect(can(null, 'dashboard')).toBe(false)
  })
})

describe('defaultLandingFor', () => {
  it('routes super_admin to the platform, everyone else to the dashboard', () => {
    expect(defaultLandingFor(user('super_admin'))).toBe('/super-admin')
    expect(defaultLandingFor(user('admin'))).toBe('/dashboard')
    expect(defaultLandingFor(user('viewer'))).toBe('/dashboard')
    expect(defaultLandingFor(null)).toBe('/dashboard')
  })
})
