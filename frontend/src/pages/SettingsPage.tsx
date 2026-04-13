import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Cog6ToothIcon,
  BellIcon,
  ShieldCheckIcon,
  CloudIcon,
  PaintBrushIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import LoadingSpinner from '@/components/ui/LoadingSpinner'

type SettingsTab = 'general' | 'notifications' | 'security' | 'integrations' | 'appearance'

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
]

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('general')

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Manage your application preferences
        </p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-64 shrink-0">
          <nav className="space-y-1">
            {sections.map((section) => (
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
                {section.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1">
          <div className="card">
            <div className="card-header">
              <h2 className="text-lg font-medium text-gray-900">
                {sections.find((s) => s.id === activeTab)?.name}
              </h2>
              <p className="text-sm text-gray-500">
                {sections.find((s) => s.id === activeTab)?.description}
              </p>
            </div>
            <div className="card-body">
              {activeTab === 'general' && <GeneralSettings />}
              {activeTab === 'notifications' && <NotificationSettings />}
              {activeTab === 'security' && <SecuritySettings />}
              {activeTab === 'integrations' && <IntegrationSettings />}
              {activeTab === 'appearance' && <AppearanceSettings />}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function GeneralSettings() {
  const { user } = useAuth()
  const [settings, setSettings] = useState({
    orgName: user?.tenant_name || 'My Organization',
    currency: 'USD',
    dateFormat: 'MM/DD/YYYY',
  })
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    // Settings are stored locally for now — backend tenant settings API can be wired up later
    localStorage.setItem('clm_settings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Organization Name
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
          Default Currency
        </label>
        <select
          className="input max-w-md"
          value={settings.currency}
          onChange={(e) => setSettings(s => ({ ...s, currency: e.target.value }))}
        >
          <option value="USD">USD - US Dollar</option>
          <option value="EUR">EUR - Euro</option>
          <option value="GBP">GBP - British Pound</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Date Format
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
        <button className="btn-primary" onClick={handleSave}>Save Changes</button>
        {saved && <span className="text-sm text-green-600">Settings saved</span>}
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

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-gray-100 text-gray-700',
  normal: 'bg-blue-100 text-blue-700',
  high: 'bg-amber-100 text-amber-700',
  critical: 'bg-red-100 text-red-700',
}

function NotificationSettings() {
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
          <h3 className="text-sm font-medium text-gray-900">Notification Rules</h3>
          <p className="text-xs text-gray-500">Configure when and how you receive notifications</p>
        </div>
        <button
          onClick={() => setShowTemplates(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700"
        >
          <PlusIcon className="h-4 w-4" />
          Add Rule
        </button>
      </div>

      {/* Templates Modal */}
      {showTemplates && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl w-full max-w-lg mx-4 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              Choose a Rule Template
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
                      {template.priority}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500">{template.description}</p>
                  <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                    <span>{EVENT_TYPE_LABELS[template.event_type] || template.event_type}</span>
                    <span>•</span>
                    <span>{template.days_before} days before</span>
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
                Cancel
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
                      {rule.priority}
                    </span>
                    {!rule.is_active && (
                      <span className="px-2 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
                        Disabled
                      </span>
                    )}
                  </div>
                  {rule.description && (
                    <p className="text-sm text-gray-500 mb-2">{rule.description}</p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span className="px-2 py-0.5 bg-gray-100 rounded">
                      {EVENT_TYPE_LABELS[rule.event_type] || rule.event_type}
                    </span>
                    <span>{rule.days_before} days before</span>
                    <span>{rule.channels.join(', ')}</span>
                    {rule.trigger_count > 0 && (
                      <span className="text-green-600">
                        Triggered {rule.trigger_count} times
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
                      if (confirm('Are you sure you want to delete this rule?')) {
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
          <p className="text-sm font-medium mb-1">No notification rules configured</p>
          <p className="text-xs">Add rules to get notified about important contract events</p>
        </div>
      )}
    </div>
  )
}

function SecuritySettings() {
  const { user } = useAuth()
  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' })
  const [passwordError, setPasswordError] = useState('')
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  const handleUpdatePassword = async () => {
    setPasswordError('')
    if (!passwords.current || !passwords.newPass || !passwords.confirm) {
      setPasswordError('All fields are required')
      return
    }
    if (passwords.newPass.length < 6) {
      setPasswordError('New password must be at least 6 characters')
      return
    }
    if (passwords.newPass !== passwords.confirm) {
      setPasswordError('Passwords do not match')
      return
    }
    try {
      await api.updateUserPassword(user!.id, passwords.newPass)
      setPasswords({ current: '', newPass: '', confirm: '' })
      setPasswordSuccess(true)
      setTimeout(() => setPasswordSuccess(false), 3000)
    } catch (err: any) {
      setPasswordError(err?.response?.data?.detail || 'Failed to update password')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-3">Change Password</h3>
        <div className="space-y-3 max-w-md">
          <input
            type="password"
            placeholder="Current password"
            value={passwords.current}
            onChange={(e) => setPasswords(p => ({ ...p, current: e.target.value }))}
            className="input"
          />
          <input
            type="password"
            placeholder="New password"
            value={passwords.newPass}
            onChange={(e) => setPasswords(p => ({ ...p, newPass: e.target.value }))}
            className="input"
          />
          <input
            type="password"
            placeholder="Confirm new password"
            value={passwords.confirm}
            onChange={(e) => setPasswords(p => ({ ...p, confirm: e.target.value }))}
            className="input"
          />
          <div className="flex items-center gap-3">
            <button className="btn-primary" onClick={handleUpdatePassword}>Update Password</button>
            {passwordSuccess && <span className="text-sm text-green-600">Password updated</span>}
          </div>
          {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
        </div>
      </div>
      <div className="pt-4 border-t border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-3">Two-Factor Authentication</h3>
        <p className="text-sm text-gray-500 mb-3">
          Add an extra layer of security to your account
        </p>
        <div className="flex items-center gap-2">
          <button className="btn-secondary opacity-60 cursor-not-allowed" disabled>Enable 2FA</button>
          <span className="text-xs text-gray-400">Coming soon</span>
        </div>
      </div>
      <div className="pt-4 border-t border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-3">Active Sessions</h3>
        <p className="text-sm text-gray-500 mb-3">
          Manage your active sessions across devices
        </p>
        <div className="flex items-center gap-2">
          <button className="btn-secondary text-red-600 hover:text-red-700 opacity-60 cursor-not-allowed" disabled>
            Sign Out All Devices
          </button>
          <span className="text-xs text-gray-400">Coming soon</span>
        </div>
      </div>
    </div>
  )
}

function IntegrationSettings() {
  const integrations = [
    { name: 'OpenAI', description: 'AI-powered contract analysis', connected: true, configurable: false },
    { name: 'ServiceNow', description: 'SLA sync and incident management', connected: false, configurable: true, configPath: '/admin/servicenow' },
    { name: 'Microsoft Teams', description: 'Send notifications to Teams channels', connected: false, configurable: false },
    { name: 'Slack', description: 'Send notifications to Slack', connected: false, configurable: false },
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
              Connected
            </span>
          ) : integration.configurable ? (
            <a
              href={integration.configPath}
              className="text-sm font-medium px-3 py-1.5 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200"
            >
              Configure
            </a>
          ) : (
            <span className="text-sm font-medium px-3 py-1.5 rounded-lg bg-gray-50 text-gray-400">
              Coming soon
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

function AppearanceSettings() {
  const [theme, setTheme] = useState('light')

  const themes = [
    { id: 'light', label: 'Light', preview: 'bg-white border border-gray-200' },
    { id: 'dark', label: 'Dark', preview: 'bg-gray-800', disabled: true },
    { id: 'system', label: 'System', preview: 'bg-gradient-to-b from-white to-gray-800', disabled: true },
  ]

  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Theme
        </label>
        <div className="flex gap-3">
          {themes.map((t) => (
            <button
              key={t.id}
              onClick={() => !t.disabled && setTheme(t.id)}
              className={cn(
                'flex-1 p-4 border-2 rounded-lg bg-white transition-colors',
                theme === t.id ? 'border-primary-500' : 'border-gray-200 hover:border-gray-300',
                t.disabled && 'opacity-50 cursor-not-allowed',
              )}
            >
              <div className={cn('h-16 rounded mb-2', t.preview)} />
              <div className="flex items-center justify-center gap-1">
                <p className="text-sm font-medium text-gray-900">{t.label}</p>
                {t.disabled && <span className="text-[10px] text-gray-400">(soon)</span>}
              </div>
            </button>
          ))}
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Sidebar Position
        </label>
        <div className="flex items-center gap-2">
          <select className="input max-w-md opacity-60" disabled>
            <option value="left">Left</option>
            <option value="right">Right</option>
          </select>
          <span className="text-xs text-gray-400">Coming soon</span>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Density
        </label>
        <div className="flex items-center gap-2">
          <select className="input max-w-md opacity-60" disabled>
            <option value="comfortable">Comfortable</option>
            <option value="compact">Compact</option>
          </select>
          <span className="text-xs text-gray-400">Coming soon</span>
        </div>
      </div>
    </div>
  )
}
