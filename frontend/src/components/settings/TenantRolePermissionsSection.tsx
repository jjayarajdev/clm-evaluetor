// Tenant-admin editor for per-tenant role-permission overrides. Platform
// defaults (set by the super admin) apply unless a role is overridden here;
// an override fully replaces that role's grants for THIS tenant only.
// Guardrails mirror the API: cannot grant superadmin; admin keeps
// 'admin' + 'settings'. Changes take effect on users' next request.
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUturnLeftIcon } from '@heroicons/react/24/outline'
import {
  getTenantRolePermissions,
  resetTenantRolePermissions,
  updateTenantRolePermissions,
} from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

const ADMIN_FLOOR = new Set(['admin', 'settings'])

function groupKey(permission: string): string {
  if (!permission.includes('.')) return 'navigation'
  return permission.split('.')[0]
}

export default function TenantRolePermissionsSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Record<string, Set<string>>>({})
  const [error, setError] = useState<string | null>(null)
  const [savedRole, setSavedRole] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['tenant-role-permissions'],
    queryFn: getTenantRolePermissions,
  })

  useEffect(() => {
    if (data) {
      setDraft(Object.fromEntries(data.roles.map((r) => [r.name, new Set(r.permissions)])))
    }
  }, [data])

  const groups = useMemo(() => {
    const out: Record<string, string[]> = {}
    for (const p of data?.catalog ?? []) {
      (out[groupKey(p)] ??= []).push(p)
    }
    return Object.entries(out).sort(([a], [b]) =>
      a === 'navigation' ? -1 : b === 'navigation' ? 1 : a.localeCompare(b)
    )
  }, [data])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['tenant-role-permissions'] })
  }

  const saveMutation = useMutation({
    mutationFn: ({ role, permissions }: { role: string; permissions: string[] }) =>
      updateTenantRolePermissions(role, permissions),
    onSuccess: (_r, { role }) => {
      invalidate()
      setError(null)
      setSavedRole(role)
      setTimeout(() => setSavedRole(null), 2500)
    },
    onError: (err: Error) => setError(err.message || t('rbac.saveFailed')),
  })

  const resetMutation = useMutation({
    mutationFn: (role: string) => resetTenantRolePermissions(role),
    onSuccess: () => {
      invalidate()
      setError(null)
    },
    onError: (err: Error) => setError(err.message || t('rbac.saveFailed')),
  })

  if (isLoading || !data) return <LoadingSpinner size="lg" />

  const roles = data.roles
  const serverPerms = (role: string) =>
    new Set(roles.find((r) => r.name === role)?.permissions ?? [])
  const isDirty = (role: string) => {
    const d = draft[role]
    if (!d) return false
    const s = serverPerms(role)
    return d.size !== s.size || [...d].some((p) => !s.has(p))
  }

  const toggle = (role: string, permission: string) => {
    if (role === 'admin' && ADMIN_FLOOR.has(permission)) return
    setDraft((prev) => {
      const next = { ...prev, [role]: new Set(prev[role]) }
      if (next[role].has(permission)) next[role].delete(permission)
      else next[role].add(permission)
      return next
    })
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-500">
        {t('rbac.tenantSubtitle', {
          defaultValue:
            'Tailor what each role can do in YOUR organization. Roles without an override follow the platform defaults. Changes apply to users on their next action.',
        })}
      </p>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="sticky left-0 bg-gray-50 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                {t('rbac.permission', { defaultValue: 'Permission' })}
              </th>
              {roles.map((role) => (
                <th key={role.name} className="px-3 py-3 text-center text-xs font-semibold uppercase tracking-wide text-gray-500">
                  {role.name.replace('_', ' ')}
                  {role.overridden && (
                    <span className="block text-[10px] font-medium normal-case text-amber-600">
                      {t('rbac.overridden', { defaultValue: 'customized' })}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map(([group, permissions]) => (
              <>
                <tr key={`g-${group}`} className="bg-gray-100/70">
                  <td colSpan={roles.length + 1} className="sticky left-0 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-gray-500">
                    {group}
                  </td>
                </tr>
                {permissions.map((permission) => (
                  <tr key={permission} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="sticky left-0 bg-white px-4 py-2 font-mono text-xs text-gray-700">
                      {permission}
                    </td>
                    {roles.map((role) => {
                      const locked = role.name === 'admin' && ADMIN_FLOOR.has(permission)
                      return (
                        <td key={role.name} className="px-3 py-2 text-center">
                          <input
                            type="checkbox"
                            checked={draft[role.name]?.has(permission) ?? false}
                            disabled={locked}
                            onChange={() => toggle(role.name, permission)}
                            className={cn(
                              'h-4 w-4 rounded border-gray-300 text-primary-600',
                              locked ? 'cursor-not-allowed opacity-40' : 'cursor-pointer'
                            )}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-gray-200 bg-gray-50">
              <td className="sticky left-0 bg-gray-50 px-4 py-3 text-xs text-gray-400">
                {t('rbac.tenantFooterNote', { defaultValue: 'Overrides apply to this organization only' })}
              </td>
              {roles.map((role) => (
                <td key={role.name} className="px-3 py-3 text-center align-top">
                  <div className="flex flex-col items-center gap-1">
                    <button
                      className="rounded-lg bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-40"
                      disabled={!isDirty(role.name) || saveMutation.isPending}
                      onClick={() =>
                        saveMutation.mutate({
                          role: role.name,
                          permissions: [...(draft[role.name] ?? [])].sort(),
                        })
                      }
                    >
                      {savedRole === role.name
                        ? t('rbac.saved', { defaultValue: 'Saved ✓' })
                        : t('common.save')}
                    </button>
                    {role.overridden && (
                      <button
                        className="inline-flex items-center gap-1 text-[11px] text-amber-700 hover:underline"
                        disabled={resetMutation.isPending}
                        onClick={() => resetMutation.mutate(role.name)}
                      >
                        <ArrowUturnLeftIcon className="h-3 w-3" />
                        {t('rbac.resetToPlatform', { defaultValue: 'Use platform defaults' })}
                      </button>
                    )}
                  </div>
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
