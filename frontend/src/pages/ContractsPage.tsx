/* Contracts register — Direction B redesign.
   Stat cards (clickable as filters) → search + chips row → table/tree toggle →
   sortable table with row selection and a bulk-action bar. Data fetching, routes,
   filters and delete flow are unchanged from the pre-redesign page. */
import { useState, useRef, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import {
  ArrowUpTrayIcon,
  BuildingOfficeIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  CheckCircleIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  ShareIcon,
  TableCellsIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import api from '@/lib/api'
import i18n from '@/i18n'
import {
  Button,
  Checkbox,
  Chip,
  ConfirmDialog,
  EmptyState,
  Field,
  IconButton,
  Pill,
  Select,
  Stat,
  Table,
  useToast,
} from '@/components/ui'
import type { PillTone, TableColumn, SortState } from '@/components/ui'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ContractTreeView from '@/components/contracts/ContractTreeView'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { useAuth } from '@/contexts/AuthContext'
import { can } from '@/lib/rbac'
import type { ContractSummary } from '@/types'

function currentLocale(): string {
  return i18n.language?.startsWith('fr') ? 'fr-FR' : 'en-US'
}

// ── Helpers ──────────────────────────────────────────────────────

function formatValue(value: number | null, currency: string | null): string {
  if (value == null) return '—'
  const c = currency || 'USD'
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(0)}K`
  return new Intl.NumberFormat(currentLocale(), { style: 'currency', currency: c, maximumFractionDigits: 0 }).format(value)
}

function isOngoing(d: Date): boolean {
  return d.getFullYear() > new Date().getFullYear() + 50
}

function formatExpiry(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  if (isOngoing(d)) return i18n.t('contracts.ongoing')
  return d.toLocaleDateString(currentLocale(), { month: 'short', year: 'numeric' })
}

function daysUntil(dateStr: string): number {
  return Math.round((new Date(dateStr).getTime() - Date.now()) / 86_400_000)
}

function displayName(c: ContractSummary): string {
  return c.filename.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')
}

const STATUS_TONE: Record<string, PillTone> = {
  completed: 'ok',
  active: 'ok',
  processing: 'in',
  under_review: 'p',
  pending: 'n',
  draft: 'n',
  failed: 'da',
  expired: 'da',
}

const RISK_TONE: Record<string, PillTone> = {
  low: 'ok',
  medium: 'wa',
  high: 'da',
  critical: 'da',
}

const RISK_RANK: Record<string, number> = { low: 0, medium: 1, high: 2, critical: 3 }

const STATUS_CHIP_VALUES = ['pending', 'processing', 'completed', 'failed']

function StatusPill({ status }: { status: string }) {
  const { t } = useTranslation()
  const key = status.toLowerCase().replace(/\s+/g, '_')
  return (
    <Pill tone={STATUS_TONE[key] || 'n'}>
      {t(`status.${key}`, { defaultValue: status.replace(/_/g, ' ') })}
    </Pill>
  )
}

function RiskPill({ level }: { level: string }) {
  const { t } = useTranslation()
  const key = level.toLowerCase()
  return (
    <Pill tone={RISK_TONE[key] || 'n'}>
      {t(`risk.${key}`, { defaultValue: level })}
    </Pill>
  )
}

/** Expiry date plus a colored "in Nd / Nd ago" hint when within 90 days or past. */
function ExpiryCell({ dateStr }: { dateStr: string | null }) {
  const { t } = useTranslation()
  const hint = (() => {
    if (!dateStr || isOngoing(new Date(dateStr))) return null
    const d = daysUntil(dateStr)
    if (d < 0) return { text: t('contracts.daysAgo', { count: Math.abs(d), defaultValue: '{{count}}d ago' }), color: 'var(--da)' }
    if (d <= 90) return { text: t('contracts.inDays', { count: d, defaultValue: 'in {{count}}d' }), color: 'var(--wa)' }
    return null
  })()
  return (
    <span className="num nw" style={{ display: 'inline-block' }}>
      {formatExpiry(dateStr)}
      {hint && (
        <span style={{ display: 'block', fontSize: 'var(--fs-xs)', color: hint.color, fontWeight: 600 }}>{hint.text}</span>
      )}
    </span>
  )
}

// ── Page Component ───────────────────────────────────────────────

export default function ContractsPage() {
  const { t } = useTranslation()
  const { contractTypeLabel, uiLabel } = useTenantConfig()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { user } = useAuth()
  const canUpload = can(user, 'upload')
  const { toast } = useToast()
  const [page, setPage] = useState(1)
  // Server-side sort — the register is paginated, so sorting must run over the
  // whole result set on the backend, not just the rows on the current page.
  const [sort, setSort] = useState<SortState | null>(null)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [selectedCounterparty, setSelectedCounterparty] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<string | null>(null)
  const [selectedRisk, setSelectedRisk] = useState<string | null>(null)
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null)
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
  const [showFilters, setShowFilters] = useState(false)
  const [partyDropdownOpen, setPartyDropdownOpen] = useState(false)
  const [partySearch, setPartySearch] = useState('')
  const [clientDropdownOpen, setClientDropdownOpen] = useState(false)
  const [selectedContracts, setSelectedContracts] = useState<Set<string>>(new Set())
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [viewMode, setViewMode] = useState<'table' | 'tree'>('table')
  const pageSize = 10
  const partyDropdownRef = useRef<HTMLDivElement>(null)
  const partyInputRef = useRef<HTMLInputElement>(null)
  const clientDropdownRef = useRef<HTMLDivElement>(null)

  // Fetch filter options
  const { data: filterOptions } = useQuery({
    queryKey: ['contract-filter-options'],
    queryFn: () => api.getContractFilterOptions(),
  })

  // Portfolio summary for the stat cards row
  const { data: summary } = useQuery({
    queryKey: ['contracts-summary'],
    queryFn: () => api.getContractsSummary(),
  })

  // Fetch contracts
  // Table column key → backend sort field.
  const SORT_FIELD: Record<string, string> = {
    name: 'filename', type: 'contract_type', counterparty: 'counterparty',
    status: 'status', value: 'contract_value', risk: 'risk_level', expiry: 'expiration_date',
  }
  const sortBy = sort ? SORT_FIELD[sort.key] : undefined

  const { data, isLoading } = useQuery({
    queryKey: ['contracts', page, search, selectedCounterparty, selectedType, selectedRisk, selectedStatus, selectedClientId, sortBy, sort?.dir],
    queryFn: () => api.getContracts({
      page,
      page_size: pageSize,
      search: search || undefined,
      counterparty: selectedCounterparty || undefined,
      contract_type: selectedType || undefined,
      risk_level: selectedRisk || undefined,
      status: selectedStatus || undefined,
      client_id: selectedClientId || undefined,
      ...(sortBy ? { sort_by: sortBy, sort_desc: sort!.dir === -1 } : {}),
    }),
  })

  // Tree view
  const { data: hierarchyData, isLoading: hierarchyLoading } = useQuery({
    queryKey: ['contract-hierarchy'],
    queryFn: () => api.getContractHierarchy(),
    enabled: viewMode === 'tree',
  })

  // Batch delete
  const deleteMutation = useMutation({
    mutationFn: (contractIds: string[]) => api.batchDeleteContracts(contractIds),
    onSuccess: (res) => {
      setSelectedContracts(new Set())
      setShowDeleteConfirm(false)
      queryClient.invalidateQueries({ queryKey: ['contracts'] })
      queryClient.invalidateQueries({ queryKey: ['contract-filter-options'] })
      queryClient.invalidateQueries({ queryKey: ['contracts-summary'] })
      toast({ text: t('contracts.deleteSuccess', { count: res.total_deleted, defaultValue: '{{count}} contract(s) deleted' }) })
    },
    onError: () => {
      toast({ text: t('contracts.deleteFailed', { defaultValue: 'Delete failed. Please try again.' }), error: true })
    },
  })

  const toggleContractSelection = (contractId: string) => {
    setSelectedContracts(prev => {
      const next = new Set(prev)
      if (next.has(contractId)) next.delete(contractId)
      else next.add(contractId)
      return next
    })
  }

  const toggleAllContracts = () => {
    if (!data?.items) return
    const allSelected = data.items.every(c => selectedContracts.has(c.id))
    setSelectedContracts(prev => {
      const next = new Set(prev)
      data.items.forEach(c => (allSelected ? next.delete(c.id) : next.add(c.id)))
      return next
    })
  }

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (partyDropdownRef.current && !partyDropdownRef.current.contains(event.target as Node)) setPartyDropdownOpen(false)
      if (clientDropdownRef.current && !clientDropdownRef.current.contains(event.target as Node)) setClientDropdownOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (partyDropdownOpen && partyInputRef.current) partyInputRef.current.focus()
  }, [partyDropdownOpen])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const clearFilters = () => {
    setSelectedCounterparty(null)
    setSelectedType(null)
    setSelectedRisk(null)
    setSelectedStatus(null)
    setSelectedClientId(null)
    setPage(1)
  }

  const hasActiveFilters = !!(selectedCounterparty || selectedRisk || selectedStatus || selectedClientId)
  const selectedClient = filterOptions?.clients?.find((c) => c.id === selectedClientId)
  const filteredCounterparties = filterOptions?.counterparties.filter((cp: string) =>
    cp.toLowerCase().includes(partySearch.toLowerCase())
  ) || []

  const toggleStatusFilter = (s: string) => {
    setSelectedStatus(prev => (prev === s ? null : s))
    setPage(1)
  }
  const toggleRiskFilter = (r: string) => {
    setSelectedRisk(prev => (prev === r ? null : r))
    setPage(1)
  }

  // Pagination helpers
  const totalPages = data?.pages || 1
  const startItem = data && data.total > 0 ? (data.page - 1) * pageSize + 1 : 0
  const endItem = data ? Math.min(data.page * pageSize, data.total) : 0

  function getPageNumbers(): (number | '...')[] {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1)
    const pages: (number | '...')[] = [1]
    if (page > 3) pages.push('...')
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i)
    }
    if (page < totalPages - 2) pages.push('...')
    pages.push(totalPages)
    return pages
  }

  // Selection state for the current page
  const items = data?.items || []
  const allSelected = items.length > 0 && items.every(c => selectedContracts.has(c.id))
  const someSelected = !allSelected && items.some(c => selectedContracts.has(c.id))

  const criticalCount = summary?.by_risk?.critical || 0

  const columns: TableColumn<ContractSummary>[] = [
    {
      key: 'sel',
      width: 40,
      header: <Checkbox checked={allSelected} mixed={someSelected} onChange={toggleAllContracts} />,
      render: (c) => (
        <Checkbox checked={selectedContracts.has(c.id)} onChange={() => toggleContractSelection(c.id)} />
      ),
    },
    {
      key: 'name',
      header: t('contracts.contractName'),
      sortable: true,
      sortValue: (c) => displayName(c).toLowerCase(),
      render: (c) => (
        <Link
          to={`/contracts/${c.id}`}
          onClick={(e) => e.stopPropagation()}
          className="trunc"
          style={{ display: 'block', maxWidth: 320, fontWeight: 500, color: 'inherit' }}
        >
          {displayName(c)}
        </Link>
      ),
    },
    {
      key: 'type',
      header: t('contracts.type'),
      sortable: true,
      nowrap: true,
      sortValue: (c) => c.contract_type,
      render: (c) => (
        <span className="muted">{c.contract_type ? contractTypeLabel(c.contract_type) : '—'}</span>
      ),
    },
    {
      key: 'counterparty',
      header: uiLabel('counterparty', t('contracts.counterparty')),
      sortable: true,
      sortValue: (c) => c.counterparty,
      render: (c) => <span className="trunc" style={{ display: 'block', maxWidth: 200 }}>{c.counterparty || '—'}</span>,
    },
    {
      key: 'status',
      header: t('common.status'),
      sortable: true,
      sortValue: (c) => c.status,
      render: (c) => <StatusPill status={c.status} />,
    },
    {
      key: 'value',
      header: uiLabel('contract_value', t('contracts.value')),
      sortable: true,
      align: 'right',
      nowrap: true,
      sortValue: (c) => c.contract_value,
      render: (c) => <span className="num" style={{ fontWeight: 500 }}>{formatValue(c.contract_value, c.currency)}</span>,
    },
    {
      key: 'risk',
      header: t('contracts.risk'),
      sortable: true,
      sortValue: (c) => (c.risk_level ? RISK_RANK[c.risk_level.toLowerCase()] ?? null : null),
      render: (c) => (c.risk_level ? <RiskPill level={c.risk_level} /> : <span className="faint">{'—'}</span>),
    },
    {
      key: 'expiry',
      header: t('contracts.expiry'),
      sortable: true,
      align: 'right',
      nowrap: true,
      sortValue: (c) => c.expiration_date,
      render: (c) => <ExpiryCell dateStr={c.expiration_date} />,
    },
  ]

  const emptyState = (
    <EmptyState
      icon={hasActiveFilters || search ? FunnelIcon : DocumentTextIcon}
      title={
        hasActiveFilters || search
          ? t('contracts.noContractsFound')
          : t('contracts.emptyTitle', { defaultValue: 'No contracts yet' })
      }
      body={
        hasActiveFilters || search
          ? t('contracts.emptyFilteredBody', { defaultValue: 'Loosen or clear a filter to see more of your portfolio.' })
          : t('contracts.emptyBody', { defaultValue: 'Upload your first contract to start the AI extraction pipeline.' })
      }
      action={
        hasActiveFilters || search ? (
          <Button variant="secondary" size="sm" onClick={() => { clearFilters(); setSearch(''); setSearchInput('') }}>
            {t('contracts.clearAllFilters')}
          </Button>
        ) : canUpload ? (
          <Button variant="primary" size="sm" icon={ArrowUpTrayIcon} onClick={() => navigate('/upload')}>
            {t('nav.upload')}
          </Button>
        ) : undefined
      }
    />
  )

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Delete confirmation */}
      <ConfirmDialog
        open={showDeleteConfirm}
        title={t('contracts.deleteConfirmTitle', { count: selectedContracts.size })}
        body={t('contracts.deleteConfirmBody')}
        confirmLabel={deleteMutation.isPending ? t('contracts.deleting') : t('common.delete')}
        cancelLabel={t('common.cancel')}
        onCancel={() => { if (!deleteMutation.isPending) setShowDeleteConfirm(false) }}
        onConfirm={() => { if (!deleteMutation.isPending) deleteMutation.mutate(Array.from(selectedContracts)) }}
      />

      {/* Header */}
      <div className="row" style={{ alignItems: 'flex-start' }}>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('nav.contracts')}</h1>
          <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('contracts.subtitle')}</p>
        </div>
        {canUpload && (
          <Button variant="primary" icon={ArrowUpTrayIcon} onClick={() => navigate('/upload')}>
            {t('nav.upload')}
          </Button>
        )}
      </div>

      {/* Stat cards — the two rightmost double as filters */}
      <div className="grid gap-3 grid-cols-2 lg:grid-cols-4">
        <Stat
          icon={DocumentTextIcon}
          label={t('contracts.statTotal', { defaultValue: 'Contracts' })}
          value={summary ? summary.total_contracts : '—'}
          sub={t('contracts.statTotalSub', { defaultValue: 'across your portfolio' })}
        />
        <Stat
          icon={CheckCircleIcon}
          label={t('contracts.statAnalyzed', { defaultValue: 'Fully analyzed' })}
          value={summary ? summary.by_status?.completed || 0 : '—'}
          sub={t('contracts.statAnalyzedSub', {
            count: summary?.by_status?.processing || 0,
            defaultValue: '{{count}} still processing',
          })}
          active={selectedStatus === 'completed'}
          onClick={() => toggleStatusFilter('completed')}
        />
        <Stat
          icon={ClockIcon}
          label={t('contracts.statExpiring', { defaultValue: 'Expiring soon' })}
          value={summary ? summary.expiring_soon : '—'}
          sub={t('contracts.statExpiringSub', { defaultValue: 'approaching expiration' })}
          subTone="var(--wa)"
        />
        <Stat
          icon={ExclamationTriangleIcon}
          label={t('contracts.statHighRisk', { defaultValue: 'High risk' })}
          value={summary ? summary.by_risk?.high || 0 : '—'}
          sub={
            criticalCount > 0
              ? t('contracts.statCritical', { count: criticalCount, defaultValue: '+{{count}} critical' })
              : t('contracts.statHighRiskSub', { defaultValue: 'needing review' })
          }
          subTone="var(--da)"
          active={selectedRisk === 'high'}
          onClick={() => toggleRiskFilter('high')}
        />
      </div>

      {/* Search + controls row */}
      <div className="col" style={{ gap: 10 }}>
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <form onSubmit={handleSearch} className="grow" style={{ maxWidth: 340, minWidth: 220 }}>
            <Field
              icon={MagnifyingGlassIcon}
              placeholder={t('contracts.searchPlaceholder')}
              value={searchInput}
              onChange={(e) => {
                const v = e.target.value
                setSearchInput(v)
                // Clearing the box should immediately restore the full list —
                // don't make the user press Enter on an empty query.
                if (v.trim() === '' && search !== '') {
                  setSearch('')
                  setPage(1)
                }
              }}
            />
          </form>
          <Select
            value={selectedType || ''}
            onChange={(e) => { setSelectedType(e.target.value || null); setPage(1) }}
            containerStyle={{ width: 170 }}
            options={[
              { value: '', label: t('contracts.all') },
              ...(filterOptions?.contract_types || []).map((type: string) => ({ value: type, label: contractTypeLabel(type) })),
            ]}
          />
          <Chip on={showFilters || hasActiveFilters} icon={FunnelIcon} onClick={() => setShowFilters(!showFilters)}>
            {t('contracts.filters')}
          </Chip>
          <span className="grow" />
          {/* Table / tree segmented toggle */}
          <div className="row" style={{ gap: 2, padding: 2, background: 'var(--s2)', borderRadius: 'var(--r-sm)' }}>
            {([
              ['table', TableCellsIcon, t('contracts.tableView')],
              ['tree', ShareIcon, t('contracts.treeView')],
            ] as const).map(([mode, Icon, label]) => (
              <button
                key={mode}
                type="button"
                onClick={() => setViewMode(mode)}
                title={label}
                className="row"
                style={{
                  gap: 6, height: 28, padding: '0 10px', border: 0, borderRadius: 'var(--r-xs)', cursor: 'pointer',
                  background: viewMode === mode ? 'var(--s)' : 'transparent',
                  boxShadow: viewMode === mode ? 'var(--sh-xs)' : 'none',
                  color: viewMode === mode ? 'var(--t)' : 'var(--m)',
                  fontSize: 'var(--fs-sm)', fontWeight: 600,
                }}
              >
                <Icon style={{ width: 14, height: 14 }} aria-hidden />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Status filter chips */}
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          {STATUS_CHIP_VALUES.map((s) => (
            <Chip key={s} on={selectedStatus === s} onClick={() => toggleStatusFilter(s)}>
              {t(`status.${s}`)}
            </Chip>
          ))}
          {hasActiveFilters && (
            <Button variant="ghost" size="sm" icon={XMarkIcon} onClick={clearFilters}>
              {t('contracts.clearAllFilters')}
            </Button>
          )}
        </div>
      </div>

      {/* Advanced filter panel */}
      {showFilters && (
        <div className="card card-p">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Client filter */}
            <div>
              <label className="lbl">{t('contracts.client')}</label>
              <div style={{ position: 'relative' }} ref={clientDropdownRef}>
                <button
                  type="button"
                  className="inp"
                  onClick={() => setClientDropdownOpen(!clientDropdownOpen)}
                  style={{ width: '100%', cursor: 'pointer', textAlign: 'left' }}
                >
                  <BuildingOfficeIcon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                  <span
                    className="grow trunc"
                    style={{ fontSize: 'var(--fs-md)', color: selectedClient ? 'var(--t)' : 'var(--m)', fontWeight: selectedClient ? 500 : 400 }}
                  >
                    {selectedClient ? selectedClient.name : t('contracts.allClients')}
                  </span>
                  {selectedClientId && (
                    <IconButton
                      icon={XMarkIcon}
                      label={t('contracts.clearAllFilters')}
                      size="sm"
                      onClick={(e) => { e.stopPropagation(); setSelectedClientId(null); setPage(1) }}
                    />
                  )}
                  <ChevronDownIcon
                    style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)', transition: 'transform .12s', transform: clientDropdownOpen ? 'rotate(180deg)' : undefined }}
                    aria-hidden
                  />
                </button>
                {clientDropdownOpen && (
                  <div className="menu" style={{ top: '100%', left: 0, right: 0, marginTop: 4, maxHeight: 240, overflowY: 'auto' }}>
                    <div
                      className="mi"
                      onClick={() => { setSelectedClientId(null); setClientDropdownOpen(false); setPage(1) }}
                      style={!selectedClientId ? { background: 'var(--p-f)', color: 'var(--p)', fontWeight: 600 } : undefined}
                    >
                      {t('contracts.allClients')}
                    </div>
                    {filterOptions?.clients?.map((client) => (
                      <div
                        key={client.id}
                        className="mi"
                        onClick={() => { setSelectedClientId(client.id); setClientDropdownOpen(false); setPage(1) }}
                        style={selectedClientId === client.id ? { background: 'var(--p-f)', color: 'var(--p)', fontWeight: 600 } : undefined}
                      >
                        <span className="grow trunc">
                          {client.name} <span className="faint">({client.code})</span>
                        </span>
                        <span className="faint num" style={{ fontSize: 'var(--fs-xs)' }}>{client.contract_count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Counterparty filter */}
            <div>
              <label className="lbl">{uiLabel('counterparty', t('contracts.counterparty'))}</label>
              <div style={{ position: 'relative' }} ref={partyDropdownRef}>
                <button
                  type="button"
                  className="inp"
                  onClick={() => setPartyDropdownOpen(!partyDropdownOpen)}
                  style={{ width: '100%', cursor: 'pointer', textAlign: 'left' }}
                >
                  <BuildingOfficeIcon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                  <span
                    className="grow trunc"
                    style={{ fontSize: 'var(--fs-md)', color: selectedCounterparty ? 'var(--t)' : 'var(--m)', fontWeight: selectedCounterparty ? 500 : 400 }}
                  >
                    {selectedCounterparty || t('contracts.allParties')}
                  </span>
                  {selectedCounterparty && (
                    <IconButton
                      icon={XMarkIcon}
                      label={t('contracts.clearAllFilters')}
                      size="sm"
                      onClick={(e) => { e.stopPropagation(); setSelectedCounterparty(null); setPage(1) }}
                    />
                  )}
                  <ChevronDownIcon
                    style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)', transition: 'transform .12s', transform: partyDropdownOpen ? 'rotate(180deg)' : undefined }}
                    aria-hidden
                  />
                </button>
                {partyDropdownOpen && (
                  <div className="menu" style={{ top: '100%', left: 0, right: 0, marginTop: 4 }}>
                    <div style={{ padding: 4, borderBottom: '1px solid var(--b)', marginBottom: 4 }}>
                      <div className="inp" style={{ height: 30 }}>
                        <MagnifyingGlassIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                        <input
                          ref={partyInputRef}
                          type="text"
                          placeholder={t('contracts.searchParties')}
                          value={partySearch}
                          onChange={(e) => setPartySearch(e.target.value)}
                        />
                      </div>
                    </div>
                    <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                      <div
                        className="mi"
                        onClick={() => { setSelectedCounterparty(null); setPartyDropdownOpen(false); setPartySearch(''); setPage(1) }}
                        style={!selectedCounterparty ? { background: 'var(--p-f)', color: 'var(--p)', fontWeight: 600 } : undefined}
                      >
                        {t('contracts.allParties')}
                      </div>
                      {filteredCounterparties.map((party: string) => (
                        <div
                          key={party}
                          className="mi"
                          onClick={() => { setSelectedCounterparty(party); setPartyDropdownOpen(false); setPartySearch(''); setPage(1) }}
                          style={selectedCounterparty === party ? { background: 'var(--p-f)', color: 'var(--p)', fontWeight: 600 } : undefined}
                        >
                          <span className="trunc">{party}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Risk level filter */}
            <Select
              label={t('contracts.riskLevel')}
              value={selectedRisk || ''}
              onChange={(e) => { setSelectedRisk(e.target.value || null); setPage(1) }}
              options={[
                { value: '', label: t('contracts.allRiskLevels') },
                ...(filterOptions?.risk_levels || []).map((risk: string) => ({
                  value: risk,
                  label: t(`risk.${risk.toLowerCase()}`, { defaultValue: risk }),
                })),
              ]}
            />
          </div>
        </div>
      )}

      {/* Bulk-action bar */}
      {selectedContracts.size > 0 && (
        <div className="row banner banner-p" style={{ gap: 12, alignItems: 'center' }}>
          <b>{t('contracts.selectedCount', { count: selectedContracts.size, defaultValue: '{{count}} selected' })}</b>
          <span className="grow" />
          <Button variant="ghost" size="sm" onClick={() => setSelectedContracts(new Set())}>
            {t('contracts.deselect', { defaultValue: 'Deselect' })}
          </Button>
          <Button variant="danger-ghost" size="sm" icon={TrashIcon} onClick={() => setShowDeleteConfirm(true)}>
            {t('common.delete')}
          </Button>
        </div>
      )}

      {/* Tree view */}
      {viewMode === 'tree' && (
        hierarchyLoading ? (
          <div className="row" style={{ justifyContent: 'center', height: 256 }}><LoadingSpinner size="lg" /></div>
        ) : hierarchyData ? (
          <ContractTreeView roots={hierarchyData.roots} totalContracts={hierarchyData.total_contracts} totalLinks={hierarchyData.total_links} />
        ) : null
      )}

      {/* Table view */}
      {viewMode === 'table' && (isLoading ? (
        <div className="row" style={{ justifyContent: 'center', height: 256 }}><LoadingSpinner size="lg" /></div>
      ) : (
        <div className="col" style={{ gap: 12 }}>
          <Table<ContractSummary>
            columns={columns}
            rows={items}
            rowKey={(c) => c.id}
            onRowClick={(c) => navigate(`/contracts/${c.id}`)}
            empty={emptyState}
            sortState={sort}
            onSortChange={(next) => { setSort(next); setPage(1) }}
          />

          {/* Pagination */}
          {data && data.pages > 1 && (
            <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
              <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
                {t('contracts.showingRange', { start: startItem, end: endItem, total: data.total })}
              </span>
              <span className="grow" />
              <div className="row" style={{ gap: 2 }}>
                <IconButton
                  icon={ChevronLeftIcon}
                  label={t('contracts.previousPage', { defaultValue: 'Previous page' })}
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                />
                {getPageNumbers().map((p, i) =>
                  p === '...' ? (
                    <span key={`dots-${i}`} className="faint" style={{ padding: '0 6px', fontSize: 'var(--fs-sm)' }}>&hellip;</span>
                  ) : (
                    <Button
                      key={p}
                      variant={page === p ? 'primary' : 'ghost'}
                      size="sm"
                      onClick={() => setPage(p as number)}
                      style={{ minWidth: 30, justifyContent: 'center' }}
                    >
                      {p}
                    </Button>
                  )
                )}
                <IconButton
                  icon={ChevronRightIcon}
                  label={t('contracts.nextPage', { defaultValue: 'Next page' })}
                  size="sm"
                  disabled={page === totalPages}
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
