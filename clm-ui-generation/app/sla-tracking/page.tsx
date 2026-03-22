'use client'

import DashboardLayout from '@/components/dashboard-layout'
import SLADashboard from '@/components/sla-dashboard'
import { Card } from '@/components/ui/card'
import { AlertTriangle, TrendingUp, Clock } from 'lucide-react'

export default function SLATrackingPage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground">SLA Tracking & Compliance</h1>
          <p className="text-muted-foreground mt-1">
            Monitor service level agreements, performance metrics, and compliance status
          </p>
        </div>

        <SLADashboard />

        {/* SLA Definition Help */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">SLA Metrics Reference</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <h4 className="font-medium flex items-center gap-2 mb-2">
                  <TrendingUp size={16} className="text-primary" />
                  Performance Metrics
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 ml-6">
                  <li>• Uptime Percentage: Availability target</li>
                  <li>• Response Time: Support/API response targets</li>
                  <li>• Resolution Time: Issue resolution targets</li>
                  <li>• Delivery Time: Service delivery targets</li>
                  <li>• Throughput: Transaction capacity</li>
                  <li>• Error Rate: Acceptable error levels</li>
                </ul>
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <h4 className="font-medium flex items-center gap-2 mb-2">
                  <AlertTriangle size={16} className="text-destructive" />
                  Breach Severity Levels
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 ml-6">
                  <li>🔴 Critical: Immediate escalation required</li>
                  <li>🟠 High: Urgent review and remediation</li>
                  <li>🟡 Medium: Schedule review and correction</li>
                  <li>🔵 Low: Monitor and improve over time</li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium flex items-center gap-2 mb-2">
                  <Clock size={16} className="text-primary" />
                  Measurement Periods
                </h4>
                <ul className="text-sm text-muted-foreground space-y-1 ml-6">
                  <li>• Daily: Continuous monitoring</li>
                  <li>• Weekly: Rolling week analysis</li>
                  <li>• Monthly: Standard measurement period</li>
                  <li>• Quarterly: Trend analysis</li>
                </ul>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  )
}
