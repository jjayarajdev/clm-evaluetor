import { useState, useRef, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ChevronRightIcon,
  ChevronDownIcon,
  DocumentTextIcon,
  FolderIcon,
  FolderOpenIcon,
  ArrowsPointingOutIcon,
  XMarkIcon,
  ArrowUturnLeftIcon,
} from '@heroicons/react/24/outline'
import api from '@/lib/api'
import { cn, getRiskColor, getStatusColor } from '@/lib/utils'
import type { ContractTreeNode } from '@/types'

const LINK_TYPE_LABELS: Record<string, string> = {
  sow: 'SOW',
  work_order: 'Work Order',
  service_order: 'Service Order',
  purchase_order: 'Purchase Order',
  amendment: 'Amendment',
  addendum: 'Addendum',
  change_order: 'Change Order',
  modification: 'Modification',
  renewal: 'Renewal',
  exhibit: 'Exhibit',
  schedule: 'Schedule',
  appendix: 'Appendix',
  attachment: 'Attachment',
  supersedes: 'Supersedes',
  references: 'References',
  related: 'Related',
}

interface TreeNodeProps {
  node: ContractTreeNode
  depth: number
  onDragStart: (e: React.DragEvent, nodeId: string) => void
  onDragOver: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent, targetId: string) => void
  onUnlink: (linkId: string) => void
  dragOverId: string | null
  draggingId: string | null
}

function TreeNode({ node, depth, onDragStart, onDragOver, onDrop, onUnlink, dragOverId, draggingId }: TreeNodeProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(depth < 2)
  const hasChildren = node.children.length > 0
  const isDragTarget = dragOverId === node.id && draggingId !== node.id
  const isDragging = draggingId === node.id
  const isChild = depth > 0 && node.link_id

  return (
    <div className={cn(isDragging && 'opacity-40')}>
      <div
        draggable
        onDragStart={(e) => onDragStart(e, node.id)}
        onDragOver={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDragOver(e)
        }}
        onDrop={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onDrop(e, node.id)
        }}
        data-node-id={node.id}
        className={cn(
          'flex items-center gap-2 py-2 px-3 rounded-lg cursor-grab transition-all group',
          'hover:bg-gray-50 active:cursor-grabbing',
          isDragTarget && 'ring-2 ring-primary-400 bg-primary-50',
        )}
        style={{ paddingLeft: `${depth * 24 + 12}px` }}
      >
        {/* Expand/collapse toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            setExpanded(!expanded)
          }}
          className={cn(
            'w-5 h-5 flex items-center justify-center rounded hover:bg-gray-200 transition-colors flex-shrink-0',
            !hasChildren && 'invisible',
          )}
        >
          {expanded ? (
            <ChevronDownIcon className="w-3.5 h-3.5 text-gray-500" />
          ) : (
            <ChevronRightIcon className="w-3.5 h-3.5 text-gray-500" />
          )}
        </button>

        {/* Icon */}
        {hasChildren ? (
          expanded ? (
            <FolderOpenIcon className="w-5 h-5 text-amber-500 flex-shrink-0" />
          ) : (
            <FolderIcon className="w-5 h-5 text-amber-500 flex-shrink-0" />
          )
        ) : (
          <DocumentTextIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
        )}

        {/* Contract name */}
        <Link
          to={`/contracts/${node.id}`}
          draggable={false}
          className="text-sm font-medium text-gray-900 hover:text-primary-700 truncate flex-1 min-w-0"
          onClick={(e) => e.stopPropagation()}
        >
          {node.filename}
        </Link>

        {/* Link type badge (how this relates to its parent) */}
        {node.link_type && (
          <span className="text-[10px] bg-primary-100 text-primary-700 px-1.5 py-0.5 rounded font-medium flex-shrink-0">
            {t(`treeView.linkTypes.${node.link_type}`, { defaultValue: LINK_TYPE_LABELS[node.link_type] || node.link_type })}
          </span>
        )}

        {/* Contract type */}
        {node.contract_type && (
          <span className="text-xs text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded flex-shrink-0 uppercase">
            {node.contract_type}
          </span>
        )}

        {/* Counterparty */}
        {node.counterparty && (
          <span className="text-xs text-gray-500 truncate max-w-[120px] hidden lg:inline flex-shrink-0">
            {node.counterparty}
          </span>
        )}

        {/* Status */}
        {node.status && (
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded font-medium capitalize flex-shrink-0',
            getStatusColor(node.status),
          )}>
            {t(`status.${node.status}`, { defaultValue: node.status })}
          </span>
        )}

        {/* Risk */}
        {node.risk_level && (
          <span className={cn(
            'text-xs px-1.5 py-0.5 rounded font-medium capitalize flex-shrink-0',
            getRiskColor(node.risk_level),
          )}>
            {t(`risk.${node.risk_level}`, { defaultValue: node.risk_level })}
          </span>
        )}

        {/* Child count */}
        {hasChildren && (
          <span className="text-xs text-gray-400 flex-shrink-0">
            {node.children.length}
          </span>
        )}

        {/* Unlink button for child nodes */}
        {isChild && (
          <button
            draggable={false}
            onClick={(e) => {
              e.stopPropagation()
              e.preventDefault()
              onUnlink(node.link_id!)
            }}
            className="p-1 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
            title={t('treeView.removeFromParent')}
          >
            <ArrowUturnLeftIcon className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Children */}
      {expanded && hasChildren && (
        <div className="relative">
          {/* Tree line */}
          <div
            className="absolute top-0 bottom-2 border-l-2 border-gray-200"
            style={{ left: `${depth * 24 + 24}px` }}
          />
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              onDragStart={onDragStart}
              onDragOver={onDragOver}
              onDrop={onDrop}
              onUnlink={onUnlink}
              dragOverId={dragOverId}
              draggingId={draggingId}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface ContractTreeViewProps {
  roots: ContractTreeNode[]
  totalContracts: number
  totalLinks: number
}

export default function ContractTreeView({ roots, totalContracts, totalLinks }: ContractTreeViewProps) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [draggingId, setDraggingId] = useState<string | null>(null)
  const [dragOverId, setDragOverId] = useState<string | null>(null)
  const dragOverRef = useRef<string | null>(null)

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ['contract-hierarchy'] })
    queryClient.invalidateQueries({ queryKey: ['contract-links'] })
    queryClient.invalidateQueries({ queryKey: ['suggested-links'] })
  }

  // Move mutation
  const moveMutation = useMutation({
    mutationFn: (data: { contract_id: string; new_parent_id: string | null; link_type: string }) =>
      api.moveContract(data),
    onSuccess: invalidateAll,
  })

  // Unlink (delete link) mutation
  const unlinkMutation = useMutation({
    mutationFn: (linkId: string) => api.deleteContractLink(linkId),
    onSuccess: invalidateAll,
  })

  const handleDragStart = useCallback((e: React.DragEvent, nodeId: string) => {
    e.dataTransfer.setData('text/plain', nodeId)
    e.dataTransfer.effectAllowed = 'move'
    setDraggingId(nodeId)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    const target = (e.target as HTMLElement).closest('[data-node-id]')
    const id = target?.getAttribute('data-node-id') || null
    if (id !== dragOverRef.current) {
      dragOverRef.current = id
      setDragOverId(id)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent, targetId: string) => {
    const sourceId = e.dataTransfer.getData('text/plain')
    setDraggingId(null)
    setDragOverId(null)
    dragOverRef.current = null

    if (!sourceId || sourceId === targetId) return

    moveMutation.mutate({
      contract_id: sourceId,
      new_parent_id: targetId,
      link_type: 'related',
    })
  }, [moveMutation])

  const handleRootDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const sourceId = e.dataTransfer.getData('text/plain')
    setDraggingId(null)
    setDragOverId(null)
    dragOverRef.current = null

    if (!sourceId) return

    moveMutation.mutate({
      contract_id: sourceId,
      new_parent_id: null,
      link_type: 'related',
    })
  }, [moveMutation])

  const handleUnlink = useCallback((linkId: string) => {
    unlinkMutation.mutate(linkId)
  }, [unlinkMutation])

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-700">
            {t('treeView.contracts', { count: totalContracts })}
          </span>
          {totalLinks > 0 && (
            <span className="text-xs text-gray-400">
              {t('treeView.relationships', { count: totalLinks })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <ArrowsPointingOutIcon className="w-4 h-4" />
          {t('treeView.dragHint')}
        </div>
      </div>

      {/* Always-visible root drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOverId('__root__')
        }}
        onDragLeave={(e) => {
          // Only clear if we're actually leaving the root zone
          const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
          const { clientX, clientY } = e
          if (clientX < rect.left || clientX > rect.right || clientY < rect.top || clientY > rect.bottom) {
            setDragOverId(null)
          }
        }}
        onDrop={handleRootDrop}
        className={cn(
          'mx-3 mt-2 rounded-lg border-2 border-dashed transition-all text-center',
          draggingId
            ? dragOverId === '__root__'
              ? 'border-primary-400 bg-primary-50 py-3'
              : 'border-gray-300 bg-gray-50 py-3'
            : 'border-transparent py-0 h-0 overflow-hidden',
        )}
      >
        {draggingId && (
          <p className={cn(
            'text-xs font-medium',
            dragOverId === '__root__' ? 'text-primary-600' : 'text-gray-400',
          )}>
            {t('treeView.dropToRoot')}
          </p>
        )}
      </div>

      {/* Tree */}
      <div
        className="py-2"
        onDragEnd={() => {
          setDraggingId(null)
          setDragOverId(null)
          dragOverRef.current = null
        }}
      >
        {roots.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <DocumentTextIcon className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p className="text-lg font-medium">{t('treeView.noContracts')}</p>
          </div>
        ) : (
          roots.map((root) => (
            <TreeNode
              key={root.id}
              node={root}
              depth={0}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onUnlink={handleUnlink}
              dragOverId={dragOverId}
              draggingId={draggingId}
            />
          ))
        )}
      </div>

      {/* Feedback */}
      {(moveMutation.isPending || unlinkMutation.isPending) && (
        <div className="px-4 py-2 border-t bg-primary-50 text-sm text-primary-700 text-center">
          {moveMutation.isPending ? t('treeView.movingContract') : t('treeView.removingLink')}
        </div>
      )}
      {(moveMutation.isError || unlinkMutation.isError) && (
        <div className="px-4 py-2 border-t bg-red-50 text-sm text-red-700 flex items-center justify-between">
          <span>
            {moveMutation.isError
              ? t('treeView.failed', { error: (moveMutation.error as any)?.response?.data?.detail || t('treeView.unknownError') })
              : t('treeView.failed', { error: (unlinkMutation.error as any)?.response?.data?.detail || t('treeView.unknownError') })
            }
          </span>
          <button onClick={() => { moveMutation.reset(); unlinkMutation.reset() }} className="p-1 hover:bg-red-100 rounded">
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}
