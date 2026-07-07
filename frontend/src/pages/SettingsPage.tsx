import { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { setAppLanguage, type AppLanguage } from '@/i18n'
import {
  Cog6ToothIcon,
  BellIcon,
  ShieldCheckIcon,
  CloudIcon,
  PaintBrushIcon,
  PlusIcon,
  TrashIcon,
  SwatchIcon,
  CheckCircleIcon,
  SparklesIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import {
  getIndustryProfiles, setMyIndustryProfile, getTenantOverrides, updateTenantOverrides,
  getExtractionThresholds, updateExtractionThresholds,
  getPromptAddenda, updatePromptAddenda,
} from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

type SettingsTab = 'general' | 'notifications' | 'security' | 'integrations' | 'appearance' | 'extraction'

interface SettingsSection {
  id: SettingsTab
  name: string
  icon: React.ComponentType<{ className?: string }>
  description: string
}

const sections: SettingsSection[] = [
  {
    id: 'general',
    name: 'General',
    icon: Cog6ToothIcon,
    description: 'Basic application settings',
  },
  {
    id: 'notifications',
    name: 'Notifications',
    icon: BellIcon,
    description: 'Configure notification preferences',
  },
  {
    id: 'security',
    name: 'Security',
    icon: ShieldCheckIcon,
    description: 'Security and authentication settings',
  },
  {
    id: 'integrations',
    name: 'Integrations',
    icon: CloudIcon,
    description: 'Third-party integrations and APIs',
  },
  {
    id: 'appearance',
    name: 'Appearance',
    icon: PaintBrushIcon,
    description: 'Customize the look and feel',
  },
  {
    id: 'extraction',
    name: 'AI Extraction',
    icon: AdjustmentsHorizontalIcon,
    description: 'Confidence thresholds and prompt customization for AI extraction (admin only)',
  },
]

export default function SettingsPage() {
  const { t } = useTranslation()
  const { isAdmin } = useAuth()
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')

  const visibleSections = useMemo(
    () => sections.filter((s) => s.id !== 'extraction' || isAdmin),
    [isAdmin]
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.settings')}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('settings.subtitle')}
        </p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-64 shrink-0">
          <nav className="space-y-1">
            {visibleSections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveTab(section.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg transition-colors',
                  activeTab === section.id
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50'
                )}
              >
                <section.icon className="h-5 w-5" />
                {t(`settings.tabs.${section.id}`, { defaultValue: section.name })}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-medium text-gray-900">
                {t(`settings.tabs.${activeTab}`, { defaultValue: sections.find((s) => s.id === activeTab)?.name })}
              </h2>
              <p className="text-sm text-gray-500">
                {t(`settings.tabDescriptions.${activeTab}`, { defaultValue: sections.find((s) => s.id === activeTab)?.description })}
              </p>
            </div>
            <div className="card-body">
              {activeTab === 'general' && <GeneralSettings />}
              {activeTab === 'notifications' && <NotificationSettings />}
              {activeTab === 'security' && <SecuritySettings />}
              {activeTab === 'integrations' && <IntegrationSettings />}
              {activeTab === 'appearance' && <AppearanceSettings />}
              {activeTab === 'extraction' && isAdmin && (
                <div className="space-y-8">
                  <ExtractionThresholdsSettings />
                  <div className="pt-6 border-t border-gray-200">
                    <PromptAddendaSettings />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function LanguageSetting() {
  const { t, i18n } = useTranslation()
  const { user } = useAuth()

  const changeLanguage = async (code: AppLanguage) => {
    setAppLanguage(code)
    if (user) {
      try {
        await api.updateMyPreferences(code)
      } catch {
        // Preference persists locally even if the API call fails
      }
    }
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {t('common.language')}
      </label>
      <select
        className="input max-w-md"
        value={i18n.language?.startsWith('fr') ? 'fr' : 'en'}
        onChange={(e) => changeLanguage(e.target.value as AppLanguage)}
      >
        <option value="en">{t('common.english')}</option>
        <option value="fr">{t('common.french')}</option>
      </select>
    </div>
  )
}


function GeneralSettings() {
  const { t } = useTranslation()
  const { user, isAdmin } = useAuth()
  const { config, refresh: refreshConfig } = useTenantConfig()
  const queryClient = useQueryClient()
  const [settings, setSettings] = useState({
    orgName: user?.tenant_name || 'My Organization',
    currency: 'USD',
    dateFormat: 'MM/DD/YYYY',
  })
  const [saved, setSaved] = useState(false)

  const { data: profiles } = useQuery({
    queryKey: ['industry-profiles'],
    queryFn: getIndustryProfiles,
    enabled: isAdmin,
  })

  const assignMutation = useMutation({
    mutationFn: (slug: string | null) => setMyIndustryProfile(slug),
    onSuccess: () => {
      refreshConfig()
      queryClient.invalidateQueries({ queryKey: ['industry-profiles'] })
    },
  })

  const handleSave = () => {
    localStorage.setItem('clm_settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const currentSlug = config?.industry

  return (
    <div className="space-y-6">
      {/* Industry Profile Selector */}
      {isAdmin && (
        <div className="pb-6 border-b border-gray-200">
          <div className="flex items-center gap-2 mb-3">
            <SwatchIcon className="h-5 w-5 text-violet-500" />
            <h3 className="text-sm font-medium text-gray-900">{t('settings.general.industryProfile')}</h3>
          </div>
          <p className="text-xs text-gray-500 mb-4">
            {t('settings.general.industryProfileDescription')}
          </p>

          {/* Current profile display */}
          {currentSlug && config?.industry_name ? (
            <div className="mb-4 p-3 bg-violet-50 border border-violet-200 rounded-lg">
              <div className="flex items-center gap-2">
                <CheckCircleIcon className="h-4 w-4 text-violet-600 flex-shrink-0" />
                <div className="flex-1">
                  <span className="text-sm font-medium text-violet-900">
                    {config.industry_name}
                  </span>
                  <div className="flex items-center gap-3 mt-1 text-xs text-violet-600">
                    <span>{t('settings.general.contractTypesCount', { count: config.contract_types?.length || 0 })}</span>
                    <span>{t('settings.general.clauseTypesCount', { count: config.clause_types?.length || 0 })}</span>
                    <span>{t('settings.general.riskCategoriesCount', { count: config.risk_categories?.length || 0 })}</span>
                    <span>{t('settings.general.slaMetricsCount', { count: config.sla_metrics?.length || 0 })}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
              <div className="flex items-center gap-2">
                <SparklesIcon className="h-4 w-4 text-amber-600 flex-shrink-0" />
                <span className="text-sm text-amber-800">
                  {t('settings.general.noProfileSelected')}
                </span>
              </div>
            </div>
          )}

          {/* Profile selector grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {profiles?.map((profile: any) => {
              const isActive = profile.slug === currentSlug
              return (
                <button
                  key={profile.id}
                  onClick={() => {
                    if (!isActive) {
                      assignMutation.mutate(profile.slug)
                    }
                  }}
                  disabled={assignMutation.isPending}
                  className={cn(
                    'text-left p-3 rounded-lg border-2 transition-all',
                    isActive
                      ? 'border-violet-500 bg-violet-50/50 ring-1 ring-violet-200'
                      : 'border-gray-200 hover:border-violet-300 hover:bg-violet-50/30',
                    assignMutation.isPending && 'opacity-60 cursor-wait'
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-semibold text-gray-900">
                      {profile.name}
                    </span>
                    {isActive && (
                      <CheckCircleIcon className="h-4 w-4 text-violet-600" />
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mb-2 line-clamp-2">
                    {profile.description}
                  </p>
                  <div className="flex items-center gap-2 text-[10px] text-gray-400">
                    <span>{t('settings.general.typesCount', { count: profile.contract_type_count })}</span>
                    <span className="text-gray-300">|</span>
                    <span>{t('settings.general.clausesCount', { count: profile.clause_type_count })}</span>
                    <span className="text-gray-300">|</span>
                    <span>{t('settings.general.risksCount', { count: profile.risk_category_count })}</span>
                  </div>
                </button>
              )
            })}
          </div>

          {/* Clear profile option */}
          {currentSlug && (
            <button
              onClick={() => assignMutation.mutate(null)}
              disabled={assignMutation.isPending}
              className="mt-2 text-xs text-gray-500 hover:text-red-600 transition-colors"
            >
              {t('settings.general.clearProfile')}
            </button>
          )}

          {assignMutation.isError && (
            <p className="mt-2 text-xs text-red-600">
              {(assignMutation.error as any)?.response?.data?.detail || t('settings.general.updateProfileFailed')}
            </p>
          )}
        </div>
      )}

      {/* Party Aliases */}
      {isAdmin && <PartyAliasesSection />}

      <LanguageSetting />

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('settings.general.organizationName')}
        </label>
        <input
          type="text"
          value={settings.orgName}
          onChange={(e) => setSettings(s => ({ ...s, orgName: e.target.value }))}
          className="input max-w-md"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('settings.general.defaultCurrency')}
        </label>
        <select
          className="input max-w-md"
          value={settings.currency}
          onChange={(e) => setSettings(s => ({ ...s, currency: e.target.value }))}
        >
          <option value="USD">{t('settings.general.currencyUsd')}</option>
          <option value="EUR">{t('settings.general.currencyEur')}</option>
          <option value="GBP">{t('settings.general.currencyGbp')}</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('settings.general.dateFormat')}
        </label>
        <select
          className="input max-w-md"
          value={settings.dateFormat}
          onChange={(e) => setSettings(s => ({ ...s, dateFormat: e.target.value }))}
        >
          <option value="MM/DD/YYYY">MM/DD/YYYY</option>
          <option value="DD/MM/YYYY">DD/MM/YYYY</option>
          <option value="YYYY-MM-DD">YYYY-MM-DD</option>
        </select>
      </div>
      <div className="pt-4 flex items-center gap-3">
        <button className="btn-primary" onClick={handleSave}>{t('settings.general.saveChanges')}</button>
        {saved && <span className="text-sm text-green-600">{t('settings.general.saved')}</span>}
      </div>
    </div>
  )
}

function PartyAliasesSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [newAlias, setNewAlias] = useState('')
  const [saving, setSaving] = useState(false)

  const { data: overrides, isLoading } = useQuery({
    queryKey: ['tenant-overrides'],
    queryFn: getTenantOverrides,
  })

  const aliases: string[] = overrides?.party_aliases || []

  const saveAliases = async (updated: string[]) => {
    setSaving(true)
    try {
      await updateTenantOverrides({ party_aliases: updated })
      queryClient.invalidateQueries({ queryKey: ['tenant-overrides'] })
    } finally {
      setSaving(false)
    }
  }

  const addAlias = async () => {
    const trimmed = newAlias.trim()
    if (!trimmed || aliases.includes(trimmed)) return
    await saveAliases([...aliases, trimmed])
    setNewAlias('')
  }

  const removeAlias = async (alias: string) => {
    await saveAliases(aliases.filter((a) => a !== alias))
  }

  return (
    <div className="pb-6 border-b border-gray-200">
      <div className="flex items-center gap-2 mb-1">
        <ShieldCheckIcon className="h-5 w-5 text-violet-500" />
        <h3 className="text-sm font-medium text-gray-900">{t('settings.aliases.title')}</h3>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        {t('settings.aliases.description')}
      </p>

      {isLoading ? (
        <LoadingSpinner size="sm" />
      ) : (
        <>
          {/* Existing aliases */}
          {aliases.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {aliases.map((alias) => (
                <span
                  key={alias}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-violet-50 border border-violet-200 rounded-full text-sm text-violet-800"
                >
                  {alias}
                  <button
                    onClick={() => removeAlias(alias)}
                    disabled={saving}
                    className="text-violet-400 hover:text-red-500 transition-colors disabled:opacity-50"
                    title={t('settings.aliases.remove')}
                  >
                    <TrashIcon className="h-3.5 w-3.5" />
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Add new alias */}
          <div className="flex items-center gap-2 max-w-md">
            <input
              type="text"
              value={newAlias}
              onChange={(e) => setNewAlias(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addAlias()}
              placeholder={t('settings.aliases.placeholder')}
              className="input flex-1"
              disabled={saving}
            />
            <button
              onClick={addAlias}
              disabled={saving || !newAlias.trim()}
              className="btn-primary flex items-center gap-1.5 disabled:opacity-50"
            >
              <PlusIcon className="h-4 w-4" />
              {t('settings.aliases.add')}
            </button>
          </div>
        </>
      )}
    </div>
  )
}

interface NotificationRule {
  id: string
  name: string
  description?: string
  is_active: boolean
  event_type: string
  days_before: number
  channels: string[]
  priority: string
  trigger_count: number
}

interface RuleTemplate {
  name: string
  description: string
  event_type: string
  days_before: number
  channels: string[]
  priority: string
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  contract_expiration: 'Contract Expiration',
  notice_deadline: 'Notice Deadline',
  obligation_due: 'Obligation Due',
  sla_breach: 'SLA Breach',
  sla_warning: 'SLA Warning',
  renewal_reminder: 'Renewal Reminder',
  key_date: 'Key Date',
  compliance_overdue: 'Compliance Overdue',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  normal: 'bg-blue-100 text-blue-700',
  high: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

function NotificationSettings() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [showTemplates, setShowTemplates] = useState(false)

  const { data: rules, isLoading } = useQuery({
    queryKey: ['notification-rules'],
    queryFn: () => api.getNotificationRules({ activeOnly: false }) as Promise<NotificationRule[]>,
  })

  const { data: templates } = useQuery({
    queryKey: ['notification-rule-templates'],
    queryFn: () => api.getNotificationRuleTemplates() as Promise<RuleTemplate[]>,
    enabled: showTemplates,
  })

  const toggleMutation = useMutation({
    mutationFn: (ruleId: string) => api.toggleNotificationRule(ruleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notification-rules'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => api.deleteNotificationRule(ruleId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notification-rules'] }),
  })

  const createFromTemplateMutation = useMutation({
    mutationFn: (templateIndex: number) => api.createNotificationRuleFromTemplate(templateIndex),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-rules'] })
      setShowTemplates(false)
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
    <div className="space-y-6">
      {/* Header with Add Button */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-gray-900">{t('settings.notifications.title')}</h3>
          <p className="text-xs text-gray-500">{t('settings.notifications.subtitle')}</p>
        </div>
        <button
          onClick={() => setShowTemplates(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700"
        >
          <PlusIcon className="h-4 w-4" />
          {t('settings.notifications.addRule')}
        </button>
      </div>

      {/* Templates Modal */}
      {showTemplates && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              {t('settings.notifications.chooseTemplate')}
            </h3>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {templates?.map((template, index) => (
                <button
                  key={index}
                  onClick={() => createFromTemplateMutation.mutate(index)}
                  className="w-full text-left p-4 border border-gray-200 rounded-lg hover:border-primary-300 hover:bg-primary-50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-medium text-gray-900">{template.name}</p>
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      PRIORITY_COLORS[template.priority] || PRIORITY_COLORS.normal
                    )}>
                      {t(`settings.notifications.priority.${template.priority}`, { defaultValue: template.priority })}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500">{template.description}</p>
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                    <span>{t(`settings.notifications.eventTypes.${template.event_type}`, { defaultValue: EVENT_TYPE_LABELS[template.event_type] || template.event_type })}</span>
                    <span>•</span>
                    <span>{t('settings.notifications.daysBefore', { count: template.days_before })}</span>
                    <span>•</span>
                    <span>{template.channels.join(', ')}</span>
                  </div>
                </button>
              ))}
            </div>
            <div className="flex justify-end mt-4">
              <button
                onClick={() => setShowTemplates(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                {t('common.cancel')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rules List */}
      {rules && rules.length > 0 ? (
        <div className="space-y-3">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className={cn(
                'p-4 border rounded-lg transition-colors',
                rule.is_active ? 'border-gray-200 bg-white' : 'border-gray-100 bg-gray-50'
              )}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <p className={cn(
                      'font-medium',
                      rule.is_active ? 'text-gray-900' : 'text-gray-500'
                    )}>
                      {rule.name}
                    </p>
                    <span className={cn(
                      'px-2 py-0.5 rounded text-xs font-medium',
                      PRIORITY_COLORS[rule.priority] || PRIORITY_COLORS.normal
                    )}>
                      {t(`settings.notifications.priority.${rule.priority}`, { defaultValue: rule.priority })}
                    </span>
                    {!rule.is_active && (
                      <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
                        {t('settings.notifications.disabled')}
                      </span>
                    )}
                  </div>
                  {rule.description && (
                    <p className="text-sm text-gray-500 mb-2">{rule.description}</p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span className="px-2 py-0.5 bg-gray-100 rounded">
                      {t(`settings.notifications.eventTypes.${rule.event_type}`, { defaultValue: EVENT_TYPE_LABELS[rule.event_type] || rule.event_type })}
                    </span>
                    <span>{t('settings.notifications.daysBefore', { count: rule.days_before })}</span>
                    <span>{rule.channels.join(', ')}</span>
                    {rule.trigger_count > 0 && (
                      <span className="text-green-600">
                        {t('settings.notifications.triggeredTimes', { count: rule.trigger_count })}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={rule.is_active}
                      onChange={() => toggleMutation.mutate(rule.id)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                  </label>
                  <button
                    onClick={() => {
                      if (confirm(t('settings.notifications.confirmDelete'))) {
                        deleteMutation.mutate(rule.id)
                      }
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <BellIcon className="h-12 w-12 mx-auto text-gray-300 mb-3" />
          <p className="text-sm font-medium mb-1">{t('settings.notifications.noRules')}</p>
          <p className="text-xs">{t('settings.notifications.noRulesHint')}</p>
        </div>
      )}
    </div>
  )
}

function SecuritySettings() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' })
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  const handleUpdatePassword = async () => {
    setPasswordError('')
    if (!passwords.current || !passwords.newPass || !passwords.confirm) {
      setPasswordError(t('settings.security.allFieldsRequired'))
      return
    }
    if (passwords.newPass.length < 6) {
      setPasswordError(t('settings.security.passwordTooShort'))
      return
    }
    if (passwords.newPass !== passwords.confirm) {
      setPasswordError(t('settings.security.passwordsDoNotMatch'))
      return
    }
    try {
      await api.updateUserPassword(user!.id, passwords.newPass)
      setPasswords({ current: '', newPass: '', confirm: '' })
      setPasswordSuccess(true)
      setTimeout(() => setPasswordSuccess(false), 3000)
    } catch (err: any) {
      setPasswordError(err?.response?.data?.detail || t('settings.security.updateFailed'))
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-3">{t('settings.security.changePassword')}</h3>
        <div className="space-y-3 max-w-md">
          <input
            type="password"
            placeholder={t('settings.security.currentPassword')}
            value={passwords.current}
            onChange={(e) => setPasswords(p => ({ ...p, current: e.target.value }))}
            className="input"
          />
          <input
            type="password"
            placeholder={t('settings.security.newPassword')}
            value={passwords.newPass}
            onChange={(e) => setPasswords(p => ({ ...p, newPass: e.target.value }))}
            className="input"
          />
          <input
            type="password"
            placeholder={t('settings.security.confirmPassword')}
            value={passwords.confirm}
            onChange={(e) => setPasswords(p => ({ ...p, confirm: e.target.value }))}
            className="input"
          />
          <div className="flex items-center gap-3">
            <button className="btn-primary" onClick={handleUpdatePassword}>{t('settings.security.updatePassword')}</button>
            {passwordSuccess && <span className="text-sm text-green-600">{t('settings.security.passwordUpdated')}</span>}
          </div>
          {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
        </div>
      </div>
      <div className="pt-4 border-t border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-3">{t('settings.security.twoFactor')}</h3>
        <p className="text-sm text-gray-500 mb-3">
          {t('settings.security.twoFactorDescription')}
        </p>
        <div className="flex items-center gap-2">
          <button className="btn-secondary opacity-60 cursor-not-allowed" disabled>{t('settings.security.enable2fa')}</button>
          <span className="text-xs text-gray-400">{t('settings.comingSoon')}</span>
        </div>
      </div>
      <div className="pt-4 border-t border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-3">{t('settings.security.activeSessions')}</h3>
        <p className="text-sm text-gray-500 mb-3">
          {t('settings.security.activeSessionsDescription')}
        </p>
        <div className="flex items-center gap-2">
          <button className="btn-secondary text-red-600 hover:text-red-700 opacity-60 cursor-not-allowed" disabled>
            {t('settings.security.signOutAllDevices')}
          </button>
          <span className="text-xs text-gray-400">{t('settings.comingSoon')}</span>
        </div>
      </div>
    </div>
  )
}

function IntegrationSettings() {
  const { t } = useTranslation()
  const integrations = [
    { name: 'OpenAI', description: t('settings.integrations.descriptions.openai'), connected: true, configurable: false },
    { name: 'ServiceNow', description: t('settings.integrations.descriptions.servicenow'), connected: false, configurable: true, configPath: '/admin/integrations/servicenow' },
    { name: 'SharePoint', description: t('settings.integrations.descriptions.sharepoint'), connected: false, configurable: true, configPath: '/admin/integrations/sharepoint' },
    { name: 'SSO (OIDC)', description: t('settings.integrations.descriptions.sso'), connected: false, configurable: true, configPath: '/admin/sso' },
    { name: 'Microsoft Teams', description: t('settings.integrations.descriptions.teams'), connected: false, configurable: false },
    { name: 'Slack', description: t('settings.integrations.descriptions.slack'), connected: false, configurable: false },
  ]

  return (
    <div className="space-y-4">
      {integrations.map((integration) => (
        <div
          key={integration.name}
          className="flex items-center justify-between py-3 border-b border-gray-200 last:border-0"
        >
          <div>
            <p className="text-sm font-medium text-gray-900">{integration.name}</p>
            <p className="text-xs text-gray-500">{integration.description}</p>
          </div>
          {integration.connected ? (
            <span className="text-sm font-medium px-3 py-1.5 rounded-lg bg-green-100 text-green-700">
              {t('settings.integrations.connected')}
            </span>
          ) : integration.configurable ? (
            <a
              href={integration.configPath}
              className="text-sm font-medium px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200"
            >
              {t('settings.integrations.configure')}
            </a>
          ) : (
            <span className="text-sm font-medium px-3 py-1.5 rounded-lg bg-gray-50 text-gray-400">
              {t('settings.comingSoon')}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

function AppearanceSettings() {
  const { t } = useTranslation()
  const [theme, setTheme] = useState('light')

  const themes = [
    { id: 'light', label: t('settings.appearance.light'), preview: 'bg-white border border-gray-200' },
    { id: 'dark', label: t('settings.appearance.dark'), preview: 'bg-gray-800', disabled: true },
    { id: 'system', label: t('settings.appearance.system'), preview: 'bg-gradient-to-b from-white to-gray-800', disabled: true },
  ]

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          {t('settings.appearance.theme')}
        </label>
        <div className="flex gap-3">
          {themes.map((th) => (
            <button
              key={th.id}
              onClick={() => !th.disabled && setTheme(th.id)}
              className={cn(
                'flex-1 p-4 border-2 rounded-lg bg-white transition-colors',
                theme === th.id ? 'border-primary-500' : 'border-gray-200 hover:border-gray-300',
                th.disabled && 'opacity-50 cursor-not-allowed',
              )}
            >
              <div className={cn('h-16 rounded mb-2', th.preview)} />
              <div className="flex items-center justify-center gap-1">
                <p className="text-sm font-medium text-gray-900">{th.label}</p>
                {th.disabled && <span className="text-[10px] text-gray-400">{t('settings.appearance.soon')}</span>}
              </div>
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('settings.appearance.sidebarPosition')}
        </label>
        <div className="flex items-center gap-2">
          <select className="input max-w-md opacity-60" disabled>
            <option value="left">{t('settings.appearance.left')}</option>
            <option value="right">{t('settings.appearance.right')}</option>
          </select>
          <span className="text-xs text-gray-400">{t('settings.comingSoon')}</span>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('settings.appearance.density')}
        </label>
        <div className="flex items-center gap-2">
          <select className="input max-w-md opacity-60" disabled>
            <option value="comfortable">{t('settings.appearance.comfortable')}</option>
            <option value="compact">{t('settings.appearance.compact')}</option>
          </select>
          <span className="text-xs text-gray-400">{t('settings.comingSoon')}</span>
        </div>
      </div>
    </div>
  )
}

// Friendly labels for extraction threshold fields
const EXTRACTION_FIELD_LABELS: Record<string, string> = {
  contract_type: 'Contract Type',
  counterparty: 'Counterparty',
  effective_date: 'Effective Date',
  expiration_date: 'Expiration Date',
  contract_value: 'Contract Value',
  currency: 'Currency',
  jurisdiction: 'Jurisdiction',
}

function ExtractionThresholdsSettings() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['extraction-thresholds'],
    queryFn: getExtractionThresholds,
  })

  const [defaultThreshold, setDefaultThreshold] = useState<number>(0.7)
  const [fields, setFields] = useState<Record<string, number>>({})
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Sync local state when server data arrives or refreshes
  useEffect(() => {
    if (data) {
      setDefaultThreshold(data.default)
      setFields({ ...data.fields })
    }
  }, [data])

  const mutation = useMutation({
    mutationFn: updateExtractionThresholds,
    onSuccess: (resp) => {
      setDefaultThreshold(resp.default)
      setFields({ ...resp.fields })
      setSaved(true)
      setError(null)
      setTimeout(() => setSaved(false), 2000)
      queryClient.invalidateQueries({ queryKey: ['extraction-thresholds'] })
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || err?.message || t('settings.extraction.saveFailed'))
    },
  })

  if (isLoading) {
    return (
      <div className="flex justify-center py-8">
        <LoadingSpinner size="md" />
      </div>
    )
  }

  const availableFields = data?.available_fields || Object.keys(EXTRACTION_FIELD_LABELS)
  const unsetFields = availableFields.filter((f) => !(f in fields))

  const updateField = (field: string, raw: string) => {
    const v = parseFloat(raw)
    if (Number.isNaN(v)) return
    if (v < 0 || v > 1) return
    setFields((prev) => ({ ...prev, [field]: v }))
  }

  const removeField = (field: string) => {
    setFields((prev) => {
      const next = { ...prev }
      delete next[field]
      return next
    })
  }

  const addField = (field: string) => {
    if (!field) return
    setFields((prev) => ({ ...prev, [field]: defaultThreshold }))
  }

  const handleSave = () => {
    setError(null)
    mutation.mutate({ default: defaultThreshold, fields })
  }

  const isDirty =
    !!data &&
    (data.default !== defaultThreshold ||
      JSON.stringify(data.fields) !== JSON.stringify(fields))

  return (
    <div className="space-y-6">
      <div className="text-sm text-gray-600">
        {t('settings.extraction.intro')}
      </div>

      {/* Default threshold */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('settings.extraction.defaultThreshold')}
        </label>
        <p className="text-xs text-gray-500 mb-2">
          {t('settings.extraction.defaultThresholdHint')}
        </p>
        <div className="flex items-center gap-3 max-w-xs">
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={defaultThreshold}
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              if (!Number.isNaN(v) && v >= 0 && v <= 1) setDefaultThreshold(v)
            }}
            className="input"
          />
          <span className="text-sm text-gray-500">{(defaultThreshold * 100).toFixed(0)}%</span>
        </div>
      </div>

      {/* Per-field overrides */}
      <div>
        <h3 className="text-sm font-medium text-gray-700 mb-2">{t('settings.extraction.perFieldOverrides')}</h3>
        {Object.keys(fields).length === 0 ? (
          <p className="text-sm text-gray-400 italic mb-3">
            {t('settings.extraction.noOverrides')}
          </p>
        ) : (
          <div className="space-y-2 mb-3">
            {Object.entries(fields).map(([field, value]) => (
              <div key={field} className="flex items-center gap-3">
                <span className="w-40 text-sm text-gray-700">
                  {t(`settings.extraction.fields.${field}`, { defaultValue: EXTRACTION_FIELD_LABELS[field] || field })}
                </span>
                <input
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={value}
                  onChange={(e) => updateField(field, e.target.value)}
                  className="input w-32"
                />
                <span className="text-xs text-gray-500 w-12">
                  {(value * 100).toFixed(0)}%
                </span>
                <button
                  type="button"
                  onClick={() => removeField(field)}
                  className="text-gray-400 hover:text-red-600"
                  title={t('settings.extraction.removeOverride')}
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {unsetFields.length > 0 && (
          <div className="flex items-center gap-2">
            <select
              className="input max-w-xs"
              value=""
              onChange={(e) => {
                addField(e.target.value)
                e.currentTarget.value = ''
              }}
            >
              <option value="">{t('settings.extraction.addFieldOverride')}</option>
              {unsetFields.map((f) => (
                <option key={f} value={f}>
                  {t(`settings.extraction.fields.${f}`, { defaultValue: EXTRACTION_FIELD_LABELS[f] || f })}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Save row */}
      <div className="pt-4 border-t border-gray-200 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={!isDirty || mutation.isPending}
          className={cn(
            'btn btn-primary',
            (!isDirty || mutation.isPending) && 'opacity-60 cursor-not-allowed'
          )}
        >
          {mutation.isPending ? t('settings.saving') : t('settings.extraction.saveThresholds')}
        </button>
        {saved && (
          <span className="text-sm text-green-600 inline-flex items-center gap-1">
            <CheckCircleIcon className="h-4 w-4" /> {t('settings.saved')}
          </span>
        )}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  )
}

// #27 — Per-tenant prompt addenda. Labels match the keys used by the backend's
// PROMPT_ADDENDA_AGENTS tuple in admin_settings.py.
const PROMPT_ADDENDA_LABELS: Record<string, { label: string; placeholder: string }> = {
  metadata: {
    label: 'Metadata extraction',
    placeholder: "e.g. Treat 'Client' as our company, not the counterparty.",
  },
  clauses: {
    label: 'Clause extraction',
    placeholder: 'e.g. Always flag references to HIPAA or HITRUST.',
  },
  obligations: {
    label: 'Obligation detection',
    placeholder: "e.g. Health-system contracts often phrase obligations as 'shall ensure'.",
  },
  slas: {
    label: 'SLA extraction',
    placeholder: 'e.g. Uptime is reported as a quarterly average, not monthly.',
  },
  risks: {
    label: 'Risk assessment',
    placeholder: 'e.g. Liability caps below $1M are a hard no for us.',
  },
}
const PROMPT_ADDENDA_ORDER = ['metadata', 'clauses', 'obligations', 'slas', 'risks']

function PromptAddendaSettings() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['prompt-addenda'],
    queryFn: getPromptAddenda,
  })

  const [draft, setDraft] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (data?.addenda) setDraft({ ...data.addenda })
  }, [data])

  const mutation = useMutation({
    mutationFn: (payload: Record<string, string>) => updatePromptAddenda(payload),
    onSuccess: (resp) => {
      setDraft({ ...resp.addenda })
      setSaved(true)
      setError(null)
      setTimeout(() => setSaved(false), 2000)
      queryClient.invalidateQueries({ queryKey: ['prompt-addenda'] })
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || err?.message || t('settings.prompts.saveFailed'))
    },
  })

  if (isLoading) {
    return <div className="py-4 flex justify-center"><LoadingSpinner size="md" /></div>
  }

  const maxChars = data?.max_chars ?? 2000
  const isDirty = !!data && JSON.stringify(draft) !== JSON.stringify(data.addenda || {})

  const handleChange = (agent: string, value: string) => {
    setDraft((prev) => ({ ...prev, [agent]: value }))
  }

  const handleSave = () => {
    setError(null)
    // Only send non-empty values; empty strings clear the entry on the backend
    const cleaned: Record<string, string> = {}
    for (const [k, v] of Object.entries(draft)) {
      if (v && v.trim()) cleaned[k] = v.trim()
    }
    mutation.mutate(cleaned)
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-base font-medium text-gray-900">{t('settings.prompts.title')}</h3>
        <p className="text-sm text-gray-600 mt-1">
          {t('settings.prompts.description', { maxChars })}
        </p>
      </div>

      <div className="space-y-4">
        {PROMPT_ADDENDA_ORDER.map((agent) => {
          const info = PROMPT_ADDENDA_LABELS[agent]
          const value = draft[agent] || ''
          const over = value.length > maxChars
          return (
            <div key={agent}>
              <div className="flex items-center justify-between mb-1">
                <label className="text-sm font-medium text-gray-700">
                  {t(`settings.prompts.labels.${agent}`, { defaultValue: info.label })}
                </label>
                <span className={cn(
                  'text-xs',
                  over ? 'text-red-600 font-medium' : 'text-gray-400'
                )}>
                  {value.length} / {maxChars}
                </span>
              </div>
              <textarea
                value={value}
                onChange={(e) => handleChange(agent, e.target.value)}
                placeholder={t(`settings.prompts.placeholders.${agent}`, { defaultValue: info.placeholder })}
                rows={3}
                className={cn(
                  'w-full text-sm border rounded-md p-2 focus:outline-none focus:ring-1',
                  over
                    ? 'border-red-300 focus:ring-red-400'
                    : 'border-gray-200 focus:ring-primary-400'
                )}
              />
            </div>
          )
        })}
      </div>

      <div className="pt-2 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={!isDirty || mutation.isPending || Object.values(draft).some(v => (v || '').length > maxChars)}
          className={cn(
            'btn btn-primary',
            (!isDirty || mutation.isPending) && 'opacity-60 cursor-not-allowed'
          )}
        >
          {mutation.isPending ? t('settings.saving') : t('settings.prompts.savePromptAddenda')}
        </button>
        {saved && (
          <span className="text-sm text-green-600 inline-flex items-center gap-1">
            <CheckCircleIcon className="h-4 w-4" /> {t('settings.saved')}
          </span>
        )}
        {error && <span className="text-sm text-red-600">{error}</span>}
      </div>
    </div>
  )
}
