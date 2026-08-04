/* Milestone master-data panel — Direction B restyle. Chip filters + seed/add
   actions, Table primitive with dependency Tags and status Pills, create/edit
   in a Drawer, delete via ConfirmDialog (was window.confirm), seed result as
   a toast (was alert). Queries, mutations and payload shapes unchanged. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowPathIcon,
  FlagIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import {
  Button,
  Chip,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Switch,
  Table,
  Tag,
  useToast,
} from '@/components/ui'
import type { TableColumn } from '@/components/ui'
import { formatCurrency } from '@/lib/utils'
import type { MilestoneMasterData, MilestoneMasterDataCreate, MilestoneMasterDataUpdate } from '@/types/admin'

interface FormData {
  milestone_code: string
  name: string
  description: string
  baseline_days_from_start: string
  dependencies: string
  credit_at_risk: string
  is_active: boolean
}

const emptyFormData: FormData = {
  milestone_code: '',
  name: '',
  description: '',
  baseline_days_from_start: '',
  dependencies: '',
  credit_at_risk: '',
  is_active: true,
}

const FORM_ID = 'milestone-config-form'

export default function MilestoneConfigPanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<MilestoneMasterData | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<MilestoneMasterData | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined)

  const { data, isLoading, error } = useQuery({
    queryKey: ['milestone-master-data', activeFilter],
    queryFn: () => api.getMilestoneMasterData({ active_only: activeFilter }),
  })

  const createMutation = useMutation({
    mutationFn: (data: MilestoneMasterDataCreate) => api.createMilestoneMasterData(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: MilestoneMasterDataUpdate }) =>
      api.updateMilestoneMasterData(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteMilestoneMasterData(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
    },
  })

  const seedMutation = useMutation({
    mutationFn: () => api.seedMilestoneMasterData(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['milestone-master-data'] })
      toast({ text: t('masterdata.milestones.seedResult', { seeded: result.seeded, skipped: result.skipped }) })
    },
  })

  const openCreateModal = () => {
    setEditingItem(null)
    setFormData(emptyFormData)
    setIsModalOpen(true)
  }

  const openEditModal = (item: MilestoneMasterData) => {
    setEditingItem(item)
    setFormData({
      milestone_code: item.milestone_code,
      name: item.name,
      description: item.description || '',
      baseline_days_from_start: String(item.baseline_days_from_start),
      dependencies: item.dependencies.join(', '),
      credit_at_risk: item.credit_at_risk ? String(item.credit_at_risk) : '',
      is_active: item.is_active,
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingItem(null)
    setFormData(emptyFormData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload = {
      milestone_code: formData.milestone_code,
      name: formData.name,
      description: formData.description || undefined,
      baseline_days_from_start: parseInt(formData.baseline_days_from_start),
      dependencies: formData.dependencies
        ? formData.dependencies.split(',').map((s) => s.trim()).filter(Boolean)
        : [],
      credit_at_risk: formData.credit_at_risk ? parseFloat(formData.credit_at_risk) : undefined,
      is_active: formData.is_active,
    }

    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  const columns: TableColumn<MilestoneMasterData>[] = [
    {
      key: 'milestone_code',
      header: t('masterdata.milestones.code'),
      width: 120,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.milestone_code,
      render: (i) => (
        <span className="mono" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500 }}>{i.milestone_code}</span>
      ),
    },
    {
      key: 'name',
      header: t('masterdata.name'),
      sortable: true,
      sortValue: (i) => i.name,
      render: (i) => (
        <span style={{ minWidth: 0, display: 'block' }}>
          <span className="trunc" style={{ display: 'block' }}>{i.name}</span>
          {i.description && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)', maxWidth: 320 }}>
              {i.description}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'baseline_days_from_start',
      header: t('masterdata.milestones.daysFromStart'),
      width: 120,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.baseline_days_from_start,
      render: (i) => (
        <span className="num">{t('masterdata.milestones.daysCount', { count: i.baseline_days_from_start })}</span>
      ),
    },
    {
      key: 'dependencies',
      header: t('masterdata.milestones.dependencies'),
      render: (i) =>
        i.dependencies.length > 0 ? (
          <span className="row" style={{ gap: 4, flexWrap: 'wrap' }}>
            {i.dependencies.map((dep) => (
              <Tag key={dep}>{dep}</Tag>
            ))}
          </span>
        ) : (
          <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('masterdata.milestones.none')}</span>
        ),
    },
    {
      key: 'credit_at_risk',
      header: t('masterdata.milestones.creditAtRisk'),
      width: 120,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.credit_at_risk,
      render: (i) => (
        <span className="num">{i.credit_at_risk ? formatCurrency(i.credit_at_risk) : '-'}</span>
      ),
    },
    {
      key: 'status',
      header: t('common.status'),
      width: 104,
      sortable: true,
      sortValue: (i) => (i.is_active ? 0 : 1),
      render: (i) => (
        <Pill tone={i.is_active ? 'ok' : 'da'}>
          {i.is_active ? t('status.active') : t('status.inactive')}
        </Pill>
      ),
    },
    {
      key: 'actions',
      header: t('common.actions'),
      width: 80,
      align: 'right',
      render: (i) => (
        <span className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
          <IconButton
            icon={PencilSquareIcon}
            size="sm"
            label={t('common.edit', { defaultValue: 'Edit' })}
            onClick={() => openEditModal(i)}
          />
          <IconButton
            icon={TrashIcon}
            size="sm"
            label={t('common.delete')}
            disabled={deleteMutation.isPending}
            onClick={() => setDeleteTarget(i)}
          />
        </span>
      ),
    },
  ]

  return (
    <div className="col" style={{ gap: 14 }}>
      {/* Actions & Filters */}
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{t('masterdata.filter')}</span>
        <Chip on={activeFilter === undefined} onClick={() => setActiveFilter(undefined)}>
          {t('masterdata.all')}
        </Chip>
        <Chip on={activeFilter === true} onClick={() => setActiveFilter(true)}>
          {t('status.active')}
        </Chip>
        <Chip on={activeFilter === false} onClick={() => setActiveFilter(false)}>
          {t('status.inactive')}
        </Chip>
        <span className="grow" />
        <Button
          variant="secondary"
          icon={ArrowPathIcon}
          disabled={seedMutation.isPending}
          onClick={() => seedMutation.mutate()}
        >
          {t('masterdata.seedFromStubs')}
        </Button>
        <Button variant="primary" icon={PlusIcon} onClick={openCreateModal}>
          {t('masterdata.milestones.addMilestone')}
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <div className="banner banner-da">
          <span>{t('masterdata.milestones.loadError')}</span>
        </div>
      )}

      {/* Table */}
      {isLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 256 }}>
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <Table
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(i) => i.id}
          minWidth={760}
          empty={<EmptyState icon={FlagIcon} title={t('masterdata.milestones.empty')} />}
        />
      )}

      {/* Create / edit drawer */}
      <Drawer
        open={isModalOpen}
        title={editingItem ? t('masterdata.milestones.editTitle') : t('masterdata.milestones.createTitle')}
        sub={editingItem?.milestone_code}
        onClose={closeModal}
        footer={
          <>
            <Button variant="ghost" onClick={closeModal}>
              {t('common.cancel')}
            </Button>
            <span className="grow" />
            <Button variant="primary" type="submit" form={FORM_ID} disabled={isSaving}>
              {editingItem ? t('masterdata.update') : t('masterdata.create')}
            </Button>
          </>
        }
      >
        <form id={FORM_ID} onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label={`${t('masterdata.milestones.milestoneCode')} *`}
              type="text"
              value={formData.milestone_code}
              onChange={(e) => setFormData({ ...formData, milestone_code: e.target.value })}
              placeholder={t('masterdata.milestones.codePlaceholder')}
              required
            />
            <Field
              label={`${t('masterdata.milestones.daysFromStart')} *`}
              type="number"
              min="0"
              value={formData.baseline_days_from_start}
              onChange={(e) => setFormData({ ...formData, baseline_days_from_start: e.target.value })}
              placeholder={t('masterdata.milestones.daysPlaceholder')}
              required
            />
          </div>

          <Field
            label={`${t('masterdata.name')} *`}
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder={t('masterdata.milestones.namePlaceholder')}
            required
          />

          <div>
            <label className="lbl">{t('masterdata.description')}</label>
            <div className="inp" style={{ height: 'auto', padding: 10, alignItems: 'flex-start' }}>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder={t('masterdata.descriptionPlaceholder')}
                rows={2}
                style={{ resize: 'vertical' }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field
              label={t('masterdata.milestones.dependencies')}
              type="text"
              value={formData.dependencies}
              onChange={(e) => setFormData({ ...formData, dependencies: e.target.value })}
              placeholder={t('masterdata.milestones.dependenciesPlaceholder')}
              hint={t('masterdata.milestones.dependenciesHint')}
            />
            <Field
              label={t('masterdata.milestones.creditAtRisk')}
              type="number"
              step="0.01"
              min="0"
              value={formData.credit_at_risk}
              onChange={(e) => setFormData({ ...formData, credit_at_risk: e.target.value })}
              placeholder={t('masterdata.milestones.creditPlaceholder')}
            />
          </div>

          <Switch
            checked={formData.is_active}
            onChange={(checked) => setFormData({ ...formData, is_active: checked })}
            label={t('status.active')}
          />
        </form>
      </Drawer>

      {/* Delete confirmation — replaces the old window.confirm */}
      <ConfirmDialog
        open={deleteTarget != null}
        title={t('masterdata.confirmDelete', { name: deleteTarget?.name ?? '' })}
        confirmLabel={t('common.delete')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id)
          setDeleteTarget(null)
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
