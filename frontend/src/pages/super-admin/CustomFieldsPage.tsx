import { useState, useEffect } from 'react'
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
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
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

const FIELD_TYPE_COLORS: Record<FieldType, string> = {
  text: 'bg-gray-100 text-gray-700',
  number: 'bg-blue-100 text-blue-700',
  date: 'bg-purple-100 text-purple-700',
  dropdown: 'bg-green-100 text-green-700',
  multi_select: 'bg-teal-100 text-teal-700',
  checkbox: 'bg-amber-100 text-amber-700',
  url: 'bg-cyan-100 text-cyan-700',
  email: 'bg-rose-100 text-rose-700',
  currency: 'bg-emerald-100 text-emerald-700',
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

export default function CustomFieldsPage() {
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const tenantId = searchParams.get('tenant') || ''

  const [selectedEntityType, setSelectedEntityType] = useState<EntityType>('contract')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingField, setEditingField] = useState<CustomField | null>(null)
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

  const handleDelete = (field: CustomField) => {
    if (window.confirm(`Are you sure you want to delete the field "${field.label}"?`)) {
      deleteMutation.mutate(field.name)
    }
  }

  const handleArchive = (field: CustomField) => {
    if (window.confirm(`Are you sure you want to archive the field "${field.label}"?`)) {
      updateMutation.mutate({
        fieldName: field.name,
        data: { is_archived: true },
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Custom Fields</h1>
          <p className="mt-1 text-sm text-gray-500">
            Configure custom data fields for each entity type
          </p>
        </div>
        {tenantId && (
          <button onClick={openCreateModal} className="btn-primary">
            <PlusIcon className="h-4 w-4 mr-2" />
            Add Field
          </button>
        )}
      </div>

      {/* Tenant Selector */}
      <div className="flex items-center gap-4">
        <label className="text-sm font-medium text-gray-700">Tenant:</label>
        <select
          value={tenantId}
          onChange={(e) => handleTenantChange(e.target.value)}
          className="input max-w-xs"
        >
          <option value="">Select a tenant</option>
          {tenants?.map((tenant) => (
            <option key={tenant.id} value={tenant.id}>
              {tenant.name}
            </option>
          ))}
        </select>
        {selectedTenant && (
          <span className="text-sm text-gray-500">
            ({selectedTenant.slug})
          </span>
        )}
      </div>

      {!tenantId ? (
        <div className="text-center py-12 text-gray-500">
          Please select a tenant to manage custom fields.
        </div>
      ) : (
        <>
          {/* Entity Type Tabs */}
          <div className="border-b border-gray-200">
            <nav className="flex gap-6">
              {ENTITY_TYPES.map((entityType) => (
                <button
                  key={entityType.id}
                  onClick={() => setSelectedEntityType(entityType.id)}
                  className={cn(
                    'py-3 text-sm font-medium border-b-2 transition-colors',
                    selectedEntityType === entityType.id
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  )}
                >
                  {entityType.label}
                </button>
              ))}
            </nav>
          </div>

          {/* Error state */}
          {error && (
            <div className="rounded-lg bg-red-50 p-4 text-red-700">
              Error loading custom fields. Please try again.
            </div>
          )}

          {/* Fields List */}
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <LoadingSpinner size="lg" />
            </div>
          ) : (
            <div className="card overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="w-8 px-2 py-3"></th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Field
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Required
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Visible
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {fields?.filter((f) => !f.is_archived).map((field) => (
                    <tr key={field.name} className="hover:bg-gray-50">
                      <td className="px-2 py-3 text-center">
                        <Bars3Icon className="h-4 w-4 text-gray-300 cursor-grab" title="Drag to reorder" />
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm font-medium text-gray-900">{field.label}</p>
                          <p className="text-xs text-gray-500 font-mono">{field.name}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'inline-flex px-2 py-0.5 rounded text-xs font-medium capitalize',
                          FIELD_TYPE_COLORS[field.field_type]
                        )}>
                          {field.field_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'inline-flex px-2 py-0.5 rounded text-xs font-medium',
                          field.required
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-gray-100 text-gray-500'
                        )}>
                          {field.required ? 'Yes' : 'No'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => handleToggleVisibility(field)}
                          className={cn(
                            'p-1 rounded',
                            field.is_visible
                              ? 'text-green-600 hover:bg-green-50'
                              : 'text-gray-400 hover:bg-gray-100'
                          )}
                          title={field.is_visible ? 'Visible' : 'Hidden'}
                        >
                          {field.is_visible ? (
                            <EyeIcon className="h-5 w-5" />
                          ) : (
                            <EyeSlashIcon className="h-5 w-5" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => openEditModal(field)}
                            className="p-1 text-gray-400 hover:text-gray-600"
                            title="Edit field"
                          >
                            <PencilSquareIcon className="h-5 w-5" />
                          </button>
                          <button
                            onClick={() => handleArchive(field)}
                            className="p-1 text-gray-400 hover:text-amber-600"
                            title="Archive field"
                          >
                            <ArchiveBoxIcon className="h-5 w-5" />
                          </button>
                          <button
                            onClick={() => handleDelete(field)}
                            className="p-1 text-gray-400 hover:text-red-600"
                            title="Delete field"
                            disabled={deleteMutation.isPending}
                          >
                            <TrashIcon className="h-5 w-5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {fields?.filter((f) => !f.is_archived).length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  No custom fields defined for {selectedEntityType}s.
                  <br />
                  <button
                    onClick={openCreateModal}
                    className="mt-2 text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Add your first field
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Preview Section */}
          {fields && fields.filter((f) => !f.is_archived && f.is_visible).length > 0 && (
            <div className="card p-5">
              <h3 className="font-semibold text-gray-900 mb-4">Form Preview</h3>
              <p className="text-sm text-gray-500 mb-4">
                This is how the custom fields will appear in forms.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl">
                {fields
                  .filter((f) => !f.is_archived && f.is_visible)
                  .sort((a, b) => a.display_order - b.display_order)
                  .map((field) => (
                    <div key={field.name}>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {field.label}
                        {field.required && <span className="text-red-500 ml-1">*</span>}
                      </label>
                      {field.field_type === 'text' && (
                        <input type="text" className="input" placeholder={field.help_text || ''} disabled />
                      )}
                      {field.field_type === 'number' && (
                        <input type="number" className="input" disabled />
                      )}
                      {field.field_type === 'date' && (
                        <input type="date" className="input" disabled />
                      )}
                      {field.field_type === 'dropdown' && (
                        <select className="input" disabled>
                          <option>Select {field.label}...</option>
                          {field.options?.map((opt) => (
                            <option key={opt}>{opt}</option>
                          ))}
                        </select>
                      )}
                      {field.field_type === 'multi_select' && (
                        <select className="input" multiple disabled>
                          {field.options?.map((opt) => (
                            <option key={opt}>{opt}</option>
                          ))}
                        </select>
                      )}
                      {field.field_type === 'checkbox' && (
                        <div className="flex items-center gap-2">
                          <input type="checkbox" className="rounded border-gray-300" disabled />
                          <span className="text-sm text-gray-500">{field.help_text || 'Enable'}</span>
                        </div>
                      )}
                      {field.field_type === 'url' && (
                        <input type="url" className="input" placeholder="https://..." disabled />
                      )}
                      {field.field_type === 'email' && (
                        <input type="email" className="input" placeholder="email@example.com" disabled />
                      )}
                      {field.field_type === 'currency' && (
                        <div className="flex">
                          <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                            $
                          </span>
                          <input type="number" className="input rounded-l-none" disabled />
                        </div>
                      )}
                      {field.help_text && field.field_type !== 'checkbox' && (
                        <p className="mt-1 text-xs text-gray-500">{field.help_text}</p>
                      )}
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Create/Edit Field Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={closeModal} />
            <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                {editingField ? 'Edit Field' : 'Create Field'}
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                {!editingField && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Field Name *
                      </label>
                      <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="input font-mono"
                        required
                        placeholder="department"
                        pattern="[a-z0-9_]+"
                        title="Only lowercase letters, numbers, and underscores"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Lowercase, no spaces (e.g., custom_field)
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Field Type *
                      </label>
                      <select
                        value={formData.field_type}
                        onChange={(e) => setFormData({ ...formData, field_type: e.target.value as FieldType })}
                        className="input"
                      >
                        {FIELD_TYPES.map((ft) => (
                          <option key={ft.id} value={ft.id}>
                            {ft.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Display Label *
                  </label>
                  <input
                    type="text"
                    value={formData.label}
                    onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                    className="input"
                    required
                    placeholder="Department"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="required"
                    checked={formData.required}
                    onChange={(e) => setFormData({ ...formData, required: e.target.checked })}
                    className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                  />
                  <label htmlFor="required" className="text-sm text-gray-700">
                    Required field
                  </label>
                </div>

                {showOptionsField && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Options *
                    </label>
                    <textarea
                      value={formData.options}
                      onChange={(e) => setFormData({ ...formData, options: e.target.value })}
                      className="input"
                      rows={4}
                      placeholder="Enter one option per line"
                      required={showOptionsField}
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      One option per line
                    </p>
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Help Text
                  </label>
                  <input
                    type="text"
                    value={formData.help_text}
                    onChange={(e) => setFormData({ ...formData, help_text: e.target.value })}
                    className="input"
                    placeholder="Optional helper text shown below the field"
                  />
                </div>

                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium text-gray-900 mb-3">AI Extraction Settings</h4>

                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Extraction Hints
                      </label>
                      <textarea
                        value={formData.extraction_hints}
                        onChange={(e) => setFormData({ ...formData, extraction_hints: e.target.value })}
                        className="input"
                        rows={2}
                        placeholder="Instructions for AI to find this value in contracts"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Guide the AI on where to look for this value
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Extraction Examples
                      </label>
                      <textarea
                        value={formData.extraction_examples}
                        onChange={(e) => setFormData({ ...formData, extraction_examples: e.target.value })}
                        className="input"
                        rows={3}
                        placeholder="Example values (one per line)"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Sample values to help AI understand the expected format
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-4 border-t">
                  <button type="button" onClick={closeModal} className="btn-secondary">
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending || updateMutation.isPending}
                    className="btn-primary"
                  >
                    {createMutation.isPending || updateMutation.isPending ? (
                      <LoadingSpinner size="sm" className="border-white border-t-transparent" />
                    ) : editingField ? (
                      'Update'
                    ) : (
                      'Create'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
