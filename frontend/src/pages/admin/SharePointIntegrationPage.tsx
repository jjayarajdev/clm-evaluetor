/* SharePoint integration — Direction B restyle.
   Config card (health Pill, request stats, credential Fields) → site/drive
   browser with token-coloured rows → import progress with a Bar and status
   Pill. All queries, mutations, connection tests, browse navigation and the
   import flow are unchanged from the pre-redesign page. */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
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
import { Bar, Button, Field, Pill, useToast } from '@/components/ui'
import type { PillTone } from '@/components/ui'

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

const HEALTH_CONFIG: Record<string, { tone: PillTone; label: string }> = {
  healthy: { tone: 'ok', label: 'Connected' },
  degraded: { tone: 'wa', label: 'Degraded' },
  unhealthy: { tone: 'da', label: 'Unhealthy' },
  unknown: { tone: 'n', label: 'Not tested' },
}

function HealthBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const cfg = HEALTH_CONFIG[status] || HEALTH_CONFIG.unknown
  return (
    <Pill tone={cfg.tone}>
      {t(`integrations.sharepoint.health.${status}`, { defaultValue: cfg.label })}
    </Pill>
  )
}

/* Token-coloured result strip for connection tests. */
function ResultBanner({ result }: { result: { healthy: boolean; message: string } }) {
  const Icon = result.healthy ? CheckCircleIcon : XCircleIcon
  return (
    <div
      className={result.healthy ? 'banner' : 'banner banner-da'}
      style={result.healthy ? { background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' } : undefined}
    >
      <Icon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
      <span>{result.message}</span>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────

type View = 'config' | 'browse' | 'importing'

export default function SharePointIntegrationPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
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
      toast({ text: result.message, error: !result.healthy })
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
      <div className="row" style={{ justifyContent: 'center', height: 256 }}>
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
      <div className="col" style={{ gap: 18 }}>
        <div className="row" style={{ gap: 10 }}>
          <CloudArrowDownIcon style={{ width: 22, height: 22, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
          <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.3px' }}>
            {t('integrations.sharepoint.importTitle')}
          </h1>
        </div>

        <div className="card card-p col" style={{ gap: 14 }}>
          <div className="row">
            <span className="sec-t grow">{t('common.status')}</span>
            <Pill tone={importStatus.status === 'completed' ? 'ok' : importStatus.status === 'failed' ? 'da' : 'in'}>
              {importStatus.status === 'running' ? t('integrations.sharepoint.importing') : t(`status.${importStatus.status}`, { defaultValue: importStatus.status })}
            </Pill>
          </div>

          {/* Progress bar */}
          <div className="col" style={{ gap: 5 }}>
            <div className="row faint" style={{ justifyContent: 'space-between', fontSize: 'var(--fs-xs)' }}>
              <span>{t('integrations.sharepoint.filesProgress', { done: importStatus.imported + importStatus.skipped + importStatus.failed, total: importStatus.total_files })}</span>
              <span className="num">{pct}%</span>
            </div>
            <Bar value={pct} width="100%" tone={isDone ? 'var(--ok)' : undefined} />
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3" style={{ paddingTop: 6 }}>
            <div className="col" style={{ alignItems: 'center', gap: 2 }}>
              <span className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, color: 'var(--ok)' }}>{importStatus.imported}</span>
              <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.sharepoint.imported')}</span>
            </div>
            <div className="col" style={{ alignItems: 'center', gap: 2 }}>
              <span className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, color: 'var(--f)' }}>{importStatus.skipped}</span>
              <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.sharepoint.skipped')}</span>
            </div>
            <div className="col" style={{ alignItems: 'center', gap: 2 }}>
              <span className="num" style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, color: 'var(--da)' }}>{importStatus.failed}</span>
              <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.failed')}</span>
            </div>
          </div>

          {/* Errors */}
          {importStatus.errors.length > 0 && (
            <div className="banner banner-da" style={{ flexDirection: 'column', gap: 6 }}>
              <b style={{ fontSize: 'var(--fs-sm)' }}>{t('integrations.sharepoint.errorsLabel')}</b>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 'var(--fs-sm)' }}>
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
            <div className="row" style={{ gap: 8, paddingTop: 6 }}>
              <Button variant="primary" onClick={() => { setView('browse'); setImportJobId(null) }}>
                {t('integrations.sharepoint.importMore')}
              </Button>
              <a href="/contracts" className="btn btn-s">
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
      <div className="col" style={{ gap: 14 }}>
        <div className="row" style={{ gap: 10 }}>
          <Button variant="ghost" size="sm" icon={ArrowLeftIcon} onClick={() => setView('config')}>
            {t('common.back', { defaultValue: 'Back' })}
          </Button>
          <FolderOpenIcon style={{ width: 22, height: 22, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
          <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.3px' }}>
            {t('integrations.sharepoint.browseTitle')}
          </h1>
        </div>

        {/* Step 1: Search for site */}
        {!selectedSite && (
          <div className="card card-p col" style={{ gap: 12 }}>
            <span className="sec-t">{t('integrations.sharepoint.findSite')}</span>
            <Field
              icon={MagnifyingGlassIcon}
              type="text"
              placeholder={t('integrations.sharepoint.searchSitesPlaceholder')}
              value={siteSearch}
              onChange={(e) => setSiteSearch(e.target.value)}
            />
            {sitesLoading && <LoadingSpinner size="sm" />}
            {sites && sites.length > 0 && (
              <div className="col" style={{ gap: 2 }}>
                {sites.map((site) => (
                  <button
                    key={site.id}
                    onClick={() => setSelectedSite(site)}
                    className="row w-full text-left rounded-md hover:bg-[var(--s2)] transition-colors"
                    style={{ gap: 10, padding: '9px 10px' }}
                  >
                    <FolderIcon style={{ width: 18, height: 18, flexShrink: 0, color: 'var(--p)' }} aria-hidden />
                    <span className="grow col" style={{ minWidth: 0 }}>
                      <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>
                        {site.display_name || site.name}
                      </span>
                      {site.web_url && (
                        <span className="faint trunc" style={{ fontSize: 'var(--fs-xs)' }}>{site.web_url}</span>
                      )}
                    </span>
                    <ChevronRightIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                  </button>
                ))}
              </div>
            )}
            {sites && sites.length === 0 && siteSearch.length >= 2 && (
              <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>
                {t('integrations.sharepoint.noSitesFound', { query: siteSearch })}
              </p>
            )}
          </div>
        )}

        {/* Step 2: Select document library */}
        {selectedSite && !selectedDrive && (
          <div className="card card-p col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 8 }}>
              <Button variant="ghost" size="sm" icon={ArrowLeftIcon} onClick={() => setSelectedSite(null)}>
                {t('common.back', { defaultValue: 'Back' })}
              </Button>
              <span className="sec-t">
                {t('integrations.sharepoint.documentLibrariesIn')}{' '}
                <span style={{ color: 'var(--p)' }}>{selectedSite.display_name || selectedSite.name}</span>
              </span>
            </div>
            {drivesLoading && <LoadingSpinner size="sm" />}
            {drives && drives.map((drive) => (
              <button
                key={drive.id}
                onClick={() => { setSelectedDrive(drive); setFolderPath('root'); setFolderHistory([]) }}
                className="row w-full text-left rounded-md hover:bg-[var(--s2)] transition-colors"
                style={{ gap: 10, padding: '9px 10px', border: '1px solid var(--b)' }}
              >
                <FolderIcon style={{ width: 18, height: 18, flexShrink: 0, color: 'var(--wa)' }} aria-hidden />
                <span className="grow col" style={{ minWidth: 0 }}>
                  <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{drive.name}</span>
                  {drive.description && (
                    <span className="faint trunc" style={{ fontSize: 'var(--fs-xs)' }}>{drive.description}</span>
                  )}
                </span>
                <ChevronRightIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
              </button>
            ))}
          </div>
        )}

        {/* Step 3: Browse folder contents */}
        {selectedDrive && (
          <div className="card card-p col" style={{ gap: 10 }}>
            {/* Breadcrumb */}
            <div className="row" style={{ gap: 8 }}>
              <Button
                variant="ghost"
                size="sm"
                icon={ArrowLeftIcon}
                onClick={() => { setSelectedDrive(null); setFolderPath('root'); setFolderHistory([]) }}
              >
                {t('common.back', { defaultValue: 'Back' })}
              </Button>
              <span className="muted" style={{ fontSize: 'var(--fs-md)' }}>{selectedDrive.name}</span>
              {folderPath !== 'root' && (
                <>
                  <span className="faint">/</span>
                  <span className="trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 500 }}>{folderPath}</span>
                </>
              )}
              <span className="grow" />
              <Button
                variant="primary"
                size="sm"
                icon={CloudArrowDownIcon}
                onClick={() => importMutation.mutate()}
                disabled={importMutation.isPending}
              >
                {importMutation.isPending ? t('integrations.sharepoint.starting') : t('integrations.sharepoint.importThisFolder')}
              </Button>
            </div>

            {/* Back button when in subfolder */}
            {folderPath !== 'root' && (
              <Button variant="ghost" size="sm" icon={ArrowLeftIcon} onClick={navigateBack} style={{ alignSelf: 'flex-start' }}>
                {t('integrations.sharepoint.back')}
              </Button>
            )}

            {folderLoading && <LoadingSpinner size="sm" />}

            {/* Items list */}
            {folderItems && (
              <div className="divide-y divide-[var(--b)]">
                {/* Folders first */}
                {folderItems.filter(i => i.is_folder).map((item) => (
                  <button
                    key={item.id}
                    onClick={() => navigateToFolder(item.name)}
                    className="row w-full text-left hover:bg-[var(--s2)] transition-colors"
                    style={{ gap: 10, padding: '8px 10px' }}
                  >
                    <FolderIcon style={{ width: 18, height: 18, flexShrink: 0, color: 'var(--wa)' }} aria-hidden />
                    <span className="trunc" style={{ fontSize: 'var(--fs-md)' }}>{item.name}</span>
                    <span className="grow" />
                    {item.child_count != null && (
                      <span className="faint num" style={{ fontSize: 'var(--fs-xs)', flexShrink: 0 }}>
                        {t('integrations.sharepoint.itemsCount', { count: item.child_count })}
                      </span>
                    )}
                    <ChevronRightIcon style={{ width: 14, height: 14, flexShrink: 0, color: 'var(--f)' }} aria-hidden />
                  </button>
                ))}
                {/* Then files */}
                {folderItems.filter(i => !i.is_folder).map((item) => {
                  const ext = item.name.split('.').pop()?.toLowerCase() || ''
                  const isSupported = ['pdf', 'docx', 'doc', 'xlsx', 'pptx'].includes(ext)
                  return (
                    <div
                      key={item.id}
                      className={cn('row', !isSupported && 'opacity-40')}
                      style={{ gap: 10, padding: '8px 10px' }}
                    >
                      <DocumentIcon
                        style={{ width: 18, height: 18, flexShrink: 0, color: isSupported ? 'var(--in)' : 'var(--f)' }}
                        aria-hidden
                      />
                      <span className="muted trunc" style={{ fontSize: 'var(--fs-md)' }}>{item.name}</span>
                      <span className="grow" />
                      <span className="faint num" style={{ fontSize: 'var(--fs-xs)', whiteSpace: 'nowrap' }}>
                        {item.size ? `${(item.size / 1024).toFixed(0)} KB` : ''}
                      </span>
                    </div>
                  )
                })}
                {folderItems.length === 0 && (
                  <p className="muted" style={{ fontSize: 'var(--fs-md)', padding: '16px 0', textAlign: 'center' }}>
                    {t('integrations.sharepoint.emptyFolder')}
                  </p>
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
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
        <span
          style={{
            width: 40, height: 40, borderRadius: 'var(--r-lg)', flexShrink: 0,
            background: 'var(--p-f)', color: 'var(--p)', display: 'grid', placeItems: 'center',
          }}
        >
          <svg style={{ width: 22, height: 22 }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
          </svg>
        </span>
        <div className="grow">
          <h1 style={{ fontSize: 'var(--fs-2xl)', fontWeight: 600, letterSpacing: '-.3px' }}>
            {t('integrations.sharepoint.title')}
          </h1>
          <p className="muted" style={{ fontSize: 'var(--fs-md)' }}>{t('integrations.sharepoint.subtitle')}</p>
        </div>
        {config && config.is_active && (
          <HealthBadge status={config.health_status} />
        )}
      </div>

      {/* Connection Card */}
      <div className="card card-p">
        {!config || !config.is_active || isEditing ? (
          // Setup / Edit form
          <div className="col" style={{ gap: 14 }}>
            <span className="sec-t">
              {config ? t('integrations.sharepoint.updateConnection') : t('integrations.sharepoint.connectTitle')}
            </span>
            <p className="faint" style={{ fontSize: 'var(--fs-sm)' }}>
              {t('integrations.sharepoint.setupHintPrefix')}{' '}
              <code className="mono" style={{ background: 'var(--s2)', padding: '1px 4px', borderRadius: 'var(--r-xs)' }}>Sites.Read.All</code>{' '}
              {t('integrations.sharepoint.setupHintSuffix')}
            </p>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field
                containerClassName="sm:col-span-2"
                label={t('integrations.sharepoint.connectionName')}
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="SharePoint"
              />
              <Field
                label={t('integrations.sharepoint.azureTenantId')}
                type="text"
                className="mono"
                value={formAzureTenant}
                onChange={(e) => setFormAzureTenant(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
              <Field
                label={t('integrations.sharepoint.appClientId')}
                type="text"
                className="mono"
                value={formClientId}
                onChange={(e) => setFormClientId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
              <Field
                containerClassName="sm:col-span-2"
                label={t('integrations.sharepoint.clientSecret')}
                type="password"
                className="mono"
                value={formClientSecret}
                onChange={(e) => setFormClientSecret(e.target.value)}
                placeholder={t('integrations.sharepoint.clientSecretPlaceholder')}
              />
            </div>

            {testResult && <ResultBanner result={testResult} />}

            <div className="row" style={{ gap: 8, paddingTop: 6 }}>
              <Button
                variant="primary"
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending || !formAzureTenant || !formClientId || !formClientSecret}
              >
                {saveMutation.isPending ? t('integrations.saving') : t('integrations.sharepoint.saveAndConnect')}
              </Button>
              {isEditing && (
                <Button variant="ghost" onClick={() => setIsEditing(false)}>
                  {t('common.cancel')}
                </Button>
              )}
            </div>
          </div>
        ) : (
          // Connected state
          <div className="col" style={{ gap: 14 }}>
            <div className="row" style={{ gap: 12 }}>
              <div className="grow" style={{ minWidth: 0 }}>
                <h3 style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>{config.name}</h3>
                <p className="faint" style={{ fontSize: 'var(--fs-xs)', marginTop: 2 }}>
                  {t('integrations.sharepoint.azureTenant')}: <span className="mono">{config.azure_tenant_id}</span>
                </p>
              </div>
              <HealthBadge status={config.health_status} />
            </div>

            <div className="grid grid-cols-3 gap-3" style={{ padding: '6px 0' }}>
              <div className="col" style={{ alignItems: 'center', gap: 2 }}>
                <span className="num" style={{ fontSize: 'var(--fs-xl)', fontWeight: 600 }}>{config.total_requests}</span>
                <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.sharepoint.apiCalls')}</span>
              </div>
              <div className="col" style={{ alignItems: 'center', gap: 2 }}>
                <span className="num" style={{ fontSize: 'var(--fs-xl)', fontWeight: 600 }}>{config.total_requests - config.failed_requests}</span>
                <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.sharepoint.successful')}</span>
              </div>
              <div className="col" style={{ alignItems: 'center', gap: 2 }}>
                <span className="num" style={{ fontSize: 'var(--fs-xl)', fontWeight: 600, color: 'var(--da)' }}>{config.failed_requests}</span>
                <span className="faint" style={{ fontSize: 'var(--fs-xs)' }}>{t('integrations.failed')}</span>
              </div>
            </div>

            <div className="row" style={{ gap: 8, paddingTop: 12, borderTop: '1px solid var(--b)', flexWrap: 'wrap' }}>
              <Button variant="primary" icon={FolderOpenIcon} onClick={() => setView('browse')}>
                {t('integrations.sharepoint.browseAndImport')}
              </Button>
              <Button
                icon={ArrowPathIcon}
                onClick={() => testMutation.mutate()}
                disabled={testMutation.isPending}
                className={cn(testMutation.isPending && '[&>svg]:animate-spin')}
              >
                {t('integrations.test')}
              </Button>
              <Button onClick={() => startEditing()}>
                {t('common.edit')}
              </Button>
              <span className="grow" />
              <Button
                variant="danger-ghost"
                onClick={() => { if (confirm(t('integrations.sharepoint.disconnectConfirm'))) disconnectMutation.mutate() }}
              >
                {t('integrations.sharepoint.disconnect')}
              </Button>
            </div>

            {testResult && <ResultBanner result={testResult} />}
          </div>
        )}
      </div>

      {/* How it works */}
      {(!config || !config.is_active) && (
        <div className="banner banner-p" style={{ flexDirection: 'column', gap: 10, padding: 16 }}>
          <b style={{ fontSize: 'var(--fs-md)' }}>{t('integrations.sharepoint.howItWorks')}</b>
          <ol className="col" style={{ gap: 8, margin: 0, padding: 0, listStyle: 'none', fontSize: 'var(--fs-md)' }}>
            {[
              <>{t('integrations.sharepoint.step1Prefix')} <strong>Sites.Read.All</strong> {t('integrations.sharepoint.step1Suffix')}</>,
              t('integrations.sharepoint.step2'),
              t('integrations.sharepoint.step3'),
              t('integrations.sharepoint.step4'),
            ].map((step, i) => (
              <li key={i} className="row" style={{ gap: 8, alignItems: 'flex-start' }}>
                <span
                  className="num"
                  style={{
                    width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                    background: 'var(--p-f2)', color: 'var(--p)', display: 'grid', placeItems: 'center',
                    fontSize: 'var(--fs-2xs)', fontWeight: 700,
                  }}
                >
                  {i + 1}
                </span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
