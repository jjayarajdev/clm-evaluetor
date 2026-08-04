/* Settings — Direction B redesign.
   Header → Tabs (admin-only tabs filtered) → one .card per section with a
   titled header and .card-p body. Sections keep their original queries,
   mutations and validation; saves surface through primary Buttons + toasts,
   destructive actions go through ConfirmDialog. TenantRolePermissionsSection
   is reused as-is. */
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
  ScaleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  KeyIcon,
  FolderIcon,
  ChatBubbleLeftRightIcon,
  WrenchScrewdriverIcon,
  LockClosedIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { useTenantConfig } from '@/contexts/TenantConfigContext'
import { useTheme, type ThemeMode } from '@/contexts/ThemeContext'
import {
  getIndustryProfiles, setMyIndustryProfile, getTenantOverrides, updateTenantOverrides,
  getExtractionThresholds, updateExtractionThresholds,
  getPromptAddenda, updatePromptAddenda,
  getBusinessUnits, getBusinessUnit, updateBusinessUnit,
  getAzureOpenAI, setAzureOpenAI, testAzureOpenAI,
} from '@/lib/api/admin'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import TenantRolePermissionsSection from '@/components/settings/TenantRolePermissionsSection'
import {
  Bar, Button, Checkbox, ConfirmDialog, Drawer, EmptyState, Field, IconButton,
  Pill, Select, Switch, Tabs, Tag, useToast,
} from '@/components/ui'
import type { IconType, PillTone } from '@/components/ui'

type SettingsTab = 'general' | 'notifications' | 'security' | 'integrations' | 'appearance' | 'extraction' | 'scoring' | 'ai' | 'permissions'

interface SettingsSection {
  id: SettingsTab
  name: string
  icon: IconType
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
  {
    id: 'scoring',
    name: 'Scoring Rules',
    icon: ScaleIcon,
    description: 'How "At Risk" and "Compliance" are calculated, per tenant or business unit (admin only)',
  },
  {
    id: 'ai',
    name: 'AI Provider',
    icon: SparklesIcon,
    description: 'Use your own Azure OpenAI resource for this organization (admin only)',
  },
  {
    id: 'permissions',
    name: 'Roles & Permissions',
    icon: ShieldCheckIcon,
    description: 'Tailor what each role can do in your organization (admin only)',
  },
]

export default function SettingsPage() {
  const { t } = useTranslation()
  const { isAdmin } = useAuth()
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')

  const adminOnly: SettingsTab[] = ['extraction', 'scoring', 'ai', 'permissions']
  const visibleSections = useMemo(
    () => sections.filter((s) => !adminOnly.includes(s.id) || isAdmin),
    [isAdmin]
  )

  const active = sections.find((s) => s.id === activeTab)

  return (
    <div className="col" style={{ gap: 18 }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>{t('nav.settings')}</h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>{t('settings.subtitle')}</p>
      </div>

      {/* Section tabs */}
      <Tabs<SettingsTab>
        tabs={visibleSections.map((s) => ({
          value: s.id,
          label: t(`settings.tabs.${s.id}`, { defaultValue: s.name }),
          icon: s.icon,
        }))}
        value={activeTab}
        onChange={setActiveTab}
      />

      {/* Active section card */}
      <div className="card">
        <div style={{ padding: '13px 16px', borderBottom: '1px solid var(--b)' }}>
          <b style={{ fontSize: 'var(--fs-lg)' }}>
            {t(`settings.tabs.${activeTab}`, { defaultValue: active?.name })}
          </b>
          <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 2 }}>
            {t(`settings.tabDescriptions.${activeTab}`, { defaultValue: active?.description })}
          </p>
        </div>
        <div className="card-p">
          {activeTab === 'general' && <GeneralSettings />}
          {activeTab === 'notifications' && <NotificationSettings />}
          {activeTab === 'security' && <SecuritySettings />}
          {activeTab === 'integrations' && <IntegrationSettings />}
          {activeTab === 'appearance' && <AppearanceSettings />}
          {activeTab === 'extraction' && isAdmin && (
            <div className="col" style={{ gap: 22 }}>
              <ExtractionThresholdsSettings />
              <div className="divider" />
              <PromptAddendaSettings />
            </div>
          )}
          {activeTab === 'scoring' && isAdmin && <ScoringRulesSection />}
          {activeTab === 'ai' && isAdmin && <AzureOpenAISection />}
          {activeTab === 'permissions' && isAdmin && <TenantRolePermissionsSection />}
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
    <Select
      label={t('common.language')}
      containerStyle={{ maxWidth: 380 }}
      value={i18n.language?.startsWith('fr') ? 'fr' : 'en'}
      onChange={(e) => changeLanguage(e.target.value as AppLanguage)}
      options={[
        { value: 'en', label: t('common.english') },
        { value: 'fr', label: t('common.french') },
      ]}
    />
  )
}


function GeneralSettings() {
  const { t } = useTranslation()
  const { user, isAdmin } = useAuth()
  const { config, refresh: refreshConfig } = useTenantConfig()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [settings, setSettings] = useState({
    orgName: user?.tenant_name || 'My Organization',
    currency: 'USD',
    dateFormat: 'MM/DD/YYYY',
  })

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
    toast({ text: t('settings.general.saved') })
  }

  const currentSlug = config?.industry

  return (
    <div className="col" style={{ gap: 22 }}>
      {/* Industry Profile Selector */}
      {isAdmin && (
        <div className="col" style={{ gap: 10 }}>
          <div>
            <div className="row" style={{ gap: 7 }}>
              <SwatchIcon style={{ width: 15, height: 15, color: 'var(--p)' }} aria-hidden />
              <span className="sec-t">{t('settings.general.industryProfile')}</span>
            </div>
            <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4, lineHeight: 1.5 }}>
              {t('settings.general.industryProfileDescription')}
            </p>
          </div>

          {/* Current profile display */}
          {currentSlug && config?.industry_name ? (
            <div className="banner banner-p">
              <CheckCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>
                <b>{config.industry_name}</b>
                <span className="row" style={{ gap: 12, marginTop: 3, fontSize: 'var(--fs-xs)', flexWrap: 'wrap' }}>
                  <span>{t('settings.general.contractTypesCount', { count: config.contract_types?.length || 0 })}</span>
                  <span>{t('settings.general.clauseTypesCount', { count: config.clause_types?.length || 0 })}</span>
                  <span>{t('settings.general.riskCategoriesCount', { count: config.risk_categories?.length || 0 })}</span>
                  <span>{t('settings.general.slaMetricsCount', { count: config.sla_metrics?.length || 0 })}</span>
                </span>
              </span>
            </div>
          ) : (
            <div className="banner banner-wa">
              <SparklesIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{t('settings.general.noProfileSelected')}</span>
            </div>
          )}

          {/* Profile selector grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {profiles?.map((profile: any) => {
              const isActive = profile.slug === currentSlug
              return (
                <button
                  key={profile.id}
                  type="button"
                  onClick={() => {
                    if (!isActive) {
                      assignMutation.mutate(profile.slug)
                    }
                  }}
                  disabled={assignMutation.isPending}
                  className="col"
                  style={{
                    gap: 6,
                    textAlign: 'left',
                    padding: '10px 12px',
                    borderRadius: 'var(--r-md)',
                    border: '1px solid ' + (isActive ? 'var(--p-b)' : 'var(--b)'),
                    background: isActive ? 'var(--p-f)' : 'var(--s)',
                    cursor: assignMutation.isPending ? 'wait' : 'pointer',
                    opacity: assignMutation.isPending ? 0.6 : 1,
                    transition: 'border-color .12s var(--ease), background .12s var(--ease)',
                  }}
                >
                  <span className="row" style={{ gap: 8 }}>
                    <span className="grow trunc" style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>
                      {profile.name}
                    </span>
                    {isActive && <CheckCircleIcon style={{ width: 15, height: 15, flexShrink: 0, color: 'var(--p)' }} aria-hidden />}
                  </span>
                  <span className="muted" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {profile.description}
                  </span>
                  <span className="faint row" style={{ gap: 8, fontSize: 'var(--fs-2xs)', flexWrap: 'wrap' }}>
                    <span>{t('settings.general.typesCount', { count: profile.contract_type_count })}</span>
                    <span>·</span>
                    <span>{t('settings.general.clausesCount', { count: profile.clause_type_count })}</span>
                    <span>·</span>
                    <span>{t('settings.general.risksCount', { count: profile.risk_category_count })}</span>
                  </span>
                </button>
              )
            })}
          </div>

          {/* Clear profile option */}
          {currentSlug && (
            <div className="row">
              <Button
                variant="danger-ghost"
                size="sm"
                icon={XMarkIcon}
                onClick={() => assignMutation.mutate(null)}
                disabled={assignMutation.isPending}
              >
                {t('settings.general.clearProfile')}
              </Button>
            </div>
          )}

          {assignMutation.isError && (
            <div className="banner banner-da">
              <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
              <span>{(assignMutation.error as any)?.response?.data?.detail || t('settings.general.updateProfileFailed')}</span>
            </div>
          )}
          <div className="divider" />
        </div>
      )}

      {/* Party Aliases */}
      {isAdmin && <PartyAliasesSection />}

      <LanguageSetting />

      <Field
        label={t('settings.general.organizationName')}
        containerStyle={{ maxWidth: 380 }}
        value={settings.orgName}
        onChange={(e) => setSettings(s => ({ ...s, orgName: e.target.value }))}
      />
      <Select
        label={t('settings.general.defaultCurrency')}
        containerStyle={{ maxWidth: 380 }}
        value={settings.currency}
        onChange={(e) => setSettings(s => ({ ...s, currency: e.target.value }))}
        options={[
          { value: 'USD', label: t('settings.general.currencyUsd') },
          { value: 'EUR', label: t('settings.general.currencyEur') },
          { value: 'GBP', label: t('settings.general.currencyGbp') },
        ]}
      />
      <Select
        label={t('settings.general.dateFormat')}
        containerStyle={{ maxWidth: 380 }}
        value={settings.dateFormat}
        onChange={(e) => setSettings(s => ({ ...s, dateFormat: e.target.value }))}
        options={[
          { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY' },
          { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY' },
          { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD' },
        ]}
      />
      <div className="row">
        <Button variant="primary" onClick={handleSave}>{t('settings.general.saveChanges')}</Button>
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
    <div className="col" style={{ gap: 10 }}>
      <div>
        <div className="row" style={{ gap: 7 }}>
          <ShieldCheckIcon style={{ width: 15, height: 15, color: 'var(--p)' }} aria-hidden />
          <span className="sec-t">{t('settings.aliases.title')}</span>
        </div>
        <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4, lineHeight: 1.5 }}>
          {t('settings.aliases.description')}
        </p>
      </div>

      {isLoading ? (
        <LoadingSpinner size="sm" />
      ) : (
        <>
          {/* Existing aliases */}
          {aliases.length > 0 && (
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              {aliases.map((alias) => (
                <span
                  key={alias}
                  className="row"
                  style={{
                    gap: 4,
                    height: 28,
                    padding: '0 4px 0 10px',
                    border: '1px solid var(--p-b)',
                    borderRadius: 'var(--r-sm)',
                    background: 'var(--p-f)',
                    color: 'var(--p)',
                    fontSize: 'var(--fs-sm)',
                    fontWeight: 500,
                  }}
                >
                  {alias}
                  <IconButton
                    icon={TrashIcon}
                    size="sm"
                    label={t('settings.aliases.remove')}
                    onClick={() => removeAlias(alias)}
                    disabled={saving}
                  />
                </span>
              ))}
            </div>
          )}

          {/* Add new alias */}
          <div className="row" style={{ gap: 8, maxWidth: 420 }}>
            <Field
              containerClassName="grow"
              value={newAlias}
              onChange={(e) => setNewAlias(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addAlias()}
              placeholder={t('settings.aliases.placeholder')}
              disabled={saving}
              aria-label={t('settings.aliases.title')}
            />
            <Button
              variant="primary"
              icon={PlusIcon}
              onClick={addAlias}
              disabled={saving || !newAlias.trim()}
            >
              {t('settings.aliases.add')}
            </Button>
          </div>
        </>
      )}
      <div className="divider" />
    </div>
  )
}

// ============================================================================
// Scoring Rules — configure how "At Risk" and "Compliance" are computed.
// Resolves default -> tenant -> BU on the backend; this UI edits one scope at a
// time. Mirrors backend DEFAULT_SCORING_CONFIG (services/scoring_config.py).
// ============================================================================

const DEFAULT_SCORING = {
  at_risk: {
    definition: 'obligations' as 'obligations' | 'risk_level' | 'both',
    overdue_count_threshold: 2,
    overdue_ratio_threshold: 0.3,
    risk_levels: ['high', 'critical'] as string[],
  },
  compliance: { obligation_weight: 0.6, sla_weight: 0.4 },
  vendor: {
    obligation_weight: 0.4,
    sla_weight: 0.3,
    responsiveness_weight: 0.2, // reserved — signal not measured yet
    issue_rate_weight: 0.1, // reserved — signal not measured yet
    low_threshold: 80,
    medium_threshold: 60,
    high_threshold: 40,
    at_risk_threshold: 60,
  },
}
const RISK_LEVEL_OPTIONS = ['low', 'medium', 'high', 'critical']
const DEFINITION_OPTIONS: Array<'obligations' | 'risk_level' | 'both'> = ['obligations', 'risk_level', 'both']

function ScoringRulesSection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [scope, setScope] = useState<string>('tenant') // 'tenant' | <buId>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [draft, setDraft] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: buList } = useQuery({
    queryKey: ['scoring-bu-list'],
    queryFn: () => getBusinessUnits({ page_size: 200, active_only: true }),
  })

  const { data: current, isLoading } = useQuery({
    queryKey: ['scoring-config', scope],
    queryFn: async () => {
      if (scope === 'tenant') {
        const o = await getTenantOverrides()
        return o?.scoring ?? {}
      }
      const bu = await getBusinessUnit(scope)
      return bu?.config_overrides?.scoring ?? {}
    },
  })

  // Merge stored override onto defaults so every field is editable; unset fields
  // show the inherited default. `hasOverride` drives the "inherited vs custom" hint.
  const hasOverride = !!current && (!!current.at_risk || !!current.compliance || !!current.vendor)
  useEffect(() => {
    const s = current || {}
    setDraft({
      at_risk: { ...DEFAULT_SCORING.at_risk, ...(s.at_risk || {}) },
      compliance: { ...DEFAULT_SCORING.compliance, ...(s.compliance || {}) },
      vendor: { ...DEFAULT_SCORING.vendor, ...(s.vendor || {}) },
    })
    setError(null)
  }, [current, scope])

  const setAtRisk = (patch: Record<string, unknown>) =>
    setDraft((d: typeof draft) => ({ ...d, at_risk: { ...d.at_risk, ...patch } }))
  const setCompliance = (patch: Record<string, unknown>) =>
    setDraft((d: typeof draft) => ({ ...d, compliance: { ...d.compliance, ...patch } }))
  const setVendor = (patch: Record<string, unknown>) =>
    setDraft((d: typeof draft) => ({ ...d, vendor: { ...d.vendor, ...patch } }))

  const save = async (payload: typeof DEFAULT_SCORING | Record<string, never>) => {
    setSaving(true)
    setError(null)
    try {
      if (scope === 'tenant') {
        await updateTenantOverrides({ scoring: payload })
      } else {
        await updateBusinessUnit(scope, { config_overrides: { scoring: payload } })
      }
      queryClient.invalidateQueries({ queryKey: ['scoring-config', scope] })
      toast({ text: t('common.saved', { defaultValue: 'Saved' }) })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  if (isLoading || !draft) return <LoadingSpinner size="sm" />

  const ar = draft.at_risk
  const comp = draft.compliance
  const vend = draft.vendor

  return (
    <div className="col" style={{ gap: 22, maxWidth: 620 }}>
      {/* Scope selector */}
      <Select
        label={t('settings.scoring.scope', { defaultValue: 'Applies to' })}
        containerStyle={{ maxWidth: 380 }}
        value={scope}
        onChange={(e) => setScope(e.target.value)}
        options={[
          { value: 'tenant', label: t('settings.scoring.scopeTenant', { defaultValue: 'Whole organization (default)' }) },
          ...(buList?.items || []).map((bu) => ({
            value: bu.id,
            label: t('settings.scoring.scopeBu', { defaultValue: 'Business unit: {{name}}', name: bu.name }),
          })),
        ]}
        hint={
          scope === 'tenant'
            ? t('settings.scoring.scopeTenantHint', { defaultValue: 'These rules apply everywhere unless a business unit overrides them.' })
            : hasOverride
              ? t('settings.scoring.scopeBuCustom', { defaultValue: 'This business unit has custom rules that override the organization defaults.' })
              : t('settings.scoring.scopeBuInherited', { defaultValue: 'This business unit currently inherits the organization defaults. Saving here creates an override.' })
        }
      />

      {/* At Risk */}
      <div className="col" style={{ gap: 12 }}>
        <div>
          <span className="sec-t">{t('settings.scoring.atRiskTitle', { defaultValue: 'At Risk' })}</span>
          <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4 }}>
            {t('settings.scoring.atRiskDesc', { defaultValue: 'When a contract is counted as "at risk".' })}
          </p>
        </div>

        <Select
          label={t('settings.scoring.definition', { defaultValue: 'Definition' })}
          containerStyle={{ maxWidth: 380 }}
          value={ar.definition}
          onChange={(e) => setAtRisk({ definition: e.target.value })}
          options={DEFINITION_OPTIONS.map((d) => ({
            value: d,
            label: t(`settings.scoring.definitionOpt.${d}`, {
              defaultValue: d === 'obligations' ? 'Overdue obligations' : d === 'risk_level' ? 'AI risk level' : 'Either one',
            }),
          }))}
        />

        {ar.definition !== 'risk_level' && (
          <div className="grid grid-cols-2 gap-4" style={{ maxWidth: 420 }}>
            <Field
              label={t('settings.scoring.overdueCount', { defaultValue: 'Overdue obligations ≥' })}
              type="number" min={1} step={1}
              value={ar.overdue_count_threshold}
              onChange={(e) => setAtRisk({ overdue_count_threshold: Number(e.target.value) })}
            />
            <Field
              label={t('settings.scoring.overdueRatio', { defaultValue: 'or overdue share >' })}
              type="number" min={0} max={100} step={5}
              value={Math.round(ar.overdue_ratio_threshold * 100)}
              onChange={(e) => setAtRisk({ overdue_ratio_threshold: Number(e.target.value) / 100 })}
              hint="%"
            />
          </div>
        )}

        {ar.definition !== 'obligations' && (
          <div>
            <span className="lbl">{t('settings.scoring.riskLevels', { defaultValue: 'Risk levels that count as at-risk' })}</span>
            <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
              {RISK_LEVEL_OPTIONS.map((lvl) => (
                <Checkbox
                  key={lvl}
                  checked={ar.risk_levels.includes(lvl)}
                  onChange={(checked) => setAtRisk({
                    risk_levels: checked
                      ? [...ar.risk_levels, lvl]
                      : ar.risk_levels.filter((x: string) => x !== lvl),
                  })}
                  label={t(`settings.scoring.riskLevel.${lvl}`, { defaultValue: lvl.charAt(0).toUpperCase() + lvl.slice(1) })}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="divider" />

      {/* Compliance */}
      <div className="col" style={{ gap: 12 }}>
        <div>
          <span className="sec-t">{t('settings.scoring.complianceTitle', { defaultValue: 'Compliance' })}</span>
          <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4, lineHeight: 1.5 }}>
            {t('settings.scoring.complianceDesc', { defaultValue: 'Overall compliance is a weighted blend of the measured components (relative weights).' })}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4" style={{ maxWidth: 420 }}>
          <Field
            label={t('settings.scoring.obligationWeight', { defaultValue: 'Obligation weight' })}
            type="number" min={0} step={0.1}
            value={comp.obligation_weight}
            onChange={(e) => setCompliance({ obligation_weight: Number(e.target.value) })}
          />
          <Field
            label={t('settings.scoring.slaWeight', { defaultValue: 'SLA weight' })}
            type="number" min={0} step={0.1}
            value={comp.sla_weight}
            onChange={(e) => setCompliance({ sla_weight: Number(e.target.value) })}
          />
        </div>
      </div>

      <div className="divider" />

      {/* Vendor scorecard */}
      <div className="col" style={{ gap: 12 }}>
        <div>
          <span className="sec-t">{t('settings.scoring.vendorTitle', { defaultValue: 'Vendor scorecard' })}</span>
          <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 4, lineHeight: 1.5 }}>
            {t('settings.scoring.vendorDesc', { defaultValue: 'How counterparty performance scores are blended and banded. Only measured signals (obligations, SLAs) enter the blend; weights are renormalized.' })}
          </p>
        </div>

        <div className="grid grid-cols-2 gap-4" style={{ maxWidth: 420 }}>
          <Field
            label={t('settings.scoring.obligationWeight', { defaultValue: 'Obligation weight' })}
            type="number" min={0} step={0.05}
            value={vend.obligation_weight}
            onChange={(e) => setVendor({ obligation_weight: Number(e.target.value) })}
          />
          <Field
            label={t('settings.scoring.slaWeight', { defaultValue: 'SLA weight' })}
            type="number" min={0} step={0.05}
            value={vend.sla_weight}
            onChange={(e) => setVendor({ sla_weight: Number(e.target.value) })}
          />
          <div style={{ opacity: 0.6 }}>
            <Field
              label={t('settings.scoring.responsivenessWeight', { defaultValue: 'Responsiveness weight' })}
              type="number" min={0} step={0.05}
              value={vend.responsiveness_weight}
              onChange={(e) => setVendor({ responsiveness_weight: Number(e.target.value) })}
            />
            <Tag>{t('settings.scoring.reservedSignal', { defaultValue: 'not yet measured' })}</Tag>
          </div>
          <div style={{ opacity: 0.6 }}>
            <Field
              label={t('settings.scoring.issueRateWeight', { defaultValue: 'Issue-rate weight' })}
              type="number" min={0} step={0.05}
              value={vend.issue_rate_weight}
              onChange={(e) => setVendor({ issue_rate_weight: Number(e.target.value) })}
            />
            <Tag>{t('settings.scoring.reservedSignal', { defaultValue: 'not yet measured' })}</Tag>
          </div>
        </div>

        <div>
          <span className="lbl">{t('settings.scoring.vendorBands', { defaultValue: 'Risk bands' })}</span>
          <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginBottom: 8, lineHeight: 1.5 }}>
            {t('settings.scoring.vendorBandsHint', { defaultValue: 'Score at or above "low" is low risk, above "medium" is medium, above "high" is high — anything lower is critical.' })}
          </p>
          <div className="grid grid-cols-2 gap-4" style={{ maxWidth: 420 }}>
            <Field
              label={t('settings.scoring.lowThreshold', { defaultValue: 'Low risk ≥' })}
              type="number" min={0} max={100} step={5}
              value={vend.low_threshold}
              onChange={(e) => setVendor({ low_threshold: Number(e.target.value) })}
            />
            <Field
              label={t('settings.scoring.mediumThreshold', { defaultValue: 'Medium risk ≥' })}
              type="number" min={0} max={100} step={5}
              value={vend.medium_threshold}
              onChange={(e) => setVendor({ medium_threshold: Number(e.target.value) })}
            />
            <Field
              label={t('settings.scoring.highThreshold', { defaultValue: 'High risk ≥' })}
              type="number" min={0} max={100} step={5}
              value={vend.high_threshold}
              onChange={(e) => setVendor({ high_threshold: Number(e.target.value) })}
            />
            <Field
              label={t('settings.scoring.atRiskThreshold', { defaultValue: '"At risk" below' })}
              type="number" min={0} max={100} step={5}
              value={vend.at_risk_threshold}
              onChange={(e) => setVendor({ at_risk_threshold: Number(e.target.value) })}
              hint={t('settings.scoring.atRiskThresholdHint', { defaultValue: 'Composite score below this counts the vendor as at risk.' })}
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{error}</span>
        </div>
      )}

      {/* Actions */}
      <div className="row" style={{ gap: 8 }}>
        <Button variant="primary" icon={CheckCircleIcon} onClick={() => save(draft)} disabled={saving}>
          {saving ? t('common.saving', { defaultValue: 'Saving…' }) : t('common.save', { defaultValue: 'Save' })}
        </Button>
        {hasOverride && (
          <Button
            variant="secondary"
            onClick={() => save({})}
            disabled={saving}
            title={t('settings.scoring.resetHint', { defaultValue: 'Remove the override and fall back to the inherited defaults.' })}
          >
            {scope === 'tenant'
              ? t('settings.scoring.resetTenant', { defaultValue: 'Reset to system defaults' })
              : t('settings.scoring.resetBu', { defaultValue: 'Clear override (inherit)' })}
          </Button>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Azure OpenAI — per-tenant AI provider. When enabled, this organization's AI
// calls run against its own Azure OpenAI resource (its own quota/billing).
// ============================================================================
// Azure REST api-version values (date-based). NOT model names.
const AZURE_API_VERSIONS = ['2024-12-01-preview', '2025-01-01-preview', '2024-08-01-preview', '2024-10-21', '2024-06-01']

function AzureOpenAISection() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [enabled, setEnabled] = useState(false)
  const [provider, setProvider] = useState<'azure' | 'openai'>('azure')
  const [endpoint, setEndpoint] = useState('')
  const [apiVersion, setApiVersion] = useState('2024-08-01-preview')
  const [deployment, setDeployment] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)

  const { data, isLoading } = useQuery({ queryKey: ['azure-openai'], queryFn: getAzureOpenAI })

  useEffect(() => {
    if (data) {
      setEnabled(data.enabled)
      setProvider(data.provider === 'openai' ? 'openai' : 'azure')
      setEndpoint(data.endpoint || '')
      // Coerce any non-date value (e.g. a model name mistakenly saved here) to the default.
      const v = data.api_version || ''
      setApiVersion(AZURE_API_VERSIONS.includes(v) ? v : '2024-08-01-preview')
      setDeployment(data.deployment || '')
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: () => setAzureOpenAI({ enabled, provider, endpoint, api_version: apiVersion, deployment, api_key: apiKey }),
    onSuccess: () => {
      setApiKey('')
      toast({ text: t('common.saved', { defaultValue: 'Saved' }) })
      queryClient.invalidateQueries({ queryKey: ['azure-openai'] })
    },
  })
  const testMutation = useMutation({
    mutationFn: testAzureOpenAI,
    onSuccess: (r) => setTestResult(r),
    onError: (e: unknown) => setTestResult({ ok: false, message: e instanceof Error ? e.message : 'Test failed' }),
  })

  if (isLoading) return <LoadingSpinner size="sm" />

  return (
    <div className="col" style={{ gap: 18, maxWidth: 620 }}>
      <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>{t('settings.azure.intro')}</p>

      <Switch
        checked={enabled}
        onChange={(checked) => setEnabled(checked)}
        label={t('settings.azure.enable')}
      />

      <div className="col" style={{ gap: 14, opacity: enabled ? 1 : 0.5 }}>
        <Select
          label={t('settings.azure.provider')}
          containerStyle={{ maxWidth: 380 }}
          value={provider}
          onChange={(e) => setProvider(e.target.value as 'azure' | 'openai')}
          disabled={!enabled}
          options={[
            { value: 'azure', label: t('settings.azure.providerAzure') },
            { value: 'openai', label: t('settings.azure.providerOpenAI') },
          ]}
        />

        {provider === 'azure' && (
          <Field
            label={t('settings.azure.endpoint')}
            placeholder="https://your-resource.openai.azure.com"
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            disabled={!enabled}
          />
        )}
        <Field
          label={provider === 'openai' ? t('settings.azure.openaiKey') : t('settings.azure.apiKey')}
          type="password"
          icon={KeyIcon}
          placeholder={data?.api_key_set ? `${data.api_key_masked} — ${t('settings.azure.keyKept')}` : (provider === 'openai' ? t('settings.azure.openaiKeyPlaceholder') : t('settings.azure.keyPlaceholder'))}
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          disabled={!enabled}
          hint={t('settings.azure.keyHint')}
        />
        {provider === 'azure' && (
          <>
            <Field
              label={t('settings.azure.deployment')}
              containerStyle={{ maxWidth: 380 }}
              placeholder="e.g. gpt-4o-mini, gpt-5, my-deployment"
              value={deployment}
              onChange={(e) => setDeployment(e.target.value)}
              disabled={!enabled}
              hint={t('settings.azure.deploymentHint')}
            />
            <Select
              label={t('settings.azure.apiVersion')}
              containerStyle={{ maxWidth: 280 }}
              value={apiVersion}
              onChange={(e) => setApiVersion(e.target.value)}
              disabled={!enabled}
              options={AZURE_API_VERSIONS.map((v) => ({ value: v, label: v }))}
              hint={t('settings.azure.apiVersionHint')}
            />
          </>
        )}
        {provider === 'openai' && (
          <div className="banner banner-in">
            <InformationCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
            <span>{t('settings.azure.openaiNote')}</span>
          </div>
        )}
      </div>

      {testResult && (
        <div
          className={cn('banner', !testResult.ok && 'banner-da')}
          style={testResult.ok ? { background: 'var(--ok-f)', borderColor: 'var(--ok-b)', color: 'var(--ok)' } : undefined}
        >
          {testResult.ok
            ? <CheckCircleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
            : <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />}
          <span>{testResult.message}</span>
        </div>
      )}

      <div className="row" style={{ gap: 8 }}>
        <Button variant="primary" icon={CheckCircleIcon} onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
          {saveMutation.isPending ? t('common.saving') : t('common.save')}
        </Button>
        <Button
          variant="secondary"
          onClick={() => { setTestResult(null); testMutation.mutate() }}
          disabled={testMutation.isPending || !data?.api_key_set}
          title={t('settings.azure.testHint')}
        >
          {testMutation.isPending ? t('settings.azure.testing') : t('settings.azure.test')}
        </Button>
      </div>
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

const PRIORITY_TONE: Record<string, PillTone> = {
  low: 'n',
  normal: 'in',
  high: 'wa',
  critical: 'da',
}

function NotificationSettings() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [showTemplates, setShowTemplates] = useState(false)
  const [ruleToDelete, setRuleToDelete] = useState<NotificationRule | null>(null)

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-rules'] })
      toast({ text: t('settings.notifications.ruleDeleted', { defaultValue: 'Notification rule deleted' }) })
    },
  })

  const createFromTemplateMutation = useMutation({
    mutationFn: (templateIndex: number) => api.createNotificationRuleFromTemplate(templateIndex),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-rules'] })
      setShowTemplates(false)
      toast({ text: t('settings.notifications.ruleCreated', { defaultValue: 'Notification rule created' }) })
    },
  })

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', height: 128 }}>
        <LoadingSpinner size="md" />
      </div>
    )
  }

  return (
    <div className="col" style={{ gap: 14 }}>
      {/* Header with Add Button */}
      <div className="row" style={{ gap: 12 }}>
        <div className="grow">
          <span className="sec-t">{t('settings.notifications.title')}</span>
          <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginTop: 3 }}>{t('settings.notifications.subtitle')}</p>
        </div>
        <Button variant="primary" icon={PlusIcon} onClick={() => setShowTemplates(true)}>
          {t('settings.notifications.addRule')}
        </Button>
      </div>

      {/* Template picker */}
      <Drawer
        open={showTemplates}
        title={t('settings.notifications.chooseTemplate')}
        onClose={() => setShowTemplates(false)}
        footer={
          <Button variant="secondary" className="grow" onClick={() => setShowTemplates(false)}>
            {t('common.cancel')}
          </Button>
        }
      >
        <div className="col" style={{ gap: 10 }}>
          {templates?.map((template, index) => (
            <button
              key={index}
              type="button"
              onClick={() => createFromTemplateMutation.mutate(index)}
              disabled={createFromTemplateMutation.isPending}
              className="col"
              style={{
                gap: 6,
                textAlign: 'left',
                padding: '11px 12px',
                border: '1px solid var(--b)',
                borderRadius: 'var(--r-md)',
                background: 'var(--s)',
                cursor: createFromTemplateMutation.isPending ? 'wait' : 'pointer',
                transition: 'border-color .12s var(--ease), background .12s var(--ease)',
              }}
            >
              <span className="row" style={{ gap: 8 }}>
                <span className="grow trunc" style={{ fontWeight: 600, fontSize: 'var(--fs-md)' }}>{template.name}</span>
                <Pill tone={PRIORITY_TONE[template.priority] || 'in'}>
                  {t(`settings.notifications.priority.${template.priority}`, { defaultValue: template.priority })}
                </Pill>
              </span>
              <span className="muted" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.45 }}>{template.description}</span>
              <span className="faint row" style={{ gap: 8, fontSize: 'var(--fs-xs)', flexWrap: 'wrap' }}>
                <span>{t(`settings.notifications.eventTypes.${template.event_type}`, { defaultValue: EVENT_TYPE_LABELS[template.event_type] || template.event_type })}</span>
                <span>·</span>
                <span>{t('settings.notifications.daysBefore', { count: template.days_before })}</span>
                <span>·</span>
                <span>{template.channels.join(', ')}</span>
              </span>
            </button>
          ))}
        </div>
      </Drawer>

      {/* Delete confirmation */}
      <ConfirmDialog
        open={!!ruleToDelete}
        title={t('settings.notifications.deleteRuleTitle', { defaultValue: 'Delete notification rule' })}
        body={t('settings.notifications.confirmDelete')}
        affected={ruleToDelete ? [ruleToDelete.name] : undefined}
        confirmLabel={t('common.delete', { defaultValue: 'Delete' })}
        cancelLabel={t('common.cancel')}
        onConfirm={() => {
          if (ruleToDelete) deleteMutation.mutate(ruleToDelete.id)
          setRuleToDelete(null)
        }}
        onCancel={() => setRuleToDelete(null)}
      />

      {/* Rules List */}
      {rules && rules.length > 0 ? (
        <div className="col" style={{ gap: 10 }}>
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="card card-p row"
              style={{ gap: 12, alignItems: 'flex-start', background: rule.is_active ? undefined : 'var(--s3)' }}
            >
              <div className="grow col" style={{ gap: 5, minWidth: 0 }}>
                <span className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                  <span className={cn(!rule.is_active && 'muted')} style={{ fontWeight: 600, fontSize: 'var(--fs-md)' }}>
                    {rule.name}
                  </span>
                  <Pill tone={PRIORITY_TONE[rule.priority] || 'in'}>
                    {t(`settings.notifications.priority.${rule.priority}`, { defaultValue: rule.priority })}
                  </Pill>
                  {!rule.is_active && <Tag>{t('settings.notifications.disabled')}</Tag>}
                </span>
                {rule.description && (
                  <span className="muted" style={{ fontSize: 'var(--fs-sm)', lineHeight: 1.45 }}>{rule.description}</span>
                )}
                <span className="faint row" style={{ gap: 10, fontSize: 'var(--fs-xs)', flexWrap: 'wrap' }}>
                  <Tag>
                    {t(`settings.notifications.eventTypes.${rule.event_type}`, { defaultValue: EVENT_TYPE_LABELS[rule.event_type] || rule.event_type })}
                  </Tag>
                  <span>{t('settings.notifications.daysBefore', { count: rule.days_before })}</span>
                  <span>{rule.channels.join(', ')}</span>
                  {rule.trigger_count > 0 && (
                    <span style={{ color: 'var(--ok)' }}>
                      {t('settings.notifications.triggeredTimes', { count: rule.trigger_count })}
                    </span>
                  )}
                </span>
              </div>
              <div className="row" style={{ gap: 6, flexShrink: 0 }}>
                <Switch
                  checked={rule.is_active}
                  onChange={() => toggleMutation.mutate(rule.id)}
                />
                <IconButton
                  icon={TrashIcon}
                  label={t('settings.notifications.deleteRuleTitle', { defaultValue: 'Delete notification rule' })}
                  size="sm"
                  onClick={() => setRuleToDelete(rule)}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          icon={BellIcon}
          title={t('settings.notifications.noRules')}
          body={t('settings.notifications.noRulesHint')}
        />
      )}
    </div>
  )
}

function SecuritySettings() {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' })
  const [passwordError, setPasswordError] = useState('')

  const handleUpdatePassword = async () => {
    setPasswordError('')
    if (!passwords.current || !passwords.newPass || !passwords.confirm) {
      setPasswordError(t('settings.security.allFieldsRequired'))
      return
    }
    if (passwords.newPass.length < 8) {
      setPasswordError(t('settings.security.passwordTooShort'))
      return
    }
    if (passwords.newPass !== passwords.confirm) {
      setPasswordError(t('settings.security.passwordsDoNotMatch'))
      return
    }
    try {
      await api.changeMyPassword(passwords.current, passwords.newPass)
      setPasswords({ current: '', newPass: '', confirm: '' })
      toast({ text: t('settings.security.passwordUpdated') })
    } catch (err: any) {
      setPasswordError(err?.response?.data?.detail || t('settings.security.updateFailed'))
    }
  }

  return (
    <div className="col" style={{ gap: 22 }}>
      {/* Change password */}
      <div className="col" style={{ gap: 12, maxWidth: 420 }}>
        <span className="sec-t">{t('settings.security.changePassword')}</span>
        <Field
          type="password"
          icon={LockClosedIcon}
          placeholder={t('settings.security.currentPassword')}
          aria-label={t('settings.security.currentPassword')}
          value={passwords.current}
          onChange={(e) => setPasswords(p => ({ ...p, current: e.target.value }))}
        />
        <Field
          type="password"
          icon={KeyIcon}
          placeholder={t('settings.security.newPassword')}
          aria-label={t('settings.security.newPassword')}
          value={passwords.newPass}
          onChange={(e) => setPasswords(p => ({ ...p, newPass: e.target.value }))}
        />
        <Field
          type="password"
          icon={KeyIcon}
          placeholder={t('settings.security.confirmPassword')}
          aria-label={t('settings.security.confirmPassword')}
          value={passwords.confirm}
          onChange={(e) => setPasswords(p => ({ ...p, confirm: e.target.value }))}
        />
        {passwordError && (
          <div className="banner banner-da">
            <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
            <span>{passwordError}</span>
          </div>
        )}
        <div className="row">
          <Button variant="primary" onClick={handleUpdatePassword}>{t('settings.security.updatePassword')}</Button>
        </div>
      </div>

      <div className="divider" />

      {/* Two-factor */}
      <div className="col" style={{ gap: 8 }}>
        <span className="sec-t">{t('settings.security.twoFactor')}</span>
        <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.5 }}>
          {t('settings.security.twoFactorDescription')}
        </p>
        <div className="row" style={{ gap: 8 }}>
          <Button variant="secondary" disabled>{t('settings.security.enable2fa')}</Button>
          <Tag>{t('settings.comingSoon')}</Tag>
        </div>
      </div>

      <div className="divider" />

      {/* Active sessions — danger zone */}
      <div className="col" style={{ gap: 8 }}>
        <span className="sec-t">{t('settings.security.activeSessions')}</span>
        <div className="banner banner-da" style={{ alignItems: 'center', flexWrap: 'wrap' }}>
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0 }} aria-hidden />
          <span className="grow" style={{ minWidth: 220 }}>{t('settings.security.activeSessionsDescription')}</span>
          <span className="row" style={{ gap: 8, flexShrink: 0 }}>
            <Button variant="danger-ghost" size="sm" disabled>
              {t('settings.security.signOutAllDevices')}
            </Button>
            <Tag>{t('settings.comingSoon')}</Tag>
          </span>
        </div>
      </div>
    </div>
  )
}

function IntegrationSettings() {
  const { t } = useTranslation()
  const integrations: Array<{
    name: string
    description: string
    icon: IconType
    connected: boolean
    configurable: boolean
    configPath?: string
  }> = [
    { name: 'OpenAI', description: t('settings.integrations.descriptions.openai'), icon: SparklesIcon, connected: true, configurable: false },
    { name: 'ServiceNow', description: t('settings.integrations.descriptions.servicenow'), icon: WrenchScrewdriverIcon, connected: false, configurable: true, configPath: '/admin/integrations/servicenow' },
    { name: 'SharePoint', description: t('settings.integrations.descriptions.sharepoint'), icon: FolderIcon, connected: false, configurable: true, configPath: '/admin/integrations/sharepoint' },
    { name: 'SSO (OIDC)', description: t('settings.integrations.descriptions.sso'), icon: KeyIcon, connected: false, configurable: true, configPath: '/admin/sso' },
    { name: 'Microsoft Teams', description: t('settings.integrations.descriptions.teams'), icon: ChatBubbleLeftRightIcon, connected: false, configurable: false },
    { name: 'Slack', description: t('settings.integrations.descriptions.slack'), icon: ChatBubbleLeftRightIcon, connected: false, configurable: false },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
      {integrations.map((integration) => (
        <div key={integration.name} className="card card-p col" style={{ gap: 12 }}>
          <div className="row" style={{ gap: 11 }}>
            <span
              style={{
                width: 34, height: 34, borderRadius: 'var(--r-md)', display: 'grid', placeItems: 'center',
                background: 'var(--s2)', color: 'var(--m)', flexShrink: 0,
              }}
            >
              <integration.icon style={{ width: 17, height: 17 }} aria-hidden />
            </span>
            <span className="grow" style={{ minWidth: 0 }}>
              <span className="trunc" style={{ display: 'block', fontSize: 'var(--fs-lg)', fontWeight: 600 }}>
                {integration.name}
              </span>
              <span className="faint trunc" style={{ display: 'block', fontSize: 'var(--fs-sm)' }} title={integration.description}>
                {integration.description}
              </span>
            </span>
            <Pill tone={integration.connected ? 'ok' : 'n'}>
              {integration.connected
                ? t('settings.integrations.connected')
                : t('settings.integrations.notConnected', { defaultValue: 'Not connected' })}
            </Pill>
          </div>
          {integration.connected ? null : integration.configurable ? (
            <a href={integration.configPath} className="btn btn-s btn-sm" style={{ width: '100%' }}>
              <Cog6ToothIcon style={{ width: 13, height: 13, flexShrink: 0 }} aria-hidden />
              {t('settings.integrations.configure')}
            </a>
          ) : (
            <span className="faint" style={{ fontSize: 'var(--fs-sm)' }}>{t('settings.comingSoon')}</span>
          )}
        </div>
      ))}
    </div>
  )
}

function AppearanceSettings() {
  const { t } = useTranslation()
  const { mode, setMode } = useTheme()

  const themes: { id: ThemeMode; label: string; preview: React.CSSProperties }[] = [
    { id: 'light', label: t('settings.appearance.light'), preview: { background: '#fff', border: '1px solid #e4e4e7' } },
    { id: 'dark', label: t('settings.appearance.dark'), preview: { background: '#18181b', border: '1px solid #27272a' } },
    { id: 'system', label: t('settings.appearance.system'), preview: { background: 'linear-gradient(105deg, #fff 50%, #18181b 50%)', border: '1px solid var(--b)' } },
  ]

  return (
    <div className="col" style={{ gap: 22 }}>
      <div>
        <span className="lbl">{t('settings.appearance.theme')}</span>
        <div className="row" style={{ gap: 10, alignItems: 'stretch', maxWidth: 560 }}>
          {themes.map((th) => (
            <button
              key={th.id}
              type="button"
              onClick={() => setMode(th.id)}
              className="col grow"
              style={{
                gap: 8,
                padding: 12,
                borderRadius: 'var(--r-md)',
                border: '1px solid ' + (mode === th.id ? 'var(--p-b)' : 'var(--b)'),
                background: mode === th.id ? 'var(--p-f)' : 'var(--s)',
                cursor: 'pointer',
                transition: 'border-color .12s var(--ease), background .12s var(--ease)',
              }}
            >
              <span style={{ height: 56, borderRadius: 'var(--r-sm)', ...th.preview }} />
              <span className="row" style={{ gap: 6, justifyContent: 'center' }}>
                <span style={{ fontSize: 'var(--fs-md)', fontWeight: 600 }}>{th.label}</span>
              </span>
            </button>
          ))}
        </div>
      </div>
      <div className="row" style={{ gap: 8, alignItems: 'flex-end' }}>
        <Select
          label={t('settings.appearance.sidebarPosition')}
          containerStyle={{ width: 280 }}
          disabled
          options={[
            { value: 'left', label: t('settings.appearance.left') },
            { value: 'right', label: t('settings.appearance.right') },
          ]}
        />
        <Tag>{t('settings.comingSoon')}</Tag>
      </div>
      <div className="row" style={{ gap: 8, alignItems: 'flex-end' }}>
        <Select
          label={t('settings.appearance.density')}
          containerStyle={{ width: 280 }}
          disabled
          options={[
            { value: 'comfortable', label: t('settings.appearance.comfortable') },
            { value: 'compact', label: t('settings.appearance.compact') },
          ]}
        />
        <Tag>{t('settings.comingSoon')}</Tag>
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
  const { toast } = useToast()
  const { data, isLoading } = useQuery({
    queryKey: ['extraction-thresholds'],
    queryFn: getExtractionThresholds,
  })

  const [defaultThreshold, setDefaultThreshold] = useState<number>(0.7)
  const [fields, setFields] = useState<Record<string, number>>({})
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
      setError(null)
      toast({ text: t('settings.saved') })
      queryClient.invalidateQueries({ queryKey: ['extraction-thresholds'] })
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || err?.message || t('settings.extraction.saveFailed'))
    },
  })

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', padding: 32 }}>
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
    <div className="col" style={{ gap: 18, maxWidth: 620 }}>
      <p className="muted" style={{ fontSize: 'var(--fs-md)', lineHeight: 1.55 }}>
        {t('settings.extraction.intro')}
      </p>

      {/* Default threshold */}
      <div>
        <span className="lbl">{t('settings.extraction.defaultThreshold')}</span>
        <p className="muted" style={{ fontSize: 'var(--fs-sm)', marginBottom: 8, lineHeight: 1.5 }}>
          {t('settings.extraction.defaultThresholdHint')}
        </p>
        <div className="row" style={{ gap: 12 }}>
          <Field
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={defaultThreshold}
            aria-label={t('settings.extraction.defaultThreshold')}
            onChange={(e) => {
              const v = parseFloat(e.target.value)
              if (!Number.isNaN(v) && v >= 0 && v <= 1) setDefaultThreshold(v)
            }}
            containerStyle={{ width: 110 }}
          />
          <Bar value={defaultThreshold * 100} width={140} />
          <span className="mono num muted" style={{ fontSize: 'var(--fs-sm)', fontWeight: 600 }}>
            {(defaultThreshold * 100).toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Per-field overrides */}
      <div className="col" style={{ gap: 8 }}>
        <span className="sec-t">{t('settings.extraction.perFieldOverrides')}</span>
        {Object.keys(fields).length === 0 ? (
          <p className="faint" style={{ fontSize: 'var(--fs-md)', fontStyle: 'italic' }}>
            {t('settings.extraction.noOverrides')}
          </p>
        ) : (
          <div className="col" style={{ gap: 8 }}>
            {Object.entries(fields).map(([field, value]) => (
              <div key={field} className="row" style={{ gap: 12 }}>
                <span style={{ width: 160, fontSize: 'var(--fs-md)' }}>
                  {t(`settings.extraction.fields.${field}`, { defaultValue: EXTRACTION_FIELD_LABELS[field] || field })}
                </span>
                <Field
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={value}
                  aria-label={t(`settings.extraction.fields.${field}`, { defaultValue: EXTRACTION_FIELD_LABELS[field] || field })}
                  onChange={(e) => updateField(field, e.target.value)}
                  containerStyle={{ width: 110 }}
                />
                <Bar value={value * 100} width={100} />
                <span className="mono num muted" style={{ fontSize: 'var(--fs-sm)', width: 40 }}>
                  {(value * 100).toFixed(0)}%
                </span>
                <IconButton
                  icon={TrashIcon}
                  size="sm"
                  label={t('settings.extraction.removeOverride')}
                  onClick={() => removeField(field)}
                />
              </div>
            ))}
          </div>
        )}

        {unsetFields.length > 0 && (
          <Select
            aria-label={t('settings.extraction.addFieldOverride')}
            containerStyle={{ maxWidth: 280 }}
            value=""
            onChange={(e) => {
              addField(e.target.value)
              e.currentTarget.value = ''
            }}
            options={[
              { value: '', label: t('settings.extraction.addFieldOverride') },
              ...unsetFields.map((f) => ({
                value: f,
                label: t(`settings.extraction.fields.${f}`, { defaultValue: EXTRACTION_FIELD_LABELS[f] || f }),
              })),
            ]}
          />
        )}
      </div>

      {error && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{error}</span>
        </div>
      )}

      {/* Save row */}
      <div className="row">
        <Button
          variant="primary"
          icon={CheckCircleIcon}
          onClick={handleSave}
          disabled={!isDirty || mutation.isPending}
        >
          {mutation.isPending ? t('settings.saving') : t('settings.extraction.saveThresholds')}
        </Button>
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
  const { toast } = useToast()
  const { data, isLoading } = useQuery({
    queryKey: ['prompt-addenda'],
    queryFn: getPromptAddenda,
  })

  const [draft, setDraft] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (data?.addenda) setDraft({ ...data.addenda })
  }, [data])

  const mutation = useMutation({
    mutationFn: (payload: Record<string, string>) => updatePromptAddenda(payload),
    onSuccess: (resp) => {
      setDraft({ ...resp.addenda })
      setError(null)
      toast({ text: t('settings.saved') })
      queryClient.invalidateQueries({ queryKey: ['prompt-addenda'] })
    },
    onError: (err: any) => {
      setError(err?.response?.data?.detail || err?.message || t('settings.prompts.saveFailed'))
    },
  })

  if (isLoading) {
    return (
      <div className="row" style={{ justifyContent: 'center', padding: 16 }}>
        <LoadingSpinner size="md" />
      </div>
    )
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
    <div className="col" style={{ gap: 14, maxWidth: 620 }}>
      <div>
        <span className="sec-t">{t('settings.prompts.title')}</span>
        <p className="muted" style={{ fontSize: 'var(--fs-md)', marginTop: 4, lineHeight: 1.55 }}>
          {t('settings.prompts.description', { maxChars })}
        </p>
      </div>

      <div className="col" style={{ gap: 14 }}>
        {PROMPT_ADDENDA_ORDER.map((agent) => {
          const info = PROMPT_ADDENDA_LABELS[agent]
          const value = draft[agent] || ''
          const over = value.length > maxChars
          return (
            <div key={agent}>
              <div className="row" style={{ marginBottom: 5 }}>
                <label className="lbl grow" style={{ marginBottom: 0 }}>
                  {t(`settings.prompts.labels.${agent}`, { defaultValue: info.label })}
                </label>
                <span
                  className="mono num"
                  style={{ fontSize: 'var(--fs-xs)', color: over ? 'var(--da)' : 'var(--f)', fontWeight: over ? 600 : undefined }}
                >
                  {value.length} / {maxChars}
                </span>
              </div>
              <div
                className="inp"
                style={{ height: 'auto', alignItems: 'stretch', ...(over ? { borderColor: 'var(--da-b)' } : undefined) }}
              >
                <textarea
                  value={value}
                  onChange={(e) => handleChange(agent, e.target.value)}
                  placeholder={t(`settings.prompts.placeholders.${agent}`, { defaultValue: info.placeholder })}
                  rows={3}
                  style={{ resize: 'vertical', padding: '8px 0' }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {error && (
        <div className="banner banner-da">
          <ExclamationTriangleIcon style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} aria-hidden />
          <span>{error}</span>
        </div>
      )}

      <div className="row">
        <Button
          variant="primary"
          icon={CheckCircleIcon}
          onClick={handleSave}
          disabled={!isDirty || mutation.isPending || Object.values(draft).some(v => (v || '').length > maxChars)}
        >
          {mutation.isPending ? t('settings.saving') : t('settings.prompts.savePromptAddenda')}
        </Button>
      </div>
    </div>
  )
}
