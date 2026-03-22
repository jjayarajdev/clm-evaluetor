'use client'

import DashboardLayout from '@/components/dashboard-layout'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react'

export default function RiskRegisterPage() {
  const risks = [
    {
      id: 1,
      title: 'ATOS Performance Decline',
      description: 'Delivery performance dropped from 95% to 85% in Q1',
      severity: 'High',
      contract: 'ATOS IT Infrastructure',
      dueDate: 'Mar 15, 2024',
      owner: 'John Smith',
      status: 'In Progress',
    },
    {
      id: 2,
      title: 'TNT SLA Compliance Gap',
      description: 'Response time metrics not meeting agreed targets',
      severity: 'High',
      contract: 'TNT Express Services',
      dueDate: 'Mar 10, 2024',
      owner: 'Sarah Johnson',
      status: 'Open',
    },
    {
      id: 3,
      title: 'FM Staffing Shortage',
      description: 'Facility management team reduced due to budget cuts',
      severity: 'Medium',
      contract: 'Facility Management',
      dueDate: 'Mar 20, 2024',
      owner: 'Michael Chen',
      status: 'Open',
    },
    {
      id: 4,
      title: 'Software License Renewal',
      description: 'Microsoft Enterprise licenses expiring in 3 months',
      severity: 'Medium',
      contract: 'Software Licensing',
      dueDate: 'Apr 1, 2024',
      owner: 'Emily Davis',
      status: 'Monitoring',
    },
    {
      id: 5,
      title: 'Data Security Audit',
      description: 'Annual compliance audit findings to be addressed',
      severity: 'Low',
      contract: 'ATOS IT Infrastructure',
      dueDate: 'Apr 30, 2024',
      owner: 'Robert Wilson',
      status: 'Scheduled',
    },
  ]

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'High':
        return 'bg-red-100 text-red-700'
      case 'Medium':
        return 'bg-yellow-100 text-yellow-700'
      case 'Low':
        return 'bg-blue-100 text-blue-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'In Progress':
        return <Clock size={16} />
      case 'Open':
        return <AlertTriangle size={16} />
      default:
        return <CheckCircle size={16} />
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Risk Register</h1>
            <p className="text-muted-foreground mt-1">Comprehensive risk tracking and mitigation actions</p>
          </div>
          <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
            Add Risk
          </Button>
        </div>

        <div className="space-y-3">
          {risks.map((risk) => (
            <Card key={risk.id} className="p-6 hover:shadow-lg transition-shadow duration-200">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-bold text-foreground">{risk.title}</h3>
                    <Badge className={getSeverityColor(risk.severity)}>
                      {risk.severity}
                    </Badge>
                    <Badge variant="outline" className="flex items-center gap-1">
                      {getStatusIcon(risk.status)}
                      {risk.status}
                    </Badge>
                  </div>
                  <p className="text-muted-foreground text-sm mb-3">{risk.description}</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Related Contract</p>
                      <p className="font-medium text-foreground">{risk.contract}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Due Date</p>
                      <p className="font-medium text-foreground">{risk.dueDate}</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground text-xs mb-1">Risk Owner</p>
                      <p className="font-medium text-foreground">{risk.owner}</p>
                    </div>
                    <div className="flex items-end">
                      <Button variant="outline" size="sm" className="w-full">
                        Update
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}
