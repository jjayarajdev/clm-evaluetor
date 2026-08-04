/* Master data admin — Direction B restyle. Token header + ui Tabs primitive
   switching between the SLA and Milestone config panels (behavior unchanged). */
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { CircleStackIcon, FlagIcon } from '@heroicons/react/24/outline'
import { Tabs } from '@/components/ui'
import type { TabDef } from '@/components/ui'
import SLAConfigPanel from './SLAConfigPanel'
import MilestoneConfigPanel from './MilestoneConfigPanel'

type Tab = 'sla' | 'milestones'

export default function MasterDataPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState<Tab>('sla')

  const tabs: TabDef<Tab>[] = [
    { value: 'sla', label: t('masterdata.tabs.sla', { defaultValue: 'SLA Configurations' }), icon: CircleStackIcon },
    { value: 'milestones', label: t('masterdata.tabs.milestones', { defaultValue: 'Milestone Configurations' }), icon: FlagIcon },
  ]

  return (
    <div className="col" style={{ gap: 18 }}>
      <div>
        <h1 style={{ fontSize: 'var(--fs-3xl)', fontWeight: 600, letterSpacing: '-.5px' }}>
          {t('nav.masterData')}
        </h1>
        <p className="muted" style={{ marginTop: 2, fontSize: 'var(--fs-md)' }}>
          {t('masterdata.subtitle')}
        </p>
      </div>

      {/* Tabs */}
      <Tabs tabs={tabs} value={activeTab} onChange={setActiveTab} />

      {/* Tab Content */}
      {activeTab === 'sla' && <SLAConfigPanel />}
      {activeTab === 'milestones' && <MilestoneConfigPanel />}
    </div>
  )
}
