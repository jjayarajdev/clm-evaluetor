/* Business Units admin — Direction B redesign.
   Header + super-admin tenant Select → hierarchy hint banner → indented tree
   rows (mono codes, profile Tags, inactive Pills, hover actions) in a tbl-w →
   create/edit in a Drawer → deactivation via ConfirmDialog stating exactly
   what is and is not affected. Queries, mutations (create/update/deactivate,
   profile assignment), tenant scoping and i18n are unchanged from the
   pre-redesign page. */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowTurnDownRightIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  PencilSquareIcon,
  PlusIcon,
  RectangleGroupIcon,
  SwatchIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Button,
  Checkbox,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Tag,
  Tooltip,
  useToast,
} from '@/components/ui'
import type { BusinessUnitTree, BusinessUnitCreate, BusinessUnitUpdate } from '@/types/business-unit'

interface FormData {
  name: string
  code: string
  description: string
  parent_id: string
  industry_profile_id: string
  is_active: boolean
}

const emptyFormData: FormData = {
  name: '',
  code: '',
  description: '',
  parent_id: '',
  industry_profile_id: '',
  is_active: true,
}

/* One tree row — prototype UnitRow idiom: 48px row, indent by depth,
   turn-down arrow for children, mono code, hover-revealed actions. */
function UnitRow({
  node,
  depth,
  expandedNodes,
  toggleExpand,
  onEdit,
  onDelete,
  onAddChild,
}: {
  node: BusinessUnitTree
  depth: number
  expandedNodes: Set<string>
  toggleExpand: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (node: BusinessUnitTree) => void
  onAddChild: (parentId: string) => void
}) {
  const { t } = useTranslation()
  const hasChildren = node.children && node.children.length > 0
  const isExpanded = expandedNodes.has(node.id)

  return (
    <>
      <div
        className="row group"
        style={{
          gap: 10,
          minHeight: 48,
          paddingLeft: 10 + depth * 26,
          paddingRight: 12,
          borderBottom: '1px solid var(--b)',
        }}
      >
        {/* Expand / collapse */}
        <span style={{ width: 26, flexShrink: 0, visibility: hasChildren ? 'visible' : 'hidden' }}>
          <IconButton
            icon={isExpanded ? ChevronDownIcon : ChevronRightIcon}
            size="sm"
            label={isExpanded ? t('businessUnits.collapseAll') : t('businessUnits.expandAll')}
            onClick={() => hasChildren && toggleExpand(node.id)}
          />
        </span>

        {depth > 0 && (
          <ArrowTurnDownRightIcon
            style={{ width: 13, height: 13, flexShrink: 0, color: 'var(--f)' }}
            aria-hidden
          />
        )}
        <RectangleGroupIcon
          style={{
            width: 16,
            height: 16,
            flexShrink: 0,
            color: node.is_active ? 'var(--m)' : 'var(--f)',
          }}
          aria-hidden
        />

        {/* Name, mono code, description */}
        <span className="grow" style={{ minWidth: 0 }}>
          <span className="row" style={{ gap: 8, minWidth: 0 }}>
            <span
              className="trunc"
              style={{
                fontWeight: 500,
                fontSize: 'var(--fs-md)',
                color: node.is_active ? undefined : 'var(--f)',
                textDecoration: node.is_active ? undefined : 'line-through',
              }}
            >
              {node.name}
            </span>
            <span className="mono faint" style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}>
              {node.code}
            </span>
          </span>
          {node.description && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)', marginTop: 1 }}>
              {node.description}
            </span>
          )}
        </span>

        {/* Effective industry profile — own assignment vs inherited */}
        {node.effective_profile_name && (
          node.industry_profile_id ? (
            <Tag icon={SwatchIcon}>{node.effective_profile_name}</Tag>
          ) : (
            <Tooltip label={t('businessUnits.inheritFromTenant')}>
              <span className="faint row" style={{ gap: 4, fontSize: 'var(--fs-sm)', cursor: 'help' }}>
                <SwatchIcon style={{ width: 12, height: 12 }} aria-hidden />
                {node.effective_profile_name} {t('businessUnits.inherited')}
              </span>
            </Tooltip>
          )
        )}

        {hasChildren && (
          <span className="faint num" style={{ fontSize: 'var(--fs-sm)', flexShrink: 0 }}>
            {t('businessUnits.childCount', { count: node.children.length, defaultValue: '{{count}} sub-units' })}
          </span>
        )}

        {!node.is_active && <Pill tone="da">{t('status.inactive')}</Pill>}

        {/* Hover-revealed actions */}
        <span
          className="row opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity"
          style={{ gap: 2, flexShrink: 0 }}
        >
          <IconButton
            icon={PlusIcon}
            size="sm"
            label={t('businessUnits.addChildUnit')}
            onClick={() => onAddChild(node.id)}
          />
          <IconButton
            icon={PencilSquareIcon}
            size="sm"
            label={t('common.edit')}
            onClick={() => onEdit(node.id)}
          />
          <IconButton
            icon={TrashIcon}
            size="sm"
            label={t('common.delete')}
            onClick={() => onDelete(node)}
          />
        </span>
      </div>

      {hasChildren && isExpanded &&
        node.children.map((child) => (
          <UnitRow
            key={child.id}
            node={child}
            depth={depth + 1}
            expandedNodes={expandedNodes}
            toggleExpand={toggleExpand}
            onEdit={onEdit}
            onDelete={onDelete}
            onAddChild={onAddChild}
          />
        ))}
    </>
  )
}

export default function BusinessUnitsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { isSuperAdmin } = useAuth()
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
  const [selectedTenantId, setSelectedTenantId] = useState<string>('')
  const [formError, setFormError] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Fetch tenants for super admin
  const { data: tenants } = useQuery({
    queryKey: ['tenants'],
    queryFn: () => api.getTenants(true),
    enabled: isSuperAdmin,
  })

  // Fetch industry profiles for the dropdown
  const { data: profiles } = useQuery({
    queryKey: ['industry-profiles'],
    queryFn: () => api.getIndustryProfiles(),
  })

  // Auto-select first tenant for super admin
  useEffect(() => {
    if (isSuperAdmin && tenants && tenants.length > 0 && !selectedTenantId) {
      setSelectedTenantId(tenants[0].id)
    }
  }, [isSuperAdmin, tenants, selectedTenantId])

  // Get effective tenant ID (for super admin, use selected; otherwise use user's tenant)
  const effectiveTenantId = isSuperAdmin ? selectedTenantId : undefined

  // Fetch tree data
  const { data: treeData, isLoading, error } = useQuery({
    queryKey: ['business-units-tree', effectiveTenantId],
    queryFn: () => api.getBusinessUnitsTree(effectiveTenantId),
    enabled: !isSuperAdmin || !!selectedTenantId,
  })

  // Fetch flat list for parent dropdown
  const { data: listData } = useQuery({
    queryKey: ['business-units-list', effectiveTenantId],
    queryFn: () => api.getBusinessUnits({ page_size: 100 }, effectiveTenantId),
    enabled: !isSuperAdmin || !!selectedTenantId,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['business-units-tree', effectiveTenantId] })
    queryClient.invalidateQueries({ queryKey: ['business-units-list', effectiveTenantId] })
  }

  const createMutation = useMutation({
    mutationFn: (data: BusinessUnitCreate) => api.createBusinessUnit(data, effectiveTenantId),
    onSuccess: (_res, variables) => {
      invalidate()
      closeDrawer()
      toast({ text: t('businessUnits.createdToast', { name: variables.name, defaultValue: '{{name}} created' }) })
    },
    onError: (err: Error) => {
      setFormError(err.message || t('businessUnits.saveFailed'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: BusinessUnitUpdate }) =>
      api.updateBusinessUnit(id, data, effectiveTenantId),
    onSuccess: (_res, variables) => {
      invalidate()
      closeDrawer()
      toast({ text: t('businessUnits.updatedToast', { name: variables.data.name ?? '', defaultValue: '{{name}} updated' }) })
    },
    onError: (err: Error) => {
      setFormError(err.message || t('businessUnits.saveFailed'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteBusinessUnit(id, effectiveTenantId),
    onSuccess: () => {
      invalidate()
      const name = deleteTarget?.name ?? ''
      setDeleteTarget(null)
      setActionError(null)
      toast({ text: t('businessUnits.deactivatedToast', { name, defaultValue: '{{name}} deactivated' }) })
    },
    onError: (err: Error) => {
      setDeleteTarget(null)
      setActionError(err.message || t('businessUnits.saveFailed'))
    },
  })

  const profileMutation = useMutation({
    mutationFn: ({ buId, profileId }: { buId: string; profileId: string | null }) =>
      api.assignBuProfile(buId, profileId, effectiveTenantId),
    onSuccess: invalidate,
  })

  const toggleExpand = (id: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const expandAll = () => {
    const allIds = new Set<string>()
    const collectIds = (nodes: BusinessUnitTree[]) => {
      nodes.forEach((node) => {
        allIds.add(node.id)
        if (node.children) collectIds(node.children)
      })
    }
    if (treeData) collectIds(treeData)
    setExpandedNodes(allIds)
  }

  const collapseAll = () => {
    setExpandedNodes(new Set())
  }

  const countUnits = (nodes: BusinessUnitTree[]): number =>
    nodes.reduce((sum, n) => sum + 1 + (n.children ? countUnits(n.children) : 0), 0)

  const openCreateDrawer = (parentId?: string) => {
    setEditingId(null)
    setFormError(null)
    setFormData({
      ...emptyFormData,
      parent_id: parentId || '',
    })
    setIsDrawerOpen(true)
  }

  const openEditDrawer = async (id: string) => {
    try {
      const bu = await api.getBusinessUnit(id, effectiveTenantId)
      setEditingId(id)
      setFormError(null)
      setFormData({
        name: bu.name,
        code: bu.code,
        description: bu.description || '',
        parent_id: bu.parent_id || '',
        industry_profile_id: bu.industry_profile_id || '',
        is_active: bu.is_active,
      })
      setIsDrawerOpen(true)
    } catch (err) {
      console.error('Failed to fetch business unit:', err)
    }
  }

  const closeDrawer = () => {
    setIsDrawerOpen(false)
    setEditingId(null)
    setFormData(emptyFormData)
    setFormError(null)
  }

  const handleSubmit = () => {
    const submitData = {
      name: formData.name,
      code: formData.code,
      description: formData.description || undefined,
      parent_id: formData.parent_id || undefined,
      industry_profile_id: formData.industry_profile_id || undefined,
    }

    if (editingId) {
      updateMutation.mutate({
        id: editingId,
        data: {
          ...submitData,
          is_active: formData.is_active,
        },
      })
      // If profile changed, also call the profile assignment endpoint
      if (formData.industry_profile_id !== '') {
        profileMutation.mutate({
          buId: editingId,
          profileId: formData.industry_profile_id || null,
        })
      }
    } else {
      createMutation.mutate(submitData)
    }
  }

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="banner banner-da">
        <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>{t('businessUnits.loadFailed')}</span>
      </div>
    )
  }

  const isSaving = createMutation.isPending || updateMutation.isPending
  const totalUnits = treeData ? countUnits(treeData) : 0

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('nav.businessUnits')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('businessUnits.subtitle')}
          </p>
        </div>
        <Button
          variant="primary"
          icon={PlusIcon}
          onClick={() => openCreateDrawer()}
          disabled={isSuperAdmin && !selectedTenantId}
        >
          {t('businessUnits.addBusinessUnit')}
        </Button>
      </div>

      {/* Tenant selector for super admin */}
      {isSuperAdmin && (
        <Select
          label={t('businessUnits.selectTenant')}
          value={selectedTenantId}
          onChange={(e) => setSelectedTenantId(e.target.value)}
          containerStyle={{ maxWidth: 320 }}
          options={[
            { value: '', label: t('businessUnits.selectTenantPlaceholder') },
            ...(tenants ?? []).map((tenant) => ({ value: tenant.id, label: tenant.name })),
          ]}
        />
      )}

      {/* How the hierarchy behaves */}
      <div className="banner banner-in">
        <InformationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
        <span>
          {t('businessUnits.hierarchyHint', {
            defaultValue:
              'Units are hierarchical and tenant-created. Contracts inherit the uploader’s unit; a unit head sees their whole subtree, and users with no unit see everything.',
          })}
        </span>
      </div>

      {actionError && (
        <div className="banner banner-da">
          <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span className="grow">{actionError}</span>
          <IconButton icon={XMarkIcon} size="sm" label={t('common.cancel')} onClick={() => setActionError(null)} />
        </div>
      )}

      {/* Tree controls */}
      <div className="row" style={{ gap: 6 }}>
        <span className="faint" style={{ fontSize: 'var(--fs-md)' }}>
          {t('businessUnits.unitCount', { count: totalUnits, defaultValue: '{{count}} units' })}
        </span>
        <span className="grow" />
        <Button variant="ghost" size="sm" onClick={expandAll}>
          {t('businessUnits.expandAll')}
        </Button>
        <Button variant="ghost" size="sm" onClick={collapseAll}>
          {t('businessUnits.collapseAll')}
        </Button>
      </div>

      {/* Hierarchy */}
      {!treeData || treeData.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={RectangleGroupIcon}
            title={t('businessUnits.noUnits')}
            body={t('businessUnits.noUnitsHint')}
            action={
              <Button
                variant="primary"
                size="sm"
                icon={PlusIcon}
                onClick={() => openCreateDrawer()}
                disabled={isSuperAdmin && !selectedTenantId}
              >
                {t('businessUnits.addBusinessUnit')}
              </Button>
            }
          />
        </div>
      ) : (
        <div className="tbl-w">
          {treeData.map((node) => (
            <UnitRow
              key={node.id}
              node={node}
              depth={0}
              expandedNodes={expandedNodes}
              toggleExpand={toggleExpand}
              onEdit={openEditDrawer}
              onDelete={(n) => setDeleteTarget({ id: n.id, name: n.name })}
              onAddChild={openCreateDrawer}
            />
          ))}
        </div>
      )}

      {/* Deactivation — states exactly what is and is not affected */}
      <ConfirmDialog
        open={!!deleteTarget}
        tone="warn"
        title={t('businessUnits.deactivatePrompt', {
          name: deleteTarget?.name ?? '',
          defaultValue: 'Deactivate {{name}}?',
        })}
        body={t('businessUnits.confirmDeactivate')}
        affected={[
          t('businessUnits.deactivateAffectsUnit', {
            defaultValue: 'The unit is marked inactive and can no longer be assigned to users or contracts',
          }),
          t('businessUnits.deactivateAffectsUsers', {
            defaultValue: 'Users assigned to it keep the assignment but the unit no longer scopes new work',
          }),
        ]}
        safe={[
          t('businessUnits.deactivateSafeData', {
            defaultValue: 'Existing contracts, sub-units and governance data — every reference stays intact',
          }),
          t('businessUnits.deactivateSafeReversible', {
            defaultValue: 'Anything permanently — reactivate the unit at any time from Edit',
          }),
        ]}
        confirmLabel={t('businessUnits.deactivate', { defaultValue: 'Deactivate' })}
        cancelLabel={t('common.cancel')}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Create / edit drawer */}
      <Drawer
        open={isDrawerOpen}
        title={editingId ? t('businessUnits.editUnit') : t('businessUnits.createUnit')}
        onClose={closeDrawer}
        width={440}
        footer={
          <>
            <span className="grow" />
            <Button variant="ghost" onClick={closeDrawer}>
              {t('common.cancel')}
            </Button>
            <Button
              variant="primary"
              disabled={!formData.name || !formData.code || isSaving}
              onClick={handleSubmit}
            >
              {isSaving
                ? t('businessUnits.saving')
                : editingId
                ? t('businessUnits.update')
                : t('businessUnits.create')}
            </Button>
          </>
        }
      >
        <div className="col" style={{ gap: 14 }}>
          <Field
            label={`${t('businessUnits.name')} *`}
            type="text"
            autoFocus
            required
            value={formData.name}
            placeholder={t('businessUnits.namePlaceholder')}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
          <Field
            label={`${t('businessUnits.code')} *`}
            type="text"
            required
            maxLength={20}
            className="mono"
            value={formData.code}
            placeholder={t('businessUnits.codePlaceholder')}
            hint={t('businessUnits.codeHint')}
            onChange={(e) => setFormData({ ...formData, code: e.target.value.toUpperCase() })}
          />
          <div>
            <label className="lbl">{t('businessUnits.description')}</label>
            <div className="inp" style={{ height: 'auto', padding: '8px 10px' }}>
              <textarea
                rows={2}
                style={{ resize: 'vertical' }}
                value={formData.description}
                placeholder={t('businessUnits.descriptionPlaceholder')}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>
          </div>
          <Select
            label={t('businessUnits.parentUnit')}
            value={formData.parent_id}
            onChange={(e) => setFormData({ ...formData, parent_id: e.target.value })}
            options={[
              { value: '', label: t('businessUnits.noneTopLevel') },
              ...(listData?.items ?? [])
                .filter((bu) => bu.id !== editingId)
                .map((bu) => ({ value: bu.id, label: `${bu.name} (${bu.code})` })),
            ]}
          />
          <Select
            label={t('businessUnits.industryProfile')}
            value={formData.industry_profile_id}
            onChange={(e) => setFormData({ ...formData, industry_profile_id: e.target.value })}
            hint={t('businessUnits.profileHint')}
            options={[
              { value: '', label: t('businessUnits.inheritFromTenant') },
              ...(profiles ?? []).map((profile: { id: string; name: string }) => ({
                value: profile.id,
                label: profile.name,
              })),
            ]}
          />
          {editingId && (
            <Checkbox
              checked={formData.is_active}
              onChange={(checked) => setFormData({ ...formData, is_active: checked })}
              label={t('status.active')}
            />
          )}
          {formError && (
            <div className="banner banner-da">
              <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{formError}</span>
            </div>
          )}
        </div>
      </Drawer>
    </div>
  )
}
