import { useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeftIcon,
  DocumentTextIcon,
  CalendarIcon,
  CurrencyDollarIcon,
  MapPinIcon,
  ShieldExclamationIcon,
  ArrowPathIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractIntelligence from '@/components/dashboard/ContractIntelligence'
import DefinitionsSummary from '@/components/dashboard/DefinitionsSummary'
import FinancialsSummary from '@/components/dashboard/FinancialsSummary'
import ProcessSummary from '@/components/dashboard/ProcessSummary'
import { cn, formatDate, formatCurrency, formatFileSize, getRiskColor, getStatusColor } from '@/lib/utils'

export default function ContractViewPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Link
            to="/contracts"
            className="p-2 -ml-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
          >
            <ArrowLeftIcon className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{contract.filename}</h1>
            <div className="flex items-center gap-3 mt-2">
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
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
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
          {contract.status === 'completed' && (
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
              Analyze
            </button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Metadata card */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900">Contract Details</h2>
            </div>
            <div className="card-body grid grid-cols-2 gap-4">
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
            </div>
          </div>

          {/* Risk assessment */}
          {contract.risk_score !== null && (
            <div className="card">
              <div className="card-header">
                <h2 className="text-sm font-medium text-gray-900">Risk Assessment</h2>
              </div>
              <div className="card-body">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    'h-16 w-16 rounded-full flex items-center justify-center text-2xl font-bold',
                    getRiskColor(contract.risk_level)
                  )}>
                    {contract.risk_score}
                  </div>
                  <div>
                    <p className="text-lg font-medium text-gray-900 capitalize">
                      {contract.risk_level} Risk
                    </p>
                    <p className="text-sm text-gray-500">
                      Based on {contract.clause_count} analyzed clauses
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Processing error */}
          {contract.processing_error && (
            <div className="card border-red-200 bg-red-50">
              <div className="card-body">
                <p className="text-sm font-medium text-red-800">Processing Error</p>
                <p className="text-sm text-red-700 mt-1">{contract.processing_error}</p>
              </div>
            </div>
          )}
        </div>

        {/* Right column - File info */}
        <div className="space-y-6">
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900">File Information</h2>
            </div>
            <div className="card-body space-y-4">
              <div className="flex items-center gap-3">
                <DocumentTextIcon className="h-8 w-8 text-gray-400" />
                <div>
                  <p className="text-sm font-medium text-gray-900 break-all">
                    {contract.filename}
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatFileSize(contract.file_size)} • {contract.mime_type}
                  </p>
                </div>
              </div>
              <div className="pt-4 border-t border-gray-200 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Uploaded</span>
                  <span className="text-gray-900">{formatDate(contract.created_at)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Clauses</span>
                  <span className="text-gray-900">{contract.clause_count}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Obligations</span>
                  <span className="text-gray-900">{contract.obligation_count}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Quick actions */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-sm font-medium text-gray-900">Actions</h2>
            </div>
            <div className="card-body space-y-2">
              <Link
                to={`/query?contract=${contract.id}`}
                className="btn-secondary w-full justify-center"
              >
                Ask AI about this contract
              </Link>
              {!showDeleteConfirm ? (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="btn-secondary w-full justify-center text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <TrashIcon className="h-4 w-4 mr-2" />
                  Delete Contract
                </button>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-red-600 text-center">Are you sure?</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setShowDeleteConfirm(false)}
                      className="btn-secondary flex-1 justify-center text-sm"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => deleteMutation.mutate()}
                      disabled={deleteMutation.isPending}
                      className="btn-secondary flex-1 justify-center text-sm bg-red-600 text-white hover:bg-red-700"
                    >
                      {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Contract Intelligence Section - only for completed contracts */}
      {contract.status === 'completed' && id && (
        <div className="mt-8 pt-8 border-t border-gray-200">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Contract Intelligence</h2>
          <ContractIntelligence contractId={id} />
        </div>
      )}

      {/* Definitions Section */}
      {contract.status === 'completed' && id && (
        <div className="mt-8 pt-8 border-t border-gray-200">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Contract Definitions</h2>
          <DefinitionsSummary contractId={id} />
        </div>
      )}

      {/* Financials Section */}
      {contract.status === 'completed' && id && (
        <div className="mt-8 pt-8 border-t border-gray-200">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Financial Terms</h2>
          <FinancialsSummary contractId={id} />
        </div>
      )}

      {/* Process Steps Section */}
      {contract.status === 'completed' && id && (
        <div className="mt-8 pt-8 border-t border-gray-200">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Process & Workflow</h2>
          <ProcessSummary contractId={id} />
        </div>
      )}
    </div>
  )
}
