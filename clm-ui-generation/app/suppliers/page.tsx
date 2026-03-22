'use client'

import DashboardLayout from '@/components/dashboard-layout'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Users, TrendingUp, AlertCircle, Phone } from 'lucide-react'

export default function SuppliersPage() {
  const suppliers = [
    {
      id: 1,
      name: 'TNT Logistics',
      category: 'Transportation',
      status: 'Active',
      rating: '4.8/5',
      performance: '98%',
      contacts: 3,
      contracts: 2,
      riskLevel: 'Low',
    },
    {
      id: 2,
      name: 'ATOS Corporation',
      category: 'IT Services',
      status: 'Active',
      rating: '3.9/5',
      performance: '85%',
      contacts: 5,
      contracts: 3,
      riskLevel: 'High',
    },
    {
      id: 3,
      name: 'FM Global',
      category: 'Facilities',
      status: 'Active',
      rating: '4.2/5',
      performance: '92%',
      contacts: 2,
      contracts: 1,
      riskLevel: 'Medium',
    },
    {
      id: 4,
      name: 'Microsoft Enterprise',
      category: 'Software',
      status: 'Active',
      rating: '4.6/5',
      performance: '100%',
      contacts: 4,
      contracts: 1,
      riskLevel: 'Low',
    },
  ]

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'High':
        return 'bg-red-100 text-red-700'
      case 'Medium':
        return 'bg-yellow-100 text-yellow-700'
      case 'Low':
        return 'bg-green-100 text-green-700'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Supplier Management</h1>
            <p className="text-muted-foreground mt-1">Monitor supplier performance and relationships</p>
          </div>
          <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
            Add Supplier
          </Button>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {suppliers.map((supplier) => (
            <Card key={supplier.id} className="p-6 hover:shadow-lg transition-shadow duration-200">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-primary/10 rounded-lg">
                    <Users className="text-primary" size={24} />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-foreground">{supplier.name}</h3>
                    <p className="text-sm text-muted-foreground">{supplier.category}</p>
                  </div>
                </div>
                <Badge className={getRiskColor(supplier.riskLevel)}>
                  {supplier.riskLevel} Risk
                </Badge>
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Rating</p>
                    <div className="flex items-center gap-2">
                      <TrendingUp size={16} className="text-accent" />
                      <p className="font-semibold text-foreground">{supplier.rating}</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Performance</p>
                    <div className="flex items-center gap-2">
                      <div className="w-12 bg-secondary rounded-full h-1.5">
                        <div
                          className="bg-accent h-full rounded-full"
                          style={{ width: supplier.performance }}
                        />
                      </div>
                      <p className="font-semibold text-foreground text-sm">{supplier.performance}</p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4 pt-2 border-t border-border">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Contacts</p>
                    <p className="font-semibold text-foreground">{supplier.contacts}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Active Contracts</p>
                    <p className="font-semibold text-foreground">{supplier.contracts}</p>
                  </div>
                  <div className="flex items-end">
                    <Button variant="outline" size="sm" className="w-full">
                      <Phone size={16} className="mr-1" />
                      Contact
                    </Button>
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
