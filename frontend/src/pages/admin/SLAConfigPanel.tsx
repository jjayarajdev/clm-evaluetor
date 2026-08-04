/* SLA master-data panel — Direction B restyle. Chip filters + seed/add
   actions, Table primitive with status Pills, create/edit in a Drawer,
   delete via ConfirmDialog (was window.confirm), seed result as a toast
   (was alert). Queries, mutations and payload shapes unchanged. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArrowPathIcon,
  CircleStackIcon,
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
  useToast,
} from '@/components/ui'
import type { TableColumn } from '@/components/ui'
import type { SLAMasterData, SLAMasterDataCreate, SLAMasterDataUpdate } from '@/types/admin'

interface FormData {
  reference_code: string
  name: string
  description: string
  target_value: string
  minimum_value: string
  typical_performance: string
  volatility: string
  category: string
  service_tower: string
  is_active: boolean
}

const emptyFormData: FormData = {
  reference_code: '',
  name: '',
  description: '',
  target_value: '',
  minimum_value: '',
  typical_performance: '',
  volatility: '',
  category: '',
  service_tower: '',
  is_active: true,
}

const FORM_ID = 'sla-config-form'

export default function SLAConfigPanel() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<SLAMasterData | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<SLAMasterData | null>(null)
  const [formData, setFormData] = useState<FormData>(emptyFormData)
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(undefined)

  const { data, isLoading, error } = useQuery({
    queryKey: ['sla-master-data', activeFilter],
    queryFn: () => api.getSLAMasterData({ active_only: activeFilter }),
  })

  const createMutation = useMutation({
    mutationFn: (data: SLAMasterDataCreate) => api.createSLAMasterData(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SLAMasterDataUpdate }) =>
      api.updateSLAMasterData(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.deleteSLAMasterData(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
    },
  })

  const seedMutation = useMutation({
    mutationFn: () => api.seedSLAMasterData(),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['sla-master-data'] })
      toast({ text: t('masterdata.sla.seedResult', { seeded: result.seeded, skipped: result.skipped }) })
    },
  })

  const openCreateModal = () => {
    setEditingItem(null)
    setFormData(emptyFormData)
    setIsModalOpen(true)
  }

  const openEditModal = (item: SLAMasterData) => {
    setEditingItem(item)
    setFormData({
      reference_code: item.reference_code,
      name: item.name,
      description: item.description || '',
      target_value: String(item.target_value),
      minimum_value: item.minimum_value ? String(item.minimum_value) : '',
      typical_performance: item.typical_performance ? String(item.typical_performance) : '',
      volatility: item.volatility ? String(item.volatility) : '',
      category: item.category || '',
      service_tower: item.service_tower || '',
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
      reference_code: formData.reference_code,
      name: formData.name,
      description: formData.description || undefined,
      target_value: parseFloat(formData.target_value),
      minimum_value: formData.minimum_value ? parseFloat(formData.minimum_value) : undefined,
      typical_performance: formData.typical_performance ? parseFloat(formData.typical_performance) : undefined,
      volatility: formData.volatility ? parseFloat(formData.volatility) : undefined,
      category: formData.category || undefined,
      service_tower: formData.service_tower || undefined,
      is_active: formData.is_active,
    }

    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, data: payload })
    } else {
      createMutation.mutate(payload)
    }
  }

  const formatPercentage = (value: number | null) => {
    if (value === null) return '-'
    return `${(value * 100).toFixed(2)}%`
  }

  const isSaving = createMutation.isPending || updateMutation.isPending

  const columns: TableColumn<SLAMasterData>[] = [
    {
      key: 'reference_code',
      header: t('masterdata.sla.reference'),
      width: 130,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.reference_code,
      render: (i) => (
        <span className="mono" style={{ fontSize: 'var(--fs-sm)', fontWeight: 500 }}>{i.reference_code}</span>
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
          {i.service_tower && (
            <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)' }}>
              {i.service_tower}
            </span>
          )}
        </span>
      ),
    },
    {
      key: 'target_value',
      header: t('masterdata.sla.target'),
      width: 100,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.target_value,
      render: (i) => <span className="num">{formatPercentage(i.target_value)}</span>,
    },
    {
      key: 'minimum_value',
      header: t('masterdata.sla.minimum'),
      width: 100,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.minimum_value,
      render: (i) => <span className="num muted">{formatPercentage(i.minimum_value)}</span>,
    },
    {
      key: 'category',
      header: t('masterdata.sla.category'),
      width: 130,
      nowrap: true,
      sortable: true,
      sortValue: (i) => i.category,
      render: (i) => <span className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{i.category || '-'}</span>,
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
          {t('masterdata.sla.addSlaConfig')}
        </Button>
      </div>

      {/* Error state */}
      {error && (
        <div className="banner banner-da">
          <span>{t('masterdata.sla.loadError')}</span>
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
          empty={<EmptyState icon={CircleStackIcon} title={t('masterdata.sla.empty')} />}
        />
      )}

      {/* Create / edit drawer */}
      <Drawer
        open={isModalOpen}
        title={editingItem ? t('masterdata.sla.editTitle') : t('masterdata.sla.createTitle')}
        sub={editingItem?.reference_code}
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
              label={`${t('masterdata.sla.referenceCode')} *`}
              type="text"
              value={formData.reference_code}
              onChange={(e) => setFormData({ ...formData, reference_code: e.target.value })}
              placeholder={t('masterdata.sla.referencePlaceholder')}
              required
            />
            <Field
              label={`${t('masterdata.sla.targetValue')} *`}
              type="number"
              step="0.0001"
              value={formData.target_value}
              onChange={(e) => setFormData({ ...formData, target_value: e.target.value })}
              placeholder={t('masterdata.sla.targetPlaceholder')}
              required
            />
          </div>

          <Field
            label={`${t('masterdata.name')} *`}
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder={t('masterdata.sla.namePlaceholder')}
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
              label={t('masterdata.sla.minimumValue')}
              type="number"
              step="0.0001"
              value={formData.minimum_value}
              onChange={(e) => setFormData({ ...formData, minimum_value: e.target.value })}
              placeholder={t('masterdata.sla.minimumPlaceholder')}
            />
            <Field
              label={t('masterdata.sla.typicalPerformance')}
              type="number"
              step="0.0001"
              value={formData.typical_performance}
              onChange={(e) => setFormData({ ...formData, typical_performance: e.target.value })}
              placeholder={t('masterdata.sla.typicalPlaceholder')}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field
              label={t('masterdata.sla.category')}
              type="text"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
              placeholder={t('masterdata.sla.categoryPlaceholder')}
            />
            <Field
              label={t('masterdata.sla.serviceTower')}
              type="text"
              value={formData.service_tower}
              onChange={(e) => setFormData({ ...formData, service_tower: e.target.value })}
              placeholder={t('masterdata.sla.serviceTowerPlaceholder')}
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
