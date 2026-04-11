import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  LinkIcon,
  CheckIcon,
  XMarkIcon,
  ChevronDownIcon,
  SparklesIcon,
  ExclamationTriangleIcon,
  DocumentTextIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  CheckCircleIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn, formatDate } from '@/lib/utils'
import type { SuggestedLink, LinkType, ContractLinkOut } from '@/types'

interface SuggestedLinksPanelProps {
  contractId: string
}

// Link type options for modify dropdown
const LINK_TYPES: { value: LinkType; label: string }[] = [
  { value: 'sow', label: 'Statement of Work (SOW)' },
  { value: 'work_order', label: 'Work Order' },
  { value: 'service_order', label: 'Service Order' },
  { value: 'purchase_order', label: 'Purchase Order' },
  { value: 'amendment', label: 'Amendment' },
  { value: 'addendum', label: 'Addendum' },
  { value: 'change_order', label: 'Change Order' },
  { value: 'modification', label: 'Modification' },
  { value: 'renewal', label: 'Renewal' },
  { value: 'exhibit', label: 'Exhibit' },
  { value: 'schedule', label: 'Schedule' },
  { value: 'appendix', label: 'Appendix' },
  { value: 'attachment', label: 'Attachment' },
  { value: 'supersedes', label: 'Supersedes' },
  { value: 'references', label: 'References' },
  { value: 'related', label: 'Related' },
]

function linkTypeLabel(type: string): string {
  const found = LINK_TYPES.find(t => t.value === type)
  return found ? found.label : type.replace(/_/g, ' ')
}

function ConfidenceBar({ score }: { score: number }) {
  const percentage = Math.round(score * 100)

  let colorClass = 'bg-red-500'
  if (percentage >= 80) {
    colorClass = 'bg-green-500'
  } else if (percentage >= 50) {
    colorClass = 'bg-yellow-500'
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={cn('h-full rounded-full transition-all', colorClass)}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className={cn(
        'text-xs font-medium min-w-[3rem] text-right',
        percentage >= 80 ? 'text-green-600' : percentage >= 50 ? 'text-yellow-600' : 'text-red-600'
      )}>
        {percentage}%
      </span>
    </div>
  )
}

// ============ ESTABLISHED LINK CARD ============

function EstablishedLinkCard({ link }: { link: ContractLinkOut }) {
  const c = link.linked_contract
  const isParent = link.direction === 'parent'

  return (
    <div className="border rounded-lg p-4 bg-white border-gray-200">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="shrink-0 mt-0.5">
            {isParent ? (
              <ArrowUpIcon className="h-5 w-5 text-blue-500" />
            ) : (
              <ArrowDownIcon className="h-5 w-5 text-green-500" />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase font-semibold text-gray-400 tracking-wider">
                {isParent ? 'Parent' : 'Child'}
              </span>
              <CheckCircleIcon className="h-3.5 w-3.5 text-green-500" />
            </div>
            <Link
              to={`/contracts/${c.id}`}
              className="text-sm font-medium text-gray-900 hover:text-primary-600 truncate block mt-0.5"
            >
              {c.filename}
            </Link>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500">
              {c.contract_type && (
                <span className="bg-gray-100 px-1.5 py-0.5 rounded uppercase">
                  {c.contract_type}
                </span>
              )}
              {c.counterparty && <span>{c.counterparty}</span>}
              {c.effective_date && <span>Eff: {formatDate(c.effective_date)}</span>}
              {c.expiration_date && <span>Exp: {formatDate(c.expiration_date)}</span>}
            </div>
          </div>
        </div>

        <div className="shrink-0 flex flex-col items-end gap-1">
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700">
            <LinkIcon className="h-3 w-3" />
            {linkTypeLabel(link.link_type)}
          </span>
          {c.risk_level && (
            <span className={cn(
              'text-[10px] px-1.5 py-0.5 rounded font-medium uppercase',
              c.risk_level === 'high' || c.risk_level === 'critical'
                ? 'bg-red-100 text-red-700'
                : c.risk_level === 'medium'
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-green-100 text-green-700'
            )}>
              {c.risk_level} risk
            </span>
          )}
        </div>
      </div>

      {link.link_description && (
        <div className="mt-2 text-xs text-gray-500 bg-gray-50 rounded p-2">
          {link.link_description}
        </div>
      )}
    </div>
  )
}

// ============ SUGGESTION CARD ============

interface SuggestionCardProps {
  suggestion: SuggestedLink
  contractId: string
  onReviewComplete: () => void
}

function SuggestionCard({ suggestion, contractId, onReviewComplete }: SuggestionCardProps) {
  const queryClient = useQueryClient()
  const [showModifyDropdown, setShowModifyDropdown] = useState(false)
  const [isProcessing, setIsProcessing] = useState(false)

  const reviewMutation = useMutation({
    mutationFn: (params: { action: 'approve' | 'reject' | 'modify'; modifiedLinkType?: string }) =>
      api.reviewSuggestedLink(contractId, suggestion.id, params.action, params.modifiedLinkType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggested-links', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract-links', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
      onReviewComplete()
    },
    onSettled: () => {
      setIsProcessing(false)
    },
  })

  const handleApprove = () => {
    setIsProcessing(true)
    reviewMutation.mutate({ action: 'approve' })
  }

  const handleReject = () => {
    setIsProcessing(true)
    reviewMutation.mutate({ action: 'reject' })
  }

  const handleModify = (linkType: string) => {
    setIsProcessing(true)
    setShowModifyDropdown(false)
    reviewMutation.mutate({ action: 'modify', modifiedLinkType: linkType })
  }

  // Show the "other" contract — if we're viewing the target, show source and vice versa
  const isViewingTarget = suggestion.target_contract_id === contractId
  const linkedContract = isViewingTarget ? suggestion.source_contract : suggestion.target_contract
  const linkedContractId = isViewingTarget ? suggestion.source_contract_id : suggestion.target_contract_id
  const isHighConfidence = suggestion.confidence_score >= 0.8
  const isLowConfidence = suggestion.confidence_score < 0.5

  return (
    <div className={cn(
      'border rounded-lg p-4 bg-white',
      isHighConfidence && 'border-green-200 bg-green-50/30',
      isLowConfidence && 'border-yellow-200 bg-yellow-50/30',
      !isHighConfidence && !isLowConfidence && 'border-gray-200'
    )}>
      {/* Header with contract info */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="shrink-0 mt-0.5">
            <DocumentTextIcon className="h-5 w-5 text-gray-400" />
          </div>
          <div className="min-w-0">
            <Link
              to={`/contracts/${linkedContractId}`}
              className="text-sm font-medium text-gray-900 hover:text-primary-600 truncate block"
            >
              {linkedContract?.filename || 'Unknown Contract'}
            </Link>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500">
              {isViewingTarget && (
                <span className="bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-[10px] font-medium uppercase">
                  Child
                </span>
              )}
              {linkedContract?.contract_type && (
                <span className="bg-gray-100 px-1.5 py-0.5 rounded uppercase">
                  {linkedContract.contract_type}
                </span>
              )}
              {linkedContract?.counterparty && (
                <span>{linkedContract.counterparty}</span>
              )}
              {linkedContract?.effective_date && (
                <span>Effective: {formatDate(linkedContract.effective_date)}</span>
              )}
            </div>
          </div>
        </div>

        {/* Suggested link type badge */}
        <div className="shrink-0">
          <span className={cn(
            'inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium',
            'bg-primary-100 text-primary-700'
          )}>
            <LinkIcon className="h-3 w-3" />
            {suggestion.suggested_link_type.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      {/* Confidence score */}
      <div className="mt-3">
        <div className="flex items-center gap-2 mb-1">
          <SparklesIcon className="h-4 w-4 text-gray-400" />
          <span className="text-xs text-gray-500">AI Confidence</span>
        </div>
        <ConfidenceBar score={suggestion.confidence_score} />
      </div>

      {/* Reasoning */}
      {suggestion.reasoning && (
        <div className="mt-3 text-xs text-gray-600 bg-gray-50 rounded p-2">
          {suggestion.reasoning}
        </div>
      )}

      {/* Low confidence warning */}
      {isLowConfidence && (
        <div className="mt-3 flex items-center gap-2 text-xs text-yellow-700 bg-yellow-50 rounded p-2">
          <ExclamationTriangleIcon className="h-4 w-4 shrink-0" />
          <span>Low confidence - please verify before approving</span>
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={handleApprove}
          disabled={isProcessing}
          className={cn(
            'btn-primary text-sm py-1.5 px-3 flex items-center gap-1',
            isProcessing && 'opacity-50 cursor-not-allowed'
          )}
        >
          {isProcessing ? (
            <LoadingSpinner size="sm" className="border-white border-t-transparent" />
          ) : (
            <CheckIcon className="h-4 w-4" />
          )}
          Approve
        </button>

        <button
          onClick={handleReject}
          disabled={isProcessing}
          className={cn(
            'btn-secondary text-sm py-1.5 px-3 flex items-center gap-1 text-red-600 hover:text-red-700 hover:bg-red-50',
            isProcessing && 'opacity-50 cursor-not-allowed'
          )}
        >
          <XMarkIcon className="h-4 w-4" />
          Reject
        </button>

        {/* Modify dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowModifyDropdown(!showModifyDropdown)}
            disabled={isProcessing}
            className={cn(
              'btn-secondary text-sm py-1.5 px-3 flex items-center gap-1',
              isProcessing && 'opacity-50 cursor-not-allowed'
            )}
          >
            Modify
            <ChevronDownIcon className={cn('h-4 w-4 transition-transform', showModifyDropdown && 'rotate-180')} />
          </button>

          {showModifyDropdown && (
            <div className="absolute z-10 mt-1 right-0 w-56 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-auto">
              {LINK_TYPES.map((type) => (
                <button
                  key={type.value}
                  onClick={() => handleModify(type.value)}
                  className={cn(
                    'w-full px-3 py-2 text-left text-sm hover:bg-gray-50',
                    type.value === suggestion.suggested_link_type && 'bg-primary-50 text-primary-700'
                  )}
                >
                  {type.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ============ MAIN PANEL ============

export default function SuggestedLinksPanel({ contractId }: SuggestedLinksPanelProps) {
  const queryClient = useQueryClient()

  // Fetch established links
  const { data: linksData, isLoading: linksLoading } = useQuery({
    queryKey: ['contract-links', contractId],
    queryFn: () => api.getContractLinks(contractId),
    enabled: !!contractId,
  })

  // Fetch AI suggestions
  const { data: suggestionsData, isLoading: suggestionsLoading } = useQuery({
    queryKey: ['suggested-links', contractId],
    queryFn: () => api.getSuggestedLinks(contractId),
    enabled: !!contractId,
  })

  const batchApproveMutation = useMutation({
    mutationFn: (suggestionIds: string[]) =>
      api.batchReviewSuggestedLinks(contractId, suggestionIds, 'approve'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggested-links', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract-links', contractId] })
      queryClient.invalidateQueries({ queryKey: ['contract', contractId] })
    },
  })

  const handleReviewComplete = () => {
    // Queries are invalidated by the mutation
  }

  const handleApproveAll = () => {
    const pendingSuggestions = suggestionsData?.suggestions.filter(s => s.status === 'pending') || []
    const ids = pendingSuggestions.map(s => s.id)
    if (ids.length > 0) {
      batchApproveMutation.mutate(ids)
    }
  }

  const isLoading = linksLoading || suggestionsLoading
  const establishedLinks = linksData?.links || []
  const pendingSuggestions = suggestionsData?.suggestions.filter(s => s.status === 'pending') || []
  const hasContent = establishedLinks.length > 0 || pendingSuggestions.length > 0

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <LinkIcon className="h-4 w-4 text-primary-500" />
              Related Contracts
            </h3>
          </div>
          <div className="card-body flex items-center justify-center py-8">
            <LoadingSpinner size="sm" />
          </div>
        </div>
      </div>
    )
  }

  if (!hasContent) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
            <LinkIcon className="h-4 w-4 text-gray-400" />
            Related Contracts
          </h3>
        </div>
        <div className="card-body text-center py-8">
          <DocumentTextIcon className="h-10 w-10 text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-500">No related contracts found</p>
          <p className="text-xs text-gray-400 mt-1">
            Related documents will be automatically detected when contracts with matching parties or types are uploaded.
          </p>
        </div>
      </div>
    )
  }

  // Group established links by direction
  const parentLinks = establishedLinks.filter(l => l.direction === 'parent')
  const childLinks = establishedLinks.filter(l => l.direction === 'child')

  return (
    <div className="space-y-4">
      {/* Established Links */}
      {establishedLinks.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <ShieldCheckIcon className="h-4 w-4 text-green-500" />
              Established Links
              <span className="bg-green-100 text-green-700 text-xs px-1.5 py-0.5 rounded-full">
                {establishedLinks.length}
              </span>
            </h3>
          </div>
          <div className="card-body space-y-3">
            {parentLinks.length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  Parent Contracts ({parentLinks.length})
                </p>
                <div className="space-y-2">
                  {parentLinks.map(link => (
                    <EstablishedLinkCard key={link.id} link={link} />
                  ))}
                </div>
              </div>
            )}
            {childLinks.length > 0 && (
              <div className={parentLinks.length > 0 ? 'mt-4' : ''}>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                  Child Contracts ({childLinks.length})
                </p>
                <div className="space-y-2">
                  {childLinks.map(link => (
                    <EstablishedLinkCard key={link.id} link={link} />
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Suggestions */}
      {pendingSuggestions.length > 0 && (
        <div className="card border-primary-200 bg-primary-50/30">
          <div className="card-header flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900 flex items-center gap-2">
              <SparklesIcon className="h-4 w-4 text-primary-500" />
              AI-Detected Suggestions
              <span className="bg-primary-100 text-primary-700 text-xs px-1.5 py-0.5 rounded-full">
                {pendingSuggestions.length} pending
              </span>
            </h3>

            <div className="flex items-center gap-2">
              {pendingSuggestions.length > 1 && (
                <button
                  onClick={handleApproveAll}
                  disabled={batchApproveMutation.isPending}
                  className="text-xs text-primary-600 hover:text-primary-800 font-medium"
                >
                  {batchApproveMutation.isPending ? 'Approving...' : 'Approve All'}
                </button>
              )}
            </div>
          </div>

          <div className="card-body space-y-3">
            {pendingSuggestions.map((suggestion) => (
              <SuggestionCard
                key={suggestion.id}
                suggestion={suggestion}
                contractId={contractId}
                onReviewComplete={handleReviewComplete}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
