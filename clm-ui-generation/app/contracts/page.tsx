'use client'

import DashboardLayout from '@/components/dashboard-layout'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { FileText, Calendar, User, TrendingUp } from 'lucide-react'

export default function ContractsPage() {
  const contracts = [
    {
      id: 1,
      name: 'TNT Express Services SLA',
      supplier: 'TNT Logistics',
      value: '$250,000',
      startDate: 'Jan 2024',
      endDate: 'Dec 2024',
      status: 'Active',
      compliance: '98%',
    },
    {
      id: 2,
      name: 'ATOS IT Infrastructure',
      supplier: 'ATOS Corporation',
      value: '$1,200,000',
      startDate: 'Mar 2023',
      endDate: 'Mar 2025',
      status: 'Active',
      compliance: '85%',
    },
    {
      id: 3,
      name: 'Facility Management',
      supplier: 'FM Global',
      value: '$180,000',
      startDate: 'Jun 2024',
      endDate: 'May 2025',
      status: 'Active',
      compliance: '92%',
    },
    {
      id: 4,
      name: 'Software Licensing',
      supplier: 'Microsoft Enterprise',
      value: '$450,000',
      startDate: 'Jan 2024',
      endDate: 'Dec 2024',
      status: 'Expiring Soon',
      compliance: '100%',
    },
  ]

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Contracts Management</h1>
            <p className="text-muted-foreground mt-1">Overview of all active and expiring contracts</p>
          </div>
          <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
            New Contract
          </Button>
        </div>

        <div className="grid gap-6">
          {contracts.map((contract) => (
            <Card key={contract.id} className="p-6 hover:shadow-lg transition-shadow duration-200">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-primary/10 rounded-lg">
                    <FileText className="text-primary" size={24} />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-foreground">{contract.name}</h3>
                    <p className="text-sm text-muted-foreground">{contract.supplier}</p>
                  </div>
                </div>
                <Badge variant={contract.status === 'Active' ? 'default' : 'secondary'}>
                  {contract.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Contract Value</p>
                  <p className="font-semibold text-foreground">{contract.value}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Start Date</p>
                  <div className="flex items-center gap-2">
                    <Calendar size={16} className="text-primary" />
                    <p className="font-semibold text-foreground">{contract.startDate}</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">End Date</p>
                  <div className="flex items-center gap-2">
                    <Calendar size={16} className="text-accent" />
                    <p className="font-semibold text-foreground">{contract.endDate}</p>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Compliance</p>
                  <div className="flex items-center gap-2">
                    <div className="w-12 bg-secondary rounded-full h-1.5">
                      <div
                        className="bg-accent h-full rounded-full"
                        style={{ width: contract.compliance }}
                      />
                    </div>
                    <p className="font-semibold text-foreground text-sm">{contract.compliance}</p>
                  </div>
                </div>
                <div className="flex items-end">
                  <Button variant="outline" size="sm" className="w-full">
                    View Details
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </DashboardLayout>
  )
}
