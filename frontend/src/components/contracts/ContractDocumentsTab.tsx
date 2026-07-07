import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  DocumentTextIcon,
  PlusIcon,
  XMarkIcon,
  ChevronDownIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'
import type {
  DocumentType,
  ContractDocumentCreate,
  ContractDocument,
  DocumentSignature,
  DocumentSection,
} from '@/types/fitgap'

const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  main_agreement: 'Main Agreement',
  amendment: 'Amendment',
  addendum: 'Addendum',
  schedule: 'Schedule',
  exhibit: 'Exhibit',
  statement_of_work: 'Statement of Work',
  side_letter: 'Side Letter',
  appendix: 'Appendix',
  certificate: 'Certificate',
  other: 'Other',
}

const SIGNATURE_STATUS_COLORS: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800',
  signed: 'bg-green-100 text-green-800',
  declined: 'bg-red-100 text-red-800',
  expired: 'bg-gray-100 text-gray-800',
}

interface Props {
  contractId: string
}

function DocumentRow({ doc, contractId }: { doc: ContractDocument; contractId: string }) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  const { data: signatures = [] } = useQuery<DocumentSignature[]>({
    queryKey: ['doc-signatures', contractId, doc.id],
    queryFn: () => api.getDocumentSignatures(contractId, doc.id),
    enabled: expanded,
  })

  const { data: sections = [] } = useQuery<DocumentSection[]>({
    queryKey: ['doc-sections', contractId, doc.id],
    queryFn: () => api.getDocumentSections(contractId, doc.id),
    enabled: expanded,
  })

  return (
    <div className="border-b border-gray-200 last:border-b-0">
      <div
        className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? (
          <ChevronDownIcon className="h-4 w-4 text-gray-400 shrink-0" />
        ) : (
          <ChevronRightIcon className="h-4 w-4 text-gray-400 shrink-0" />
        )}
        <DocumentTextIcon className="h-5 w-5 text-primary-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{doc.title}</p>
          {doc.description && (
            <p className="text-xs text-gray-500 truncate">{doc.description}</p>
          )}
        </div>
        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded shrink-0">
          {t(`docsTab.docTypes.${doc.document_type}`, { defaultValue: DOC_TYPE_LABELS[doc.document_type] || doc.document_type })}
        </span>
        {doc.version && (
          <span className="text-xs text-gray-400 shrink-0">v{doc.version}</span>
        )}
        <span className="text-xs text-gray-400 shrink-0">{doc.language}</span>
      </div>

      {expanded && (
        <div className="px-8 pb-4 space-y-3">
          {/* Signatures */}
          {signatures.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t('docsTab.signatures', { count: signatures.length })}</p>
              <div className="space-y-2">
                {signatures.map((sig) => (
                  <div key={sig.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{sig.signer_name}</p>
                      <p className="text-xs text-gray-500">
                        {[sig.signer_title, sig.signer_organization].filter(Boolean).join(', ') || t('docsTab.noTitle')}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs capitalize">{sig.signature_type.replace(/_/g, ' ')}</span>
                      <span className={cn(
                        'px-2 py-0.5 rounded text-xs font-medium capitalize',
                        SIGNATURE_STATUS_COLORS[sig.signature_status] || 'bg-gray-100 text-gray-800'
                      )}>
                        {t([`status.${sig.signature_status}`, `docsTab.signatureStatus.${sig.signature_status}`], { defaultValue: sig.signature_status })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sections */}
          {sections.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">{t('docsTab.sections', { count: sections.length })}</p>
              <div className="space-y-1">
                {sections.map((section) => (
                  <div key={section.id} className="flex items-baseline gap-2 px-3 py-1.5">
                    {section.section_number && (
                      <span className="text-xs font-mono text-gray-400 w-8">{section.section_number}</span>
                    )}
                    <span className="text-sm text-gray-700">{section.title}</span>
                    {section.page_start && (
                      <span className="text-xs text-gray-400 ml-auto">
                        p.{section.page_start}{section.page_end && section.page_end !== section.page_start ? `–${section.page_end}` : ''}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {signatures.length === 0 && sections.length === 0 && (
            <p className="text-xs text-gray-400 italic">{t('docsTab.noSignaturesOrSections')}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default function ContractDocumentsTab({ contractId }: Props) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [formData, setFormData] = useState<Partial<ContractDocumentCreate>>({
    document_type: 'other',
    language: 'en',
  })

  const { data: docData, isLoading } = useQuery({
    queryKey: ['contract-documents', contractId],
    queryFn: () => api.getContractDocuments(contractId),
  })

  const documents = docData?.items ?? []

  const createMutation = useMutation({
    mutationFn: (data: ContractDocumentCreate) => api.createContractDocument(contractId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-documents', contractId] })
      setShowCreate(false)
      setFormData({ document_type: 'other', language: 'en' })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <DocumentTextIcon className="h-5 w-5 text-gray-400" />
          {t('docsTab.title', { count: documents.length })}
        </h2>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary text-xs flex items-center gap-1"
        >
          <PlusIcon className="h-3.5 w-3.5" /> {t('docsTab.addDocument')}
        </button>
      </div>

      {/* Summary by type */}
      {documents.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(
            documents.reduce<Record<string, number>>((acc, d) => {
              acc[d.document_type] = (acc[d.document_type] || 0) + 1
              return acc
            }, {})
          ).map(([type, count]) => (
            <span key={type} className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
              {t(`docsTab.docTypes.${type}`, { defaultValue: DOC_TYPE_LABELS[type as DocumentType] || type })}: {count}
            </span>
          ))}
        </div>
      )}

      {/* Documents list */}
      <div className="card">
        {documents.length > 0 ? (
          documents.map((doc) => (
            <DocumentRow key={doc.id} doc={doc} contractId={contractId} />
          ))
        ) : (
          <div className="px-4 py-8 text-center">
            <DocumentTextIcon className="h-8 w-8 text-gray-300 mx-auto mb-2" />
            <p className="text-sm text-gray-500">{t('docsTab.noDocuments')}</p>
            <p className="text-xs text-gray-400 mt-1">{t('docsTab.noDocumentsHint')}</p>
          </div>
        )}
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">{t('docsTab.addDocument')}</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('docsTab.titleLabel')}</label>
                <input
                  type="text"
                  value={formData.title || ''}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('docsTab.documentTypeLabel')}</label>
                  <select
                    value={formData.document_type || 'other'}
                    onChange={(e) => setFormData({ ...formData, document_type: e.target.value as DocumentType })}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  >
                    {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
                      <option key={value} value={value}>{t(`docsTab.docTypes.${value}`, { defaultValue: label })}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('docsTab.version')}</label>
                  <input
                    type="text"
                    value={formData.version || ''}
                    onChange={(e) => setFormData({ ...formData, version: e.target.value })}
                    placeholder={t('docsTab.versionPlaceholder')}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('docsTab.description')}</label>
                <textarea
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('common.language')}</label>
                <input
                  type="text"
                  value={formData.language || 'en'}
                  onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button onClick={() => setShowCreate(false)} className="btn-secondary">{t('common.cancel')}</button>
              <button
                onClick={() => {
                  if (formData.title && formData.document_type) {
                    createMutation.mutate(formData as ContractDocumentCreate)
                  }
                }}
                disabled={!formData.title || createMutation.isPending}
                className="btn-primary"
              >
                {createMutation.isPending ? t('docsTab.adding') : t('docsTab.addDocument')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
