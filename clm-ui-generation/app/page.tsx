'use client'

import DashboardLayout from '@/components/dashboard-layout'
import ContractOverview from '@/components/contract-overview'
import PerformanceMetrics from '@/components/performance-metrics'
import RiskIndicators from '@/components/risk-indicators'
import RecentActivity from '@/components/recent-activity'
import SLADashboard from '@/components/sla-dashboard'
import VendorScoring from '@/components/vendor-scoring'

export default function Page() {
  return (
    <DashboardLayout>
      <div className="grid gap-6 lg:grid-cols-3">
        <ContractOverview />
        <PerformanceMetrics />
        <RiskIndicators />
      </div>

      <SLADashboard />

      <VendorScoring />

      <RecentActivity />
    </DashboardLayout>
  )
}
