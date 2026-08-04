/* Per-tenant custom field schema editor — Direction B restyle.
   Header + tenant Select → entity-type Tabs → sortable field Table (type
   Pills, visibility toggle) → create/edit in a Drawer, archive/delete via
   ConfirmDialog (replacing window.confirm). Queries, mutations, the field
   name normalization and the tenant querystring are unchanged. */
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  PlusIcon,
  PencilSquareIcon,
  TrashIcon,
  ArchiveBoxIcon,
  EyeIcon,
  EyeSlashIcon,
  Bars3Icon,
  ExclamationCircleIcon,
  RectangleStackIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
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
  Table,
  Tabs,
} from '@/components/ui'
import type { PillTone, TableColumn } from '@/components/ui'
import type { Tenant, CustomField, CustomFieldCreate, CustomFieldUpdate, EntityType, FieldType } from '@/types'

const ENTITY_TYPES: { id: EntityType; label: string }[] = [
  { id: 'contract', label: 'Contract' },
  { id: 'obligation', label: 'Obligation' },
  { id: 'clause', label: 'Clause' },
  { id: 'client', label: 'Client' },
]

const FIELD_TYPES: { id: FieldType; label: string; description: string }[] = [
  { id: 'text', label: 'Text', description: 'Single line text input' },
  { id: 'number', label: 'Number', description: 'Numeric value' },
  { id: 'date', label: 'Date', description: 'Date picker' },
  { id: 'dropdown', label: 'Dropdown', description: 'Single selection from options' },
  { id: 'multi_select', label: 'Multi-Select', description: 'Multiple selections from options' },
  { id: 'checkbox', label: 'Checkbox', description: 'Boolean true/false' },
  { id: 'url', label: 'URL', description: 'Web address' },
  { id: 'email', label: 'Email', description: 'Email address' },
  { id: 'currency', label: 'Currency', description: 'Monetary value' },
]

/* Same hue families as the legacy badge colors, mapped onto Pill tones. */
const FIELD_TYPE_TONES: Record<FieldType, PillTone> = {
  text: 'n',
  number: 'in',
  date: 'p',
  dropdown: 'ok',
  multi_select: 'in',
  checkbox: 'wa',
  url: 'in',
  email: 'da',
  currency: 'ok',
}

interface FieldFormData {
  name: string
  label: string
  field_type: FieldType
  required: boolean
  options: string
  help_text: string
  extraction_hints: string
  extraction_examples: string
}

const emptyFormData: FieldFormData = {
  name: '',
  label: '',
  field_type: 'text',
  required: false,
  options: '',
  help_text: '',
  extraction_hints: '',
  extraction_examples: '',
}

const FORM_ID = 'custom-field-form'

/* Labeled multi-line control in the Field frame (SettingsPage textarea pattern). */
function TextareaField({
  label, value, onChange, rows, placeholder, required, hint, mono,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  rows: number
  placeholder?: string
  required?: boolean
  hint?: string
  mono?: boolean
}) {
  return (
    <div>
      <label className="lbl">{label}</label>
      <div className="inp" style={{ height: 'auto', alignItems: 'stretch' }}>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          rows={rows}
          placeholder={placeholder}
          required={required}
          className={mono ? 'mono' : undefined}
          style={{ resize: 'vertical', padding: '8px 0' }}
        />
      </div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export default function CustomFieldsPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const tenantId = searchParams.get('tenant') || ''

  const [selectedEntityType, setSelectedEntityType] = useState<EntityType>('contract')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingField, setEditingField] = useState<CustomField | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<CustomField | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<CustomField | null>(null)
  const [formData, setFormData] = useState<FieldFormData>(emptyFormData)

  const { data: tenants } = useQuery<Tenant[]>({
    queryKey: ['tenants-list'],
    queryFn: () => api.getTenants(false),
  })

  const { data: fields, isLoading, error } = useQuery({
    queryKey: ['custom-fields', tenantId, selectedEntityType],
    queryFn: () => api.getCustomFields(tenantId, selectedEntityType),
    enabled: !!tenantId,
  })

  const createMutation = useMutation({
    mutationFn: (data: CustomFieldCreate) => api.createCustomField(tenantId, selectedEntityType, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-fields', tenantId, selectedEntityType] })
      closeModal()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ fieldName, data }: { fieldName: string; data: CustomFieldUpdate }) =>
      api.updateCustomField(tenantId, selectedEntityType, fieldName, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-fields', tenantId, selectedEntityType] })
      closeModal()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (fieldName: string) => api.deleteCustomField(tenantId, selectedEntityType, fieldName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['custom-fields', tenantId, selectedEntityType] })
    },
  })

  // Set initial tenant from URL or first available
  useEffect(() => {
    if (!tenantId && tenants && tenants.length > 0) {
      setSearchParams({ tenant: tenants[0].id })
    }
  }, [tenants, tenantId, setSearchParams])

  const handleTenantChange = (newTenantId: string) => {
    setSearchParams({ tenant: newTenantId })
  }

  const openCreateModal = () => {
    setEditingField(null)
    setFormData(emptyFormData)
    setIsModalOpen(true)
  }

  const openEditModal = (field: CustomField) => {
    setEditingField(field)
    setFormData({
      name: field.name,
      label: field.label,
      field_type: field.field_type,
      required: field.required,
      options: field.options?.join('\n') || '',
      help_text: field.help_text || '',
      extraction_hints: field.extraction_hints || '',
      extraction_examples: field.extraction_examples?.join('\n') || '',
    })
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingField(null)
    setFormData(emptyFormData)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const optionsArray = formData.options
      .split('\n')
      .map((o) => o.trim())
      .filter((o) => o.length > 0)

    const examplesArray = formData.extraction_examples
      .split('\n')
      .map((e) => e.trim())
      .filter((e) => e.length > 0)

    if (editingField) {
      updateMutation.mutate({
        fieldName: editingField.name,
        data: {
          label: formData.label,
          required: formData.required,
          options: optionsArray.length > 0 ? optionsArray : undefined,
          help_text: formData.help_text || undefined,
          extraction_hints: formData.extraction_hints || undefined,
          extraction_examples: examplesArray.length > 0 ? examplesArray : undefined,
        },
      })
    } else {
      createMutation.mutate({
        name: formData.name.toLowerCase().replace(/[^a-z0-9_]/g, '_'),
        label: formData.label,
        field_type: formData.field_type,
        required: formData.required,
        options: optionsArray.length > 0 ? optionsArray : undefined,
        help_text: formData.help_text || undefined,
        extraction_hints: formData.extraction_hints || undefined,
        extraction_examples: examplesArray.length > 0 ? examplesArray : undefined,
      })
    }
  }

  const handleToggleVisibility = (field: CustomField) => {
    updateMutation.mutate({
      fieldName: field.name,
      data: { is_visible: !field.is_visible },
    })
  }

  const showOptionsField = formData.field_type === 'dropdown' || formData.field_type === 'multi_select'

  const selectedTenant = tenants?.find((t) => t.id === tenantId)
  const activeFields = fields?.filter((f) => !f.is_archived) ?? []
  const previewFields = fields
    ?.filter((f) => !f.is_archived && f.is_visible)
    .sort((a, b) => a.display_order - b.display_order) ?? []
  const isSaving = createMutation.isPending || updateMutation.isPending

  const columns: TableColumn<CustomField>[] = [
    {
      key: 'drag',
      header: '',
      width: 34,
      render: () => (
        <Bars3Icon
          className="cursor-grab"
          style={{ width: 15, height: 15, color: 'var(--f)' }}
          title={t('superadmin.customFields.dragToReorder')}
          aria-hidden
        />
      ),
    },
    {
      key: 'field',
      header: t('superadmin.customFields.field'),
      sortable: true,
      sortValue: (f) => f.label,
      render: (f) => (
        <span style={{ minWidth: 0, display: 'block' }}>
          <span className="trunc" style={{ display: 'block', fontWeight: 500 }}>{f.label}</span>
          <span className="faint mono trunc" style={{ display: 'block', fontSize: 'var(--fs-xs)' }}>
            {f.name}
          </span>
        </span>
      ),
    },
    {
      key: 'type',
      header: t('superadmin.customFields.type'),
      width: 130,
      sortable: true,
      sortValue: (f) => f.field_type,
      render: (f) => (
        <Pill tone={FIELD_TYPE_TONES[f.field_type]} dot={false}>
          {t(`superadmin.customFields.fieldTypes.${f.field_type}`, {
            defaultValue: f.field_type.replace('_', ' '),
          })}
        </Pill>
      ),
    },
    {
      key: 'required',
      header: t('superadmin.customFields.required'),
      width: 100,
      sortable: true,
      sortValue: (f) => (f.required ? 0 : 1),
      render: (f) => (
        <Pill tone={f.required ? 'wa' : 'n'} dot={false}>
          {f.required ? t('common.yes') : t('common.no')}
        </Pill>
      ),
    },
    {
      key: 'visible',
      header: t('superadmin.customFields.visible'),
      width: 90,
      sortable: true,
      sortValue: (f) => (f.is_visible ? 0 : 1),
      render: (f) => (
        <IconButton
          icon={f.is_visible ? EyeIcon : EyeSlashIcon}
          size="sm"
          active={f.is_visible}
          label={f.is_visible ? t('superadmin.customFields.visible') : t('superadmin.customFields.hidden')}
          onClick={() => handleToggleVisibility(f)}
        />
      ),
    },
    {
      key: 'actions',
      header: '',
      width: 110,
      align: 'right',
      render: (f) => (
        <span className="row" style={{ gap: 4, justifyContent: 'flex-end' }}>
          <IconButton
            icon={PencilSquareIcon}
            size="sm"
            label={t('superadmin.customFields.editField')}
            onClick={() => openEditModal(f)}
          />
          <IconButton
            icon={ArchiveBoxIcon}
            size="sm"
            label={t('superadmin.customFields.archiveField')}
            onClick={() => setArchiveTarget(f)}
          />
          <IconButton
            icon={TrashIcon}
            size="sm"
            label={t('superadmin.customFields.deleteField')}
            disabled={deleteMutation.isPending}
            onClick={() => setDeleteTarget(f)}
          />
        </span>
      ),
    },
  ]

  /* Disabled control mirroring the tenant-facing form — presentation only. */
  const renderPreviewControl = (field: CustomField) => {
    switch (field.field_type) {
      case 'text':
        return <Field type="text" placeholder={field.help_text || ''} disabled />
      case 'number':
        return <Field type="number" disabled />
      case 'date':
        return <Field type="date" disabled />
      case 'dropdown':
        return (
          <Select
            disabled
            options={[
              { value: '', label: t('superadmin.customFields.selectOptionPlaceholder', { label: field.label }) },
              ...(field.options?.map((opt) => ({ value: opt, label: opt })) ?? []),
            ]}
          />
        )
      case 'multi_select':
        return (
          <div className="inp" style={{ height: 'auto', alignItems: 'stretch' }}>
            <select multiple disabled style={{ padding: '6px 0' }}>
              {field.options?.map((opt) => (
                <option key={opt}>{opt}</option>
              ))}
            </select>
          </div>
        )
      case 'checkbox':
        return (
          <Checkbox
            disabled
            label={field.help_text || t('superadmin.customFields.enable')}
          />
        )
      case 'url':
        return <Field type="url" placeholder="https://..." disabled />
      case 'email':
        return <Field type="email" placeholder="email@example.com" disabled />
      case 'currency':
        return (
          <div className="inp">
            <span className="faint" style={{ fontSize: 'var(--fs-md)' }}>$</span>
            <input type="number" disabled />
          </div>
        )
    }
  }

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start', gap: 12, flexWrap: 'wrap' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
            {t('nav.customFields')}
          </h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
            {t('superadmin.customFields.subtitle')}
          </p>
        </div>
        {tenantId && (
          <Button variant="primary" icon={PlusIcon} onClick={openCreateModal}>
            {t('superadmin.customFields.addField')}
          </Button>
        )}
      </div>

      {/* Tenant selector */}
      <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
        <span className="lbl" style={{ marginBottom: 0 }}>{t('superadmin.tenant')}:</span>
        <Select
          value={tenantId}
          onChange={(e) => handleTenantChange(e.target.value)}
          containerStyle={{ width: 240 }}
          options={[
            { value: '', label: t('superadmin.users.selectTenant') },
            ...(tenants?.map((tenant) => ({ value: tenant.id, label: tenant.name })) ?? []),
          ]}
        />
        {selectedTenant && (
          <span className="faint mono" style={{ fontSize: 'var(--fs-sm)' }}>
            ({selectedTenant.slug})
          </span>
        )}
      </div>

      {!tenantId ? (
        <EmptyState
          icon={RectangleStackIcon}
          title={t('superadmin.customFields.selectTenantPrompt')}
        />
      ) : (
        <>
          {/* Entity type tabs */}
          <Tabs
            tabs={ENTITY_TYPES.map((entityType) => ({
              value: entityType.id,
              label: t(`superadmin.customFields.entityTypes.${entityType.id}`, { defaultValue: entityType.label }),
            }))}
            value={selectedEntityType}
            onChange={setSelectedEntityType}
          />

          {/* Error state */}
          {error && (
            <div className="banner banner-da">
              <ExclamationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{t('superadmin.customFields.loadError')}</span>
            </div>
          )}

          {/* Fields list */}
          {isLoading ? (
            <div className="row" style={{ justifyContent: 'center', height: 256 }}>
              <LoadingSpinner size="lg" />
            </div>
          ) : (
            <Table
              columns={columns}
              rows={activeFields}
              rowKey={(f) => f.name}
              minWidth={720}
              empty={
                <EmptyState
                  icon={RectangleStackIcon}
                  title={t('superadmin.customFields.noFields', {
                    entityType: t(`superadmin.customFields.entityTypes.${selectedEntityType}`, {
                      defaultValue: selectedEntityType,
                    }),
                  })}
                  action={
                    <Button variant="primary" size="sm" icon={PlusIcon} onClick={openCreateModal}>
                      {t('superadmin.customFields.addFirstField')}
                    </Button>
                  }
                />
              }
            />
          )}

          {/* Preview section */}
          {previewFields.length > 0 && (
            <div className="card card-p">
              <h3 style={{ fontSize: 'var(--fs-lg)', fontWeight: 600 }}>
                {t('superadmin.customFields.formPreview')}
              </h3>
              <p className="muted" style={{ marginTop: 2, marginBottom: 14, fontSize: 'var(--fs-sm)' }}>
                {t('superadmin.customFields.previewDesc')}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
                {previewFields.map((field) => (
                  <div key={field.name}>
                    <label className="lbl">
                      {field.label}
                      {field.required && <span style={{ color: 'var(--da)', marginLeft: 4 }}>*</span>}
                    </label>
                    {renderPreviewControl(field)}
                    {field.help_text && field.field_type !== 'checkbox' && (
                      <div className="hint">{field.help_text}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Create / edit field drawer */}
      <Drawer
        open={isModalOpen}
        title={editingField ? t('superadmin.customFields.editFieldTitle') : t('superadmin.customFields.createFieldTitle')}
        sub={editingField?.name}
        onClose={closeModal}
        footer={
          <>
            <Button variant="ghost" onClick={closeModal}>
              {t('common.cancel')}
            </Button>
            <span className="grow" />
            <Button variant="primary" type="submit" form={FORM_ID} disabled={isSaving}>
              {isSaving
                ? t('common.saving')
                : editingField
                  ? t('superadmin.update')
                  : t('superadmin.create')}
            </Button>
          </>
        }
      >
        <form id={FORM_ID} onSubmit={handleSubmit} className="col" style={{ gap: 14 }}>
          {!editingField && (
            <div className="grid grid-cols-2 gap-3">
              <Field
                label={`${t('superadmin.customFields.fieldName')} *`}
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
                placeholder="department"
                pattern="[a-z0-9_]+"
                title={t('superadmin.customFields.fieldNamePattern')}
                hint={t('superadmin.customFields.fieldNameHint')}
                className="mono"
              />
              <Select
                label={`${t('superadmin.customFields.fieldType')} *`}
                value={formData.field_type}
                onChange={(e) => setFormData({ ...formData, field_type: e.target.value as FieldType })}
                options={FIELD_TYPES.map((ft) => ({
                  value: ft.id,
                  label: t(`superadmin.customFields.fieldTypes.${ft.id}`, { defaultValue: ft.label }),
                }))}
              />
            </div>
          )}

          <Field
            label={`${t('superadmin.customFields.displayLabel')} *`}
            type="text"
            value={formData.label}
            onChange={(e) => setFormData({ ...formData, label: e.target.value })}
            required
            placeholder={t('superadmin.customFields.displayLabelPlaceholder')}
          />

          <Checkbox
            checked={formData.required}
            onChange={(checked) => setFormData({ ...formData, required: checked })}
            label={t('superadmin.customFields.requiredField')}
          />

          {showOptionsField && (
            <TextareaField
              label={`${t('superadmin.customFields.options')} *`}
              value={formData.options}
              onChange={(v) => setFormData({ ...formData, options: v })}
              rows={4}
              placeholder={t('superadmin.customFields.optionsPlaceholder')}
              required
              hint={t('superadmin.customFields.optionsHint')}
            />
          )}

          <Field
            label={t('superadmin.customFields.helpText')}
            type="text"
            value={formData.help_text}
            onChange={(e) => setFormData({ ...formData, help_text: e.target.value })}
            placeholder={t('superadmin.customFields.helpTextPlaceholder')}
          />

          <div style={{ borderTop: '1px solid var(--b)', paddingTop: 14 }} className="col">
            <span className="sec-t" style={{ marginBottom: 12 }}>
              {t('superadmin.customFields.aiExtractionSettings')}
            </span>
            <div className="col" style={{ gap: 14 }}>
              <TextareaField
                label={t('superadmin.customFields.extractionHints')}
                value={formData.extraction_hints}
                onChange={(v) => setFormData({ ...formData, extraction_hints: v })}
                rows={2}
                placeholder={t('superadmin.customFields.extractionHintsPlaceholder')}
                hint={t('superadmin.customFields.extractionHintsHelp')}
              />
              <TextareaField
                label={t('superadmin.customFields.extractionExamples')}
                value={formData.extraction_examples}
                onChange={(v) => setFormData({ ...formData, extraction_examples: v })}
                rows={3}
                placeholder={t('superadmin.customFields.extractionExamplesPlaceholder')}
                hint={t('superadmin.customFields.extractionExamplesHelp')}
              />
            </div>
          </div>
        </form>
      </Drawer>

      {/* Delete confirmation — replaces the old window.confirm */}
      <ConfirmDialog
        open={deleteTarget != null}
        title={t('superadmin.customFields.deleteConfirm', { label: deleteTarget?.label ?? '' })}
        confirmLabel={t('superadmin.customFields.deleteField')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.name)
          setDeleteTarget(null)
        }}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Archive confirmation — replaces the old window.confirm */}
      <ConfirmDialog
        open={archiveTarget != null}
        tone="warn"
        title={t('superadmin.customFields.archiveConfirm', { label: archiveTarget?.label ?? '' })}
        confirmLabel={t('superadmin.customFields.archiveField')}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          if (archiveTarget) {
            updateMutation.mutate({ fieldName: archiveTarget.name, data: { is_archived: true } })
          }
          setArchiveTarget(null)
        }}
        onCancel={() => setArchiveTarget(null)}
      />
    </div>
  )
}
