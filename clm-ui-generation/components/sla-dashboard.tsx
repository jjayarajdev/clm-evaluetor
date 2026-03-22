'use client'

import { Card } from '@/components/ui/card'
import { useApi } from '@/hooks/use-api'
import { APIClient } from '@/lib/api-client'
import { AlertTriangle, TrendingUp, CheckCircle, Clock } from 'lucide-react'

export default function SLADashboard() {
  const { data: compliance, loading: complianceLoading } = useApi(
    () => APIClient.getSLACompliance(),
    []
  )

  const { data: breaches, loading: breachesLoading } = useApi(
    () => APIClient.getActiveSLABreaches(),
    []
  )

  if (complianceLoading || breachesLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-24 bg-muted rounded-lg" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="h-24 bg-muted rounded-lg" />
            <div className="h-24 bg-muted rounded-lg" />
            <div className="h-24 bg-muted rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  const complianceRate = compliance?.overall_compliance_rate || 0
  const totalBreaches = breaches?.total_breaches || 0
  const criticalBreaches = breaches?.critical?.length || 0
  const penaltyExposure = breaches?.total_penalty_exposure || 0

  return (
    <div className="space-y-6">
      {/* Compliance Overview */}
      <Card className="p-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold">SLA Compliance Overview</h3>
            <TrendingUp className="text-accent" size={24} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Overall Compliance</p>
              <p className="text-2xl font-bold">{complianceRate.toFixed(1)}%</p>
              <div className="w-full bg-secondary rounded-full h-2">
                <div
                  className={`h-2 rounded-full transition-all ${
                    complianceRate >= 95
                      ? 'bg-accent'
                      : complianceRate >= 80
                        ? 'bg-yellow-500'
                        : 'bg-destructive'
                  }`}
                  style={{ width: `${complianceRate}%` }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Total SLAs</p>
              <p className="text-2xl font-bold">{compliance?.total_slas || 0}</p>
              <p className="text-xs text-muted-foreground">
                {compliance?.total_active || 0} active
              </p>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Active Breaches</p>
              <p className="text-2xl font-bold text-destructive">{totalBreaches}</p>
              <p className="text-xs text-muted-foreground">
                {criticalBreaches} critical
              </p>
            </div>

            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Penalty Exposure</p>
              <p className="text-2xl font-bold">${penaltyExposure.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">This period</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Breaches by Severity */}
      {totalBreaches > 0 && (
        <Card className="p-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">SLA Breaches by Severity</h3>
              <AlertTriangle className="text-destructive" size={24} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 bg-red-50 rounded-lg border border-red-200">
                <p className="text-sm text-red-600 font-medium">Critical</p>
                <p className="text-2xl font-bold text-red-700">
                  {breaches?.critical?.length || 0}
                </p>
              </div>
              <div className="p-4 bg-orange-50 rounded-lg border border-orange-200">
                <p className="text-sm text-orange-600 font-medium">High</p>
                <p className="text-2xl font-bold text-orange-700">
                  {breaches?.high?.length || 0}
                </p>
              </div>
              <div className="p-4 bg-yellow-50 rounded-lg border border-yellow-200">
                <p className="text-sm text-yellow-600 font-medium">Medium</p>
                <p className="text-2xl font-bold text-yellow-700">
                  {breaches?.medium?.length || 0}
                </p>
              </div>
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-600 font-medium">Low</p>
                <p className="text-2xl font-bold text-blue-700">
                  {breaches?.low?.length || 0}
                </p>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Compliance by Metric Type */}
      {compliance?.by_metric_type && Object.keys(compliance.by_metric_type).length > 0 && (
        <Card className="p-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Compliance by Metric Type</h3>
            <div className="space-y-3">
              {Object.entries(compliance.by_metric_type).map(([metric, rate]: [string, any]) => (
                <div key={metric} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium capitalize">{metric.replace(/_/g, ' ')}</span>
                    <span className="text-sm font-bold">{rate.toFixed(1)}%</span>
                  </div>
                  <div className="w-full bg-secondary rounded-full h-2">
                    <div
                      className="h-2 rounded-full bg-accent transition-all"
                      style={{ width: `${rate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
