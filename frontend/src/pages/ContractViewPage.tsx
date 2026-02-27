import { useState } from 'react'
import { useParams, Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  ShieldExclamationIcon,
  ArrowPathIcon,
  TrashIcon,
  ClipboardDocumentListIcon,
  ChartBarIcon,
  LinkIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractIntelligence from '@/components/dashboard/ContractIntelligence'
import SLASummary from '@/components/dashboard/SLASummary'
import CustomFieldsDisplay from '@/components/contracts/CustomFieldsDisplay'
import SuggestedLinksPanel from '@/components/contracts/SuggestedLinksPanel'
import { useAuth } from '@/contexts/AuthContext'
import { cn, formatDate, formatCurrency, formatFileSize, getRiskColor, getStatusColor } from '@/lib/utils'

type TabType = 'overview' | 'intelligence' | 'slas' | 'related'

const TABS = [
  { id: 'overview' as const, label: 'Overview', icon: InformationCircleIcon },
  { id: 'intelligence' as const, label: 'Intelligence', icon: ClipboardDocumentListIcon },
  { id: 'slas' as const, label: 'SLAs', icon: ChartBarIcon },
  { id: 'related' as const, label: 'Related Docs', icon: LinkIcon },
]

export default function ContractViewPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Get active tab from URL or default to 'overview'
  const activeTab = (searchParams.get('tab') as TabType) || 'overview'
  const setActiveTab = (tab: TabType) => {
    setSearchParams({ tab })
  }

  // Determine if user can edit custom fields (admin, legal, or procurement roles)
  const canEditCustomFields = user?.role === 'admin' || user?.role === 'legal' || user?.role === 'procurement' || user?.role === 'super_admin'

  const { data: contract, isLoading, error } = useQuery({
    queryKey: ['contract', id],
    queryFn: () => api.getContract(id!),
    enabled: !!id,
  })

  const processMutation = useMutation({
    mutationFn: () => api.processContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
    },
  })

  const analyzeMutation = useMutation({
    mutationFn: () => api.analyzeContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract', id] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteContract(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      navigate('/contracts')
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !contract) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Contract not found</p>
        <Link to="/contracts" className="text-primary-600 hover:underline mt-2 inline-block">
          Back to contracts
        </Link>
      </div>
    )
  }

  const isCompleted = contract.status === 'completed'

  return (
    <div className="h-full flex flex-col">
      {/* Compact Header */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 min-w-0">
            <Link
              to="/contracts"
              className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg flex-shrink-0"
            >
              <ArrowLeftIcon className="h-5 w-5" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900 truncate">{contract.filename}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className={cn(
                  'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                  getStatusColor(contract.status)
                )}>
                  {contract.status}
                </span>
                {contract.risk_level && (
                  <span className={cn(
                    'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize',
                    getRiskColor(contract.risk_level)
                  )}>
                    {contract.risk_level} Risk
                  </span>
                )}
                {contract.contract_type && (
                  <span className="text-sm text-gray-500 uppercase">
                    {contract.contract_type}
                  </span>
                )}
                {contract.counterparty && (
                  <span className="text-sm text-gray-500">
                    • {contract.counterparty}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {contract.status === 'pending' && (
              <button
                onClick={() => processMutation.mutate()}
                disabled={processMutation.isPending}
                className="btn-secondary"
              >
                {processMutation.isPending ? (
                  <LoadingSpinner size="sm" className="mr-2" />
                ) : (
                  <ArrowPathIcon className="h-4 w-4 mr-2" />
                )}
                Process
              </button>
            )}
            {isCompleted && (
              <button
                onClick={() => analyzeMutation.mutate()}
                disabled={analyzeMutation.isPending}
                className="btn-primary"
              >
                {analyzeMutation.isPending ? (
                  <LoadingSpinner size="sm" className="mr-2 border-white border-t-transparent" />
                ) : (
                  <ShieldExclamationIcon className="h-4 w-4 mr-2" />
                )}
                Re-analyze
              </button>
            )}
            <Link
              to={`/query?contract=${contract.id}`}
              className="btn-secondary"
            >
              Ask AI
            </Link>
            {!showDeleteConfirm ? (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="btn-secondary text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="btn-secondary text-sm py-1"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  className="btn-secondary text-sm py-1 bg-red-600 text-white hover:bg-red-700"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6">
        <nav className="flex gap-6" aria-label="Tabs">
          {TABS.map((tab) => {
            // Hide Intelligence, SLAs, Related tabs for non-completed contracts
            if (!isCompleted && tab.id !== 'overview') {
              return null
            }
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-600 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        {/* Processing error banner */}
        {contract.processing_error && (
          <div className="mb-6 p-4 rounded-lg border border-red-200 bg-red-50">
            <p className="text-sm font-medium text-red-800">Processing Error</p>
            <p className="text-sm text-red-700 mt-1">{contract.processing_error}</p>
          </div>
        )}

        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left column - Details */}
            <div className="lg:col-span-2 space-y-6">
              {/* Contract Details */}
              <div className="card">
                <div className="card-header">
                  <h2 className="text-sm font-medium text-gray-900">Contract Details</h2>
                </div>
                <div className="card-body grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-xs text-gray-500">Counterparty</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.counterparty || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Contract Value</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.contract_value
                        ? formatCurrency(contract.contract_value, contract.currency || 'USD')
                        : '-'
                      }
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Contract Type</p>
                    <p className="text-sm font-medium text-gray-900 uppercase">
                      {contract.contract_type || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Effective Date</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(contract.effective_date)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Expiration Date</p>
                    <p className="text-sm font-medium text-gray-900">
                      {formatDate(contract.expiration_date)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Jurisdiction</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.jurisdiction || '-'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Auto-Renewal</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.auto_renewal ? 'Yes' : 'No'}
                      {contract.notice_period_days && ` (${contract.notice_period_days}d notice)`}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Renewal Term</p>
                    <p className="text-sm font-medium text-gray-900">
                      {contract.renewal_term_months ? `${contract.renewal_term_months} months` : '-'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Custom Fields */}
              <CustomFieldsDisplay contract={contract} canEdit={canEditCustomFields} />

              {/* Risk Assessment - only show if analyzed */}
              {contract.risk_score !== null && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="text-sm font-medium text-gray-900">Risk Assessment</h2>
                  </div>
                  <div className="card-body">
                    <div className="flex items-center gap-6">
                      <div className={cn(
                        'h-20 w-20 rounded-full flex items-center justify-center text-2xl font-bold',
                        getRiskColor(contract.risk_level)
                      )}>
                        {contract.risk_score}
                      </div>
                      <div className="flex-1">
                        <p className="text-lg font-medium text-gray-900 capitalize mb-1">
                          {contract.risk_level} Risk
                        </p>
                        <p className="text-sm text-gray-500">
                          Based on analysis of {contract.clause_count} clauses and {contract.obligation_count} obligations
                        </p>
                        {isCompleted && (
                          <button
                            onClick={() => setActiveTab('intelligence')}
                            className="text-sm text-primary-600 hover:text-primary-700 mt-2"
                          >
                            View detailed analysis →
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right column - File info & stats */}
            <div className="space-y-6">
              {/* File Information */}
              <div className="card">
                <div className="card-header">
                  <h2 className="text-sm font-medium text-gray-900">File Information</h2>
                </div>
                <div className="card-body space-y-4">
                  <div className="flex items-center gap-3">
                    <DocumentTextIcon className="h-10 w-10 text-gray-400" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {contract.filename}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatFileSize(contract.file_size)} • {contract.mime_type}
                      </p>
                    </div>
                  </div>
                  <div className="pt-4 border-t border-gray-200 space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Uploaded</span>
                      <span className="text-gray-900">{formatDate(contract.created_at)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Last Updated</span>
                      <span className="text-gray-900">{formatDate(contract.updated_at)}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Extraction Stats */}
              {isCompleted && (
                <div className="card">
                  <div className="card-header">
                    <h2 className="text-sm font-medium text-gray-900">Extraction Summary</h2>
                  </div>
                  <div className="card-body">
                    <div className="grid grid-cols-2 gap-4">
                      <button
                        onClick={() => setActiveTab('intelligence')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.clause_count}</p>
                        <p className="text-xs text-gray-500">Clauses</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('intelligence')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.obligation_count}</p>
                        <p className="text-xs text-gray-500">Obligations</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('slas')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-gray-900">{contract.sla_count || 0}</p>
                        <p className="text-xs text-gray-500">SLAs</p>
                      </button>
                      <button
                        onClick={() => setActiveTab('related')}
                        className="text-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
                      >
                        <p className="text-2xl font-bold text-primary-600">→</p>
                        <p className="text-xs text-gray-500">Related</p>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Intelligence Tab */}
        {activeTab === 'intelligence' && isCompleted && id && (
          <ContractIntelligence contractId={id} />
        )}

        {/* SLAs Tab */}
        {activeTab === 'slas' && isCompleted && id && (
          <SLASummary contractId={id} />
        )}

        {/* Related Docs Tab */}
        {activeTab === 'related' && isCompleted && id && (
          <SuggestedLinksPanel contractId={id} />
        )}
      </div>
    </div>
  )
}
