// Super-admin editor for the platform role→permission matrix — the single
// source of truth for backend endpoint guards AND the permission list every
// user receives on login (/auth/me). Guardrails mirror the API: super_admin
// is immutable, and the admin role cannot lose 'admin'/'settings'.
// Direction B restyle: token matrix table, Checkbox primitive, toast on save.
import { Fragment, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowUturnLeftIcon,
  ExclamationCircleIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import { getRolePermissions, updateRolePermissions } from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { Button, Checkbox, useToast } from '@/components/ui'

const ADMIN_FLOOR = new Set(['admin', 'settings'])

// Group catalog keys for readability: nav keys have no dot, action/backend
// keys group by their prefix.
function groupKey(permission: string): string {
  if (!permission.includes('.')) return 'navigation'
  return permission.split('.')[0]
}

export default function RolePermissionsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [draft, setDraft] = useState<Record<string, Set<string>>>({})
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['role-permissions'],
    queryFn: getRolePermissions,
  })

  useEffect(() => {
    if (data) {
      setDraft(Object.fromEntries(data.roles.map((r) => [r.name, new Set(r.permissions)])))
    }
  }, [data])

  const groups = useMemo(() => {
    const out: Record<string, string[]> = {}
    for (const p of data?.catalog ?? []) {
      const g = groupKey(p)
      ;(out[g] ??= []).push(p)
    }
    return Object.entries(out).sort(([a], [b]) =>
      a === 'navigation' ? -1 : b === 'navigation' ? 1 : a.localeCompare(b)
    )
  }, [data])

  const saveMutation = useMutation({
    mutationFn: ({ role, permissions }: { role: string; permissions: string[] }) =>
      updateRolePermissions(role, permissions),
    onSuccess: (_res, { role }) => {
      queryClient.invalidateQueries({ queryKey: ['role-permissions'] })
      setError(null)
      toast({
        text: t('rbac.savedToast', {
          defaultValue: '{{role}} permissions saved',
          role: role.replace('_', ' '),
        }),
      })
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
    if (role === 'super_admin') return
    if (role === 'admin' && ADMIN_FLOOR.has(permission)) return
    setDraft((prev) => {
      const next = { ...prev, [role]: new Set(prev[role]) }
      if (next[role].has(permission)) next[role].delete(permission)
      else next[role].add(permission)
      return next
    })
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div>
        <h1 className="row" style={{ gap: 8, fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
          <ShieldCheckIcon style={{ width: 26, height: 26, color: 'var(--p)', flexShrink: 0 }} aria-hidden />
          {t('rbac.title', { defaultValue: 'Roles & Permissions' })}
        </h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
          {t('rbac.subtitle', {
            defaultValue:
              'Platform-wide matrix driving both API access and what each role sees in the app. Changes take effect within 1 minute.',
          })}
        </p>
      </div>

      {error && (
        <div className="banner banner-da">
          <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{error}</span>
        </div>
      )}

      <div className="tbl-w">
        <table className="tbl" style={{ minWidth: 640 }}>
          <thead>
            <tr>
              <th style={{ position: 'sticky', left: 0, zIndex: 2, background: 'var(--s3)' }}>
                {t('rbac.permission', { defaultValue: 'Permission' })}
              </th>
              {roles.map((role) => (
                <th key={role.name} style={{ textAlign: 'center' }}>
                  {role.name.replace('_', ' ')}
                  {role.name === 'super_admin' && (
                    <span
                      className="faint"
                      style={{ display: 'block', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}
                    >
                      {t('rbac.immutable', { defaultValue: 'immutable' })}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map(([group, permissions]) => (
              <Fragment key={group}>
                <tr>
                  <td
                    colSpan={roles.length + 1}
                    className="sec-t"
                    style={{
                      position: 'sticky',
                      left: 0,
                      padding: '6px 14px',
                      background: 'var(--s2)',
                    }}
                  >
                    {group}
                  </td>
                </tr>
                {permissions.map((permission) => (
                  <tr key={permission}>
                    <td
                      className="mono"
                      style={{
                        position: 'sticky',
                        left: 0,
                        zIndex: 1,
                        background: 'var(--s)',
                        fontSize: 'var(--fs-xs)',
                        color: 'var(--m)',
                      }}
                    >
                      {permission}
                    </td>
                    {roles.map((role) => {
                      const locked =
                        role.name === 'super_admin' ||
                        (role.name === 'admin' && ADMIN_FLOOR.has(permission))
                      return (
                        <td key={role.name} style={{ textAlign: 'center' }}>
                          <Checkbox
                            checked={draft[role.name]?.has(permission) ?? false}
                            disabled={locked}
                            onChange={() => toggle(role.name, permission)}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
          <tfoot>
            <tr style={{ background: 'var(--s3)' }}>
              <td
                className="faint"
                style={{
                  position: 'sticky',
                  left: 0,
                  background: 'var(--s3)',
                  fontSize: 'var(--fs-xs)',
                  borderTop: '1px solid var(--b)',
                }}
              >
                {t('rbac.footerNote', { defaultValue: 'super_admin always passes all checks' })}
              </td>
              {roles.map((role) => (
                <td key={role.name} style={{ textAlign: 'center', borderTop: '1px solid var(--b)' }}>
                  {role.name !== 'super_admin' && (
                    <div className="col" style={{ alignItems: 'center', gap: 4 }}>
                      <Button
                        variant="primary"
                        size="sm"
                        disabled={!isDirty(role.name) || saveMutation.isPending}
                        onClick={() =>
                          saveMutation.mutate({
                            role: role.name,
                            permissions: [...(draft[role.name] ?? [])].sort(),
                          })
                        }
                      >
                        {t('common.save')}
                      </Button>
                      {isDirty(role.name) && (
                        <Button
                          variant="ghost"
                          size="sm"
                          icon={ArrowUturnLeftIcon}
                          onClick={() =>
                            setDraft((prev) => ({ ...prev, [role.name]: serverPerms(role.name) }))
                          }
                        >
                          {t('rbac.reset', { defaultValue: 'Reset' })}
                        </Button>
                      )}
                    </div>
                  )}
                </td>
              ))}
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  )
}
