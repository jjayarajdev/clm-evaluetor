import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  SignalIcon,
  FolderIcon,
  FolderOpenIcon,
  DocumentIcon,
  CloudArrowDownIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'
import { client } from '@/lib/api/client'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/utils'

// ── Types ─────────────────────────────────────────────────────────────

interface SPConfig {
  id: string
  name: string
  is_active: boolean
  health_status: string
  last_health_check: string | null
  last_health_message: string | null
  total_requests: number
  failed_requests: number
  azure_tenant_id: string | null
  config: Record<string, unknown> | null
  created_at: string | null
}

interface SPSite {
  id: string
  name: string
  display_name: string | null
  web_url: string | null
}

interface SPDrive {
  id: string
  name: string
  description: string | null
  web_url: string | null
  item_count: number | null
}

interface SPFolderItem {
  id: string
  name: string
  size: number | null
  is_folder: boolean
  mime_type: string | null
  last_modified: string | null
  web_url: string | null
  child_count: number | null
}

interface ImportStatus {
  job_id: string
  status: string
  total_files: number
  imported: number
  skipped: number
  failed: number
  errors: string[]
  started_at: string | null
  completed_at: string | null
}

// ── API calls ─────────────────────────────────────────────────────────

const spApi = {
  getConfig: async (): Promise<SPConfig | null> => {
    const resp = await client.get('/integrations/sharepoint/config')
    return resp.data
  },
  saveConfig: async (data: {
    name: string
    credentials: { azure_tenant_id: string; client_id: string; client_secret: string }
    config?: Record<string, unknown>
  }): Promise<SPConfig> => {
    const resp = await client.post('/integrations/sharepoint/config', data)
    return resp.data
  },
  testConnection: async (): Promise<{ healthy: boolean; message: string }> => {
    const resp = await client.post('/integrations/sharepoint/config/test')
    return resp.data
  },
  disconnect: async (): Promise<void> => {
    await client.delete('/integrations/sharepoint/config')
  },
  searchSites: async (q: string): Promise<SPSite[]> => {
    const resp = await client.get('/integrations/sharepoint/sites', { params: { q } })
    return resp.data
  },
  listDrives: async (siteId: string): Promise<SPDrive[]> => {
    const resp = await client.get(`/integrations/sharepoint/sites/${siteId}/drives`)
    return resp.data
  },
  browseDrive: async (driveId: string, path: string): Promise<SPFolderItem[]> => {
    const resp = await client.get(`/integrations/sharepoint/drives/${driveId}/browse`, { params: { path } })
    return resp.data
  },
  importFolder: async (data: {
    drive_id: string
    folder_path: string
    recursive: boolean
    file_types: string[]
    client_id?: string
  }): Promise<ImportStatus> => {
    const resp = await client.post('/integrations/sharepoint/import', data)
    return resp.data
  },
  getImportStatus: async (jobId: string): Promise<ImportStatus> => {
    const resp = await client.get(`/integrations/sharepoint/import/${jobId}`)
    return resp.data
  },
}

// ── Health Badge ──────────────────────────────────────────────────────

const HEALTH_CONFIG: Record<string, { color: string; icon: typeof CheckCircleIcon; label: string }> = {
  healthy: { color: 'bg-green-100 text-green-700', icon: CheckCircleIcon, label: 'Connected' },
  degraded: { color: 'bg-yellow-100 text-yellow-700', icon: ExclamationTriangleIcon, label: 'Degraded' },
  unhealthy: { color: 'bg-red-100 text-red-700', icon: XCircleIcon, label: 'Unhealthy' },
  unknown: { color: 'bg-gray-100 text-gray-600', icon: SignalIcon, label: 'Not tested' },
}

function HealthBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const cfg = HEALTH_CONFIG[status] || HEALTH_CONFIG.unknown
  const Icon = cfg.icon
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium', cfg.color)}>
      <Icon className="h-3.5 w-3.5" />
      {t(`integrations.sharepoint.health.${status}`, { defaultValue: cfg.label })}
    </span>
  )
}

// ── Main Component ────────────────────────────────────────────────────

type View = 'config' | 'browse' | 'importing'

export default function SharePointIntegrationPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [view, setView] = useState<View>('config')
  const [isEditing, setIsEditing] = useState(false)
  const [testResult, setTestResult] = useState<{ healthy: boolean; message: string } | null>(null)

  // Config form
  const [formName, setFormName] = useState('SharePoint')
  const [formAzureTenant, setFormAzureTenant] = useState('')
  const [formClientId, setFormClientId] = useState('')
  const [formClientSecret, setFormClientSecret] = useState('')

  // Browse state
  const [siteSearch, setSiteSearch] = useState('')
  const [selectedSite, setSelectedSite] = useState<SPSite | null>(null)
  const [selectedDrive, setSelectedDrive] = useState<SPDrive | null>(null)
  const [folderPath, setFolderPath] = useState('root')
  const [folderHistory, setFolderHistory] = useState<string[]>([])

  // Import state
  const [importJobId, setImportJobId] = useState<string | null>(null)

  // ── Queries ──────────────────────────────────────────────────────

  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: ['sp-config'],
    queryFn: spApi.getConfig,
  })

  const { data: sites, isFetching: sitesLoading } = useQuery({
    queryKey: ['sp-sites', siteSearch],
    queryFn: () => spApi.searchSites(siteSearch),
    enabled: view === 'browse' && siteSearch.length >= 2,
  })

  const { data: drives, isFetching: drivesLoading } = useQuery({
    queryKey: ['sp-drives', selectedSite?.id],
    queryFn: () => spApi.listDrives(selectedSite!.id),
    enabled: !!selectedSite,
  })

  const { data: folderItems, isFetching: folderLoading } = useQuery({
    queryKey: ['sp-folder', selectedDrive?.id, folderPath],
    queryFn: () => spApi.browseDrive(selectedDrive!.id, folderPath),
    enabled: !!selectedDrive,
  })

  const { data: importStatus } = useQuery({
    queryKey: ['sp-import', importJobId],
    queryFn: () => spApi.getImportStatus(importJobId!),
    enabled: !!importJobId && view === 'importing',
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' || status === 'pending' ? 2000 : false
    },
  })

  // ── Mutations ────────────────────────────────────────────────────

  const saveMutation = useMutation({
    mutationFn: () =>
      spApi.saveConfig({
        name: formName,
        credentials: {
          azure_tenant_id: formAzureTenant,
          client_id: formClientId,
          client_secret: formClientSecret,
        },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sp-config'] })
      setIsEditing(false)
      setTestResult(null)
    },
  })

  const testMutation = useMutation({
    mutationFn: spApi.testConnection,
    onSuccess: (result) => {
      setTestResult(result)
      queryClient.invalidateQueries({ queryKey: ['sp-config'] })
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: spApi.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sp-config'] })
      setView('config')
    },
  })

  const importMutation = useMutation({
    mutationFn: () =>
      spApi.importFolder({
        drive_id: selectedDrive!.id,
        folder_path: folderPath,
        recursive: true,
        file_types: ['.pdf', '.docx'],
      }),
    onSuccess: (result) => {
      setImportJobId(result.job_id)
      setView('importing')
    },
  })

  // ── Handlers ─────────────────────────────────────────────────────

  const startEditing = () => {
    setFormName(config?.name || 'SharePoint')
    setFormAzureTenant(config?.azure_tenant_id || '')
    setFormClientId('')
    setFormClientSecret('')
    setIsEditing(true)
    setTestResult(null)
  }

  const navigateToFolder = (folderName: string) => {
    setFolderHistory((prev) => [...prev, folderPath])
    setFolderPath(folderPath === 'root' ? folderName : `${folderPath}/${folderName}`)
  }

  const navigateBack = () => {
    const prev = folderHistory[folderHistory.length - 1] || 'root'
    setFolderHistory((h) => h.slice(0, -1))
    setFolderPath(prev)
  }

  // ── Loading ──────────────────────────────────────────────────────

  if (configLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // ── Import Status View ───────────────────────────────────────────

  if (view === 'importing' && importStatus) {
    const pct = importStatus.total_files > 0
      ? Math.round(((importStatus.imported + importStatus.skipped + importStatus.failed) / importStatus.total_files) * 100)
      : 0
    const isDone = importStatus.status === 'completed' || importStatus.status === 'failed'

    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <CloudArrowDownIcon className="h-6 w-6 text-primary-600" />
          <h1 className="text-xl font-semibold text-gray-900">{t('integrations.sharepoint.importTitle')}</h1>
        </div>

        <div className="bg-white rounded-lg border p-6 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">{t('common.status')}</span>
            <span className={cn(
              'text-sm font-medium px-2.5 py-0.5 rounded-full',
              importStatus.status === 'completed' ? 'bg-green-100 text-green-700' :
              importStatus.status === 'failed' ? 'bg-red-100 text-red-700' :
              'bg-blue-100 text-blue-700'
            )}>
              {importStatus.status === 'running' ? t('integrations.sharepoint.importing') : t(`status.${importStatus.status}`, { defaultValue: importStatus.status })}
            </span>
          </div>

          {/* Progress bar */}
          <div>
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>{t('integrations.sharepoint.filesProgress', { done: importStatus.imported + importStatus.skipped + importStatus.failed, total: importStatus.total_files })}</span>
              <span>{pct}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className={cn('h-2 rounded-full transition-all', isDone ? 'bg-green-500' : 'bg-primary-500')}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-4 pt-2">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{importStatus.imported}</div>
              <div className="text-xs text-gray-500">{t('integrations.sharepoint.imported')}</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-400">{importStatus.skipped}</div>
              <div className="text-xs text-gray-500">{t('integrations.sharepoint.skipped')}</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-500">{importStatus.failed}</div>
              <div className="text-xs text-gray-500">{t('integrations.failed')}</div>
            </div>
          </div>

          {/* Errors */}
          {importStatus.errors.length > 0 && (
            <div className="mt-3 bg-red-50 rounded-md p-3">
              <p className="text-xs font-medium text-red-700 mb-1">{t('integrations.sharepoint.errorsLabel')}</p>
              <ul className="text-xs text-red-600 space-y-0.5">
                {importStatus.errors.slice(0, 10).map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
                {importStatus.errors.length > 10 && (
                  <li>{t('integrations.sharepoint.moreErrors', { count: importStatus.errors.length - 10 })}</li>
                )}
              </ul>
            </div>
          )}

          {isDone && (
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => { setView('browse'); setImportJobId(null) }}
                className="px-4 py-2 text-sm font-medium rounded-md bg-primary-600 text-white hover:bg-primary-700"
              >
                {t('integrations.sharepoint.importMore')}
              </button>
              <a
                href="/contracts"
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                {t('integrations.sharepoint.viewContracts')}
              </a>
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Browse View ──────────────────────────────────────────────────

  if (view === 'browse') {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => setView('config')} className="text-gray-500 hover:text-gray-700">
              <ArrowLeftIcon className="h-5 w-5" />
            </button>
            <FolderOpenIcon className="h-6 w-6 text-primary-600" />
            <h1 className="text-xl font-semibold text-gray-900">{t('integrations.sharepoint.browseTitle')}</h1>
          </div>
        </div>

        {/* Step 1: Search for site */}
        {!selectedSite && (
          <div className="bg-white rounded-lg border p-6 space-y-4">
            <h3 className="text-sm font-medium text-gray-700">{t('integrations.sharepoint.findSite')}</h3>
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder={t('integrations.sharepoint.searchSitesPlaceholder')}
                value={siteSearch}
                onChange={(e) => setSiteSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
              />
            </div>
            {sitesLoading && <LoadingSpinner size="sm" />}
            {sites && sites.length > 0 && (
              <div className="space-y-1">
                {sites.map((site) => (
                  <button
                    key={site.id}
                    onClick={() => setSelectedSite(site)}
                    className="w-full flex items-center gap-3 px-3 py-2.5 text-left rounded-md hover:bg-primary-50 transition-colors"
                  >
                    <FolderIcon className="h-5 w-5 text-primary-500 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">{site.display_name || site.name}</p>
                      {site.web_url && <p className="text-xs text-gray-500 truncate">{site.web_url}</p>}
                    </div>
                    <ChevronRightIcon className="h-4 w-4 text-gray-400 ml-auto shrink-0" />
                  </button>
                ))}
              </div>
            )}
            {sites && sites.length === 0 && siteSearch.length >= 2 && (
              <p className="text-sm text-gray-500">{t('integrations.sharepoint.noSitesFound', { query: siteSearch })}</p>
            )}
          </div>
        )}

        {/* Step 2: Select document library */}
        {selectedSite && !selectedDrive && (
          <div className="bg-white rounded-lg border p-6 space-y-4">
            <div className="flex items-center gap-2">
              <button onClick={() => setSelectedSite(null)} className="text-gray-400 hover:text-gray-600">
                <ArrowLeftIcon className="h-4 w-4" />
              </button>
              <h3 className="text-sm font-medium text-gray-700">
                {t('integrations.sharepoint.documentLibrariesIn')} <span className="text-primary-600">{selectedSite.display_name || selectedSite.name}</span>
              </h3>
            </div>
            {drivesLoading && <LoadingSpinner size="sm" />}
            {drives && drives.map((drive) => (
              <button
                key={drive.id}
                onClick={() => { setSelectedDrive(drive); setFolderPath('root'); setFolderHistory([]) }}
                className="w-full flex items-center gap-3 px-3 py-2.5 text-left rounded-md hover:bg-primary-50 border border-gray-100"
              >
                <FolderIcon className="h-5 w-5 text-amber-500 shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900">{drive.name}</p>
                  {drive.description && <p className="text-xs text-gray-500 truncate">{drive.description}</p>}
                </div>
                <ChevronRightIcon className="h-4 w-4 text-gray-400 ml-auto shrink-0" />
              </button>
            ))}
          </div>
        )}

        {/* Step 3: Browse folder contents */}
        {selectedDrive && (
          <div className="bg-white rounded-lg border p-4 space-y-3">
            {/* Breadcrumb */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => { setSelectedDrive(null); setFolderPath('root'); setFolderHistory([]) }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <ArrowLeftIcon className="h-4 w-4" />
                </button>
                <span className="text-gray-500">{selectedDrive.name}</span>
                {folderPath !== 'root' && (
                  <>
                    <span className="text-gray-300">/</span>
                    <span className="text-gray-900 font-medium">{folderPath}</span>
                  </>
                )}
              </div>
              <button
                onClick={() => importMutation.mutate()}
                disabled={importMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
              >
                <CloudArrowDownIcon className="h-4 w-4" />
                {importMutation.isPending ? t('integrations.sharepoint.starting') : t('integrations.sharepoint.importThisFolder')}
              </button>
            </div>

            {/* Back button when in subfolder */}
            {folderPath !== 'root' && (
              <button
                onClick={navigateBack}
                className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 rounded-md hover:bg-gray-50"
              >
                <ArrowLeftIcon className="h-3.5 w-3.5" />
                {t('integrations.sharepoint.back')}
              </button>
            )}

            {folderLoading && <LoadingSpinner size="sm" />}

            {/* Items list */}
            {folderItems && (
              <div className="divide-y">
                {/* Folders first */}
                {folderItems.filter(i => i.is_folder).map((item) => (
                  <button
                    key={item.id}
                    onClick={() => navigateToFolder(item.name)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50"
                  >
                    <FolderIcon className="h-5 w-5 text-amber-400 shrink-0" />
                    <span className="text-sm text-gray-900 truncate">{item.name}</span>
                    {item.child_count != null && (
                      <span className="text-xs text-gray-400 ml-auto">{t('integrations.sharepoint.itemsCount', { count: item.child_count })}</span>
                    )}
                    <ChevronRightIcon className="h-4 w-4 text-gray-300 shrink-0" />
                  </button>
                ))}
                {/* Then files */}
                {folderItems.filter(i => !i.is_folder).map((item) => {
                  const ext = item.name.split('.').pop()?.toLowerCase() || ''
                  const isSupported = ['pdf', 'docx', 'doc', 'xlsx', 'pptx'].includes(ext)
                  return (
                    <div
                      key={item.id}
                      className={cn('flex items-center gap-3 px-3 py-2', !isSupported && 'opacity-40')}
                    >
                      <DocumentIcon className={cn('h-5 w-5 shrink-0', isSupported ? 'text-blue-400' : 'text-gray-300')} />
                      <span className="text-sm text-gray-700 truncate">{item.name}</span>
                      <span className="text-xs text-gray-400 ml-auto whitespace-nowrap">
                        {item.size ? `${(item.size / 1024).toFixed(0)} KB` : ''}
                      </span>
                    </div>
                  )
                })}
                {folderItems.length === 0 && (
                  <p className="text-sm text-gray-500 py-4 text-center">{t('integrations.sharepoint.emptyFolder')}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  // ── Config View (default) ────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary-100 flex items-center justify-center">
            <svg className="h-6 w-6 text-primary-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{t('integrations.sharepoint.title')}</h1>
            <p className="text-sm text-gray-500">{t('integrations.sharepoint.subtitle')}</p>
          </div>
        </div>
        {config && config.is_active && (
          <HealthBadge status={config.health_status} />
        )}
      </div>

      {/* Connection Card */}
      <div className="bg-white rounded-lg border p-6">
        {!config || !config.is_active || isEditing ? (
          // Setup / Edit form
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-gray-700">
              {config ? t('integrations.sharepoint.updateConnection') : t('integrations.sharepoint.connectTitle')}
            </h3>
            <p className="text-xs text-gray-500">
              {t('integrations.sharepoint.setupHintPrefix')} <code className="bg-gray-100 px-1 rounded">Sites.Read.All</code> {t('integrations.sharepoint.setupHintSuffix')}
            </p>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">{t('integrations.sharepoint.connectionName')}</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500"
                  placeholder="SharePoint"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t('integrations.sharepoint.azureTenantId')}</label>
                <input
                  type="text"
                  value={formAzureTenant}
                  onChange={(e) => setFormAzureTenant(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500 font-mono"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">{t('integrations.sharepoint.appClientId')}</label>
                <input
                  type="text"
                  value={formClientId}
                  onChange={(e) => setFormClientId(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500 font-mono"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-gray-600 mb-1">{t('integrations.sharepoint.clientSecret')}</label>
                <input
                  type="password"
                  value={formClientSecret}
                  onChange={(e) => setFormClientSecret(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500 font-mono"
                  placeholder={t('integrations.sharepoint.clientSecretPlaceholder')}
                />
              </div>
            </div>

            {testResult && (
              <div className={cn(
                'flex items-center gap-2 p-3 rounded-md text-sm',
                testResult.healthy ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
              )}>
                {testResult.healthy ? <CheckCircleIcon className="h-5 w-5" /> : <XCircleIcon className="h-5 w-5" />}
                {testResult.message}
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending || !formAzureTenant || !formClientId || !formClientSecret}
                className="px-4 py-2 text-sm font-medium rounded-md bg-primary-600 text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {saveMutation.isPending ? t('integrations.saving') : t('integrations.sharepoint.saveAndConnect')}
              </button>
              {isEditing && (
                <button
                  onClick={() => setIsEditing(false)}
                  className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
                >
                  {t('common.cancel')}
                </button>
              )}
            </div>
          </div>
        ) : (
          // Connected state
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-gray-900">{config.name}</h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {t('integrations.sharepoint.azureTenant')}: <span className="font-mono">{config.azure_tenant_id}</span>
                </p>
              </div>
              <HealthBadge status={config.health_status} />
            </div>

            <div className="grid grid-cols-3 gap-4 py-2">
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">{config.total_requests}</div>
                <div className="text-xs text-gray-500">{t('integrations.sharepoint.apiCalls')}</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-900">{config.total_requests - config.failed_requests}</div>
                <div className="text-xs text-gray-500">{t('integrations.sharepoint.successful')}</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-red-500">{config.failed_requests}</div>
                <div className="text-xs text-gray-500">{t('integrations.failed')}</div>
              </div>
            </div>

            <div className="flex gap-2 pt-2 border-t">
              <button
                onClick={() => setView('browse')}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md bg-primary-600 text-white hover:bg-primary-700"
              >
                <FolderOpenIcon className="h-4 w-4" />
                {t('integrations.sharepoint.browseAndImport')}
              </button>
              <button
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                <ArrowPathIcon className={cn('h-4 w-4', testMutation.isPending && 'animate-spin')} />
                {t('integrations.test')}
              </button>
              <button
                onClick={() => startEditing()}
                className="px-4 py-2 text-sm font-medium rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50"
              >
                {t('common.edit')}
              </button>
              <button
                onClick={() => { if (confirm(t('integrations.sharepoint.disconnectConfirm'))) disconnectMutation.mutate() }}
                className="px-4 py-2 text-sm font-medium rounded-md border border-red-200 text-red-600 hover:bg-red-50 ml-auto"
              >
                {t('integrations.sharepoint.disconnect')}
              </button>
            </div>

            {testResult && (
              <div className={cn(
                'flex items-center gap-2 p-3 rounded-md text-sm',
                testResult.healthy ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
              )}>
                {testResult.healthy ? <CheckCircleIcon className="h-5 w-5" /> : <XCircleIcon className="h-5 w-5" />}
                {testResult.message}
              </div>
            )}
          </div>
        )}
      </div>

      {/* How it works */}
      {(!config || !config.is_active) && (
        <div className="bg-primary-50 rounded-lg border border-primary-100 p-5">
          <h3 className="text-sm font-semibold text-primary-900 mb-3">{t('integrations.sharepoint.howItWorks')}</h3>
          <ol className="space-y-2 text-sm text-primary-800">
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary-200 text-primary-700 text-xs flex items-center justify-center font-bold">1</span>
              {t('integrations.sharepoint.step1Prefix')} <strong>Sites.Read.All</strong> {t('integrations.sharepoint.step1Suffix')}
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary-200 text-primary-700 text-xs flex items-center justify-center font-bold">2</span>
              {t('integrations.sharepoint.step2')}
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary-200 text-primary-700 text-xs flex items-center justify-center font-bold">3</span>
              {t('integrations.sharepoint.step3')}
            </li>
            <li className="flex gap-2">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary-200 text-primary-700 text-xs flex items-center justify-center font-bold">4</span>
              {t('integrations.sharepoint.step4')}
            </li>
          </ol>
        </div>
      )}
    </div>
  )
}
