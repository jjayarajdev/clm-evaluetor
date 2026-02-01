import { useState } from 'react'
import {
  Cog6ToothIcon,
  BellIcon,
  ShieldCheckIcon,
  CloudIcon,
  PaintBrushIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

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
  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Organization Name
        </label>
        <input
          type="text"
          defaultValue="Acme Corporation"
          className="input max-w-md"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Default Currency
        </label>
        <select className="input max-w-md">
          <option value="USD">USD - US Dollar</option>
          <option value="EUR">EUR - Euro</option>
          <option value="GBP">GBP - British Pound</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Date Format
        </label>
        <select className="input max-w-md">
          <option value="MM/DD/YYYY">MM/DD/YYYY</option>
          <option value="DD/MM/YYYY">DD/MM/YYYY</option>
          <option value="YYYY-MM-DD">YYYY-MM-DD</option>
        </select>
      </div>
      <div className="pt-4">
        <button className="btn-primary">Save Changes</button>
      </div>
    </div>
  )
}

function NotificationSettings() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between py-3 border-b border-gray-200">
        <div>
          <p className="text-sm font-medium text-gray-900">Contract Expiration Alerts</p>
          <p className="text-xs text-gray-500">Get notified before contracts expire</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" defaultChecked className="sr-only peer" />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
        </label>
      </div>
      <div className="flex items-center justify-between py-3 border-b border-gray-200">
        <div>
          <p className="text-sm font-medium text-gray-900">Obligation Reminders</p>
          <p className="text-xs text-gray-500">Reminders for upcoming obligations</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" defaultChecked className="sr-only peer" />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
        </label>
      </div>
      <div className="flex items-center justify-between py-3 border-b border-gray-200">
        <div>
          <p className="text-sm font-medium text-gray-900">High Risk Alerts</p>
          <p className="text-xs text-gray-500">Notifications for high-risk clauses</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" defaultChecked className="sr-only peer" />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
        </label>
      </div>
      <div className="flex items-center justify-between py-3">
        <div>
          <p className="text-sm font-medium text-gray-900">Processing Complete</p>
          <p className="text-xs text-gray-500">Notify when document processing finishes</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" className="sr-only peer" />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
        </label>
      </div>
    </div>
  )
}

function SecuritySettings() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-3">Change Password</h3>
        <div className="space-y-3 max-w-md">
          <input
            type="password"
            placeholder="Current password"
            className="input"
          />
          <input
            type="password"
            placeholder="New password"
            className="input"
          />
          <input
            type="password"
            placeholder="Confirm new password"
            className="input"
          />
          <button className="btn-primary">Update Password</button>
        </div>
      </div>
      <div className="pt-4 border-t border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-3">Two-Factor Authentication</h3>
        <p className="text-sm text-gray-500 mb-3">
          Add an extra layer of security to your account
        </p>
        <button className="btn-secondary">Enable 2FA</button>
      </div>
      <div className="pt-4 border-t border-gray-200">
        <h3 className="text-sm font-medium text-gray-900 mb-3">Active Sessions</h3>
        <p className="text-sm text-gray-500 mb-3">
          Manage your active sessions across devices
        </p>
        <button className="btn-secondary text-red-600 hover:text-red-700">
          Sign Out All Devices
        </button>
      </div>
    </div>
  )
}

function IntegrationSettings() {
  const integrations = [
    { name: 'OpenAI', description: 'AI-powered contract analysis', connected: true },
    { name: 'Google Drive', description: 'Import contracts from Drive', connected: false },
    { name: 'Dropbox', description: 'Import contracts from Dropbox', connected: false },
    { name: 'Slack', description: 'Send notifications to Slack', connected: false },
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
          <button
            className={cn(
              'text-sm font-medium px-3 py-1.5 rounded-lg',
              integration.connected
                ? 'bg-green-100 text-green-700'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            )}
          >
            {integration.connected ? 'Connected' : 'Connect'}
          </button>
        </div>
      ))}
    </div>
  )
}

function AppearanceSettings() {
  return (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Theme
        </label>
        <div className="flex gap-3">
          <button className="flex-1 p-4 border-2 border-primary-500 rounded-lg bg-white">
            <div className="h-16 bg-white border border-gray-200 rounded mb-2" />
            <p className="text-sm font-medium text-gray-900">Light</p>
          </button>
          <button className="flex-1 p-4 border-2 border-gray-200 rounded-lg bg-white hover:border-gray-300">
            <div className="h-16 bg-gray-800 rounded mb-2" />
            <p className="text-sm font-medium text-gray-900">Dark</p>
          </button>
          <button className="flex-1 p-4 border-2 border-gray-200 rounded-lg bg-white hover:border-gray-300">
            <div className="h-16 bg-gradient-to-b from-white to-gray-800 rounded mb-2" />
            <p className="text-sm font-medium text-gray-900">System</p>
          </button>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Sidebar Position
        </label>
        <select className="input max-w-md">
          <option value="left">Left</option>
          <option value="right">Right</option>
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Density
        </label>
        <select className="input max-w-md">
          <option value="comfortable">Comfortable</option>
          <option value="compact">Compact</option>
        </select>
      </div>
    </div>
  )
}
