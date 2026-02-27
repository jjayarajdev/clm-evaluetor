import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { PencilIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import type { CustomField, Contract } from '@/types'

interface CustomFieldsDisplayProps {
  contract: Contract
  canEdit?: boolean
}

type FieldValue = string | number | boolean | string[] | null | undefined

export default function CustomFieldsDisplay({ contract, canEdit = false }: CustomFieldsDisplayProps) {
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [editValues, setEditValues] = useState<Record<string, FieldValue>>({})

  // Fetch custom field definitions for contracts
  const { data: fieldDefinitions, isLoading, error } = useQuery({
    queryKey: ['custom-fields', 'contract'],
    queryFn: () => api.getTenantCustomFields('contract'),
  })

  const updateMutation = useMutation({
    mutationFn: (customFields: Record<string, unknown>) =>
      api.updateContractCustomFields(contract.id, customFields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', contract.id] })
      setIsEditing(false)
      setEditValues({})
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <LoadingSpinner size="sm" />
      </div>
    )
  }

  if (error || !fieldDefinitions || fieldDefinitions.length === 0) {
    return null // No custom fields defined for this tenant
  }

  const startEditing = () => {
    // Cast custom_fields to the expected type
    const initialValues: Record<string, FieldValue> = {}
    if (contract.custom_fields) {
      for (const [key, val] of Object.entries(contract.custom_fields)) {
        initialValues[key] = val as FieldValue
      }
    }
    setEditValues(initialValues)
    setIsEditing(true)
  }

  const cancelEditing = () => {
    setIsEditing(false)
    setEditValues({})
  }

  const saveChanges = () => {
    updateMutation.mutate(editValues)
  }

  const handleValueChange = (fieldName: string, value: FieldValue) => {
    setEditValues(prev => ({ ...prev, [fieldName]: value }))
  }

  const renderFieldValue = (field: CustomField): React.ReactNode => {
    const value = contract.custom_fields?.[field.name]

    if (value === null || value === undefined || value === '') {
      return <span className="text-gray-400 italic">Not set</span>
    }

    switch (field.field_type) {
      case 'checkbox':
        return <>{value ? 'Yes' : 'No'}</>
      case 'date':
        return <>{new Date(value as string).toLocaleDateString()}</>
      case 'currency':
        return typeof value === 'number'
          ? <>{new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value)}</>
          : <>{String(value)}</>
      case 'multi_select':
        return <>{Array.isArray(value) ? value.join(', ') : String(value)}</>
      case 'url':
        return (
          <a href={value as string} target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">
            {value as string}
          </a>
        )
      case 'email':
        return (
          <a href={`mailto:${value}`} className="text-primary-600 hover:underline">
            {value as string}
          </a>
        )
      default:
        return <>{String(value)}</>
    }
  }

  const renderFieldInput = (field: CustomField) => {
    const value = editValues[field.name]

    switch (field.field_type) {
      case 'text':
        return (
          <input
            type="text"
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(field.name, e.target.value)}
            className="input-field text-sm"
            placeholder={field.help_text || `Enter ${field.label.toLowerCase()}`}
          />
        )
      case 'number':
      case 'currency':
        return (
          <input
            type="number"
            value={(value as number) ?? ''}
            onChange={(e) => handleValueChange(field.name, e.target.value ? Number(e.target.value) : null)}
            className="input-field text-sm"
            placeholder={field.help_text || `Enter ${field.label.toLowerCase()}`}
          />
        )
      case 'date':
        return (
          <input
            type="date"
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(field.name, e.target.value)}
            className="input-field text-sm"
          />
        )
      case 'checkbox':
        return (
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => handleValueChange(field.name, e.target.checked)}
            className="h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
          />
        )
      case 'dropdown':
        return (
          <select
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(field.name, e.target.value)}
            className="input-field text-sm"
          >
            <option value="">Select...</option>
            {field.options?.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        )
      case 'multi_select':
        return (
          <select
            multiple
            value={(value as string[]) || []}
            onChange={(e) => {
              const selected = Array.from(e.target.selectedOptions, option => option.value)
              handleValueChange(field.name, selected)
            }}
            className="input-field text-sm min-h-[80px]"
          >
            {field.options?.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        )
      case 'url':
        return (
          <input
            type="url"
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(field.name, e.target.value)}
            className="input-field text-sm"
            placeholder="https://..."
          />
        )
      case 'email':
        return (
          <input
            type="email"
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(field.name, e.target.value)}
            className="input-field text-sm"
            placeholder="email@example.com"
          />
        )
      default:
        return (
          <input
            type="text"
            value={(value as string) || ''}
            onChange={(e) => handleValueChange(field.name, e.target.value)}
            className="input-field text-sm"
          />
        )
    }
  }

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900">Custom Fields</h2>
        {canEdit && !isEditing && (
          <button
            onClick={startEditing}
            className="p-1 text-gray-400 hover:text-gray-600 rounded"
            title="Edit custom fields"
          >
            <PencilIcon className="h-4 w-4" />
          </button>
        )}
        {isEditing && (
          <div className="flex items-center gap-2">
            <button
              onClick={cancelEditing}
              className="p-1 text-gray-400 hover:text-gray-600 rounded"
              title="Cancel"
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
            <button
              onClick={saveChanges}
              disabled={updateMutation.isPending}
              className="p-1 text-green-500 hover:text-green-600 rounded disabled:opacity-50"
              title="Save changes"
            >
              {updateMutation.isPending ? (
                <LoadingSpinner size="sm" />
              ) : (
                <CheckIcon className="h-4 w-4" />
              )}
            </button>
          </div>
        )}
      </div>
      <div className="card-body">
        <div className="grid grid-cols-2 gap-4">
          {fieldDefinitions.map((field) => (
            <div key={field.name}>
              <p className="text-xs text-gray-500">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </p>
              {isEditing ? (
                <div className="mt-1">
                  {renderFieldInput(field)}
                  {field.help_text && (
                    <p className="text-xs text-gray-400 mt-1">{field.help_text}</p>
                  )}
                </div>
              ) : (
                <p className="text-sm font-medium text-gray-900">
                  {renderFieldValue(field)}
                </p>
              )}
            </div>
          ))}
        </div>
        {updateMutation.isError && (
          <p className="text-sm text-red-600 mt-3">
            Failed to save changes. Please try again.
          </p>
        )}
      </div>
    </div>
  )
}
