import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'
import { CircleStackIcon, FlagIcon } from '@heroicons/react/24/outline'
import SLAConfigPanel from './SLAConfigPanel'
import MilestoneConfigPanel from './MilestoneConfigPanel'

type Tab = 'sla' | 'milestones'

const TABS: { key: Tab; label: string; icon: typeof CircleStackIcon }[] = [
  { key: 'sla', label: 'SLA Configurations', icon: CircleStackIcon },
  { key: 'milestones', label: 'Milestone Configurations', icon: FlagIcon },
]

export default function MasterDataPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<Tab>('sla')

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{t('nav.masterData')}</h1>
        <p className="mt-1 text-sm text-gray-500">
          {t('masterdata.subtitle')}
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6" aria-label="Tabs">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'flex items-center gap-2 py-3 px-1 border-b-2 text-sm font-medium transition-colors',
                activeTab === tab.key
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              )}
            >
              <tab.icon className="h-4 w-4" />
              {t(`masterdata.tabs.${tab.key}`, { defaultValue: tab.label })}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'sla' && <SLAConfigPanel />}
      {activeTab === 'milestones' && <MilestoneConfigPanel />}
    </div>
  )
}
