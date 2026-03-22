'use client'

import DashboardLayout from '@/components/dashboard-layout'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, CheckCircle, Calendar, User } from 'lucide-react'

export default function GovernancePage() {
  const policies = [
    {
      id: 1,
      title: 'Contract Approval Policy',
      description: 'Guidelines for contract review and approval process',
      version: '2.1',
      lastUpdated: 'Feb 10, 2024',
      owner: 'Compliance Team',
      status: 'Active',
    },
    {
      id: 2,
      title: 'Supplier Code of Conduct',
      description: 'Ethical standards and expectations for all suppliers',
      version: '1.5',
      lastUpdated: 'Jan 15, 2024',
      owner: 'Procurement',
      status: 'Active',
    },
    {
      id: 3,
      title: 'Performance Management Framework',
      description: 'KPIs and metrics for supplier evaluation',
      version: '3.0',
      lastUpdated: 'Dec 20, 2023',
      owner: 'Operations',
      status: 'Active',
    },
    {
      id: 4,
      title: 'Risk Assessment Matrix',
      description: 'Risk evaluation criteria and mitigation strategies',
      version: '2.2',
      lastUpdated: 'Nov 30, 2023',
      owner: 'Risk Management',
      status: 'Under Review',
    },
  ]

  const audits = [
    {
      id: 1,
      name: 'Annual Compliance Audit',
      date: 'Mar 1-15, 2024',
      status: 'Scheduled',
      auditor: 'Internal Audit Team',
      scope: 'All suppliers',
    },
    {
      id: 2,
      name: 'ATOS Performance Review',
      date: 'Feb 15-20, 2024',
      status: 'In Progress',
      auditor: 'Sarah Johnson',
      scope: 'IT Services',
    },
    {
      id: 3,
      name: 'Financial Audit Q4 2023',
      date: 'Completed Jan 20, 2024',
      status: 'Completed',
      auditor: 'External Auditors',
      scope: 'All contracts',
    },
  ]

  return (
    <DashboardLayout>
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Governance & Compliance</h1>
          <p className="text-muted-foreground mt-1">Policies, procedures, and audit management</p>
        </div>

        {/* Policies Section */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-foreground">Policies & Procedures</h2>
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
              Add Policy
            </Button>
          </div>

          <div className="grid gap-4">
            {policies.map((policy) => (
              <Card key={policy.id} className="p-6 hover:shadow-lg transition-shadow duration-200">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="p-3 bg-primary/10 rounded-lg flex-shrink-0">
                      <FileText className="text-primary" size={24} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="text-lg font-bold text-foreground">{policy.title}</h3>
                        <Badge variant={policy.status === 'Active' ? 'default' : 'secondary'}>
                          {policy.status}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground mb-3">{policy.description}</p>
                      <div className="flex flex-wrap gap-4 text-sm">
                        <div>
                          <p className="text-xs text-muted-foreground">Version</p>
                          <p className="font-medium text-foreground">{policy.version}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Last Updated</p>
                          <p className="font-medium text-foreground">{policy.lastUpdated}</p>
                        </div>
                        <div>
                          <p className="text-xs text-muted-foreground">Owner</p>
                          <p className="font-medium text-foreground">{policy.owner}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" className="flex-shrink-0">
                    View
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Audits Section */}
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-foreground">Audits & Reviews</h2>
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
              Schedule Audit
            </Button>
          </div>

          <div className="grid gap-4">
            {audits.map((audit) => (
              <Card key={audit.id} className="p-6 hover:shadow-lg transition-shadow duration-200">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-bold text-foreground">{audit.name}</h3>
                      <Badge
                        variant={
                          audit.status === 'Completed'
                            ? 'default'
                            : audit.status === 'In Progress'
                              ? 'secondary'
                              : 'outline'
                        }
                      >
                        {audit.status}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 text-sm">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Date</p>
                        <div className="flex items-center gap-2">
                          <Calendar size={16} className="text-primary" />
                          <p className="font-medium text-foreground">{audit.date}</p>
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Auditor</p>
                        <div className="flex items-center gap-2">
                          <User size={16} className="text-accent" />
                          <p className="font-medium text-foreground">{audit.auditor}</p>
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Scope</p>
                        <p className="font-medium text-foreground">{audit.scope}</p>
                      </div>
                      <div className="flex items-end">
                        <Button variant="outline" size="sm" className="w-full">
                          Details
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
