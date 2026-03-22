'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/dashboard-layout'
import VendorScoring from '@/components/vendor-scoring'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApi } from '@/hooks/use-api'
import { APIClient } from '@/lib/api-client'
import { Search, Filter } from 'lucide-react'

export default function VendorPage() {
  const [searchTerm, setSearchTerm] = useState('')

  const { data: vendors } = useApi(
    () => APIClient.getVendors({ page_size: 50 }),
    []
  )

  const vendorList = vendors?.vendors || []

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Vendor Management</h1>
          <p className="text-muted-foreground mt-1">
            Monitor vendor performance, scores, and strategic relationships
          </p>
        </div>

        {/* Vendor Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Vendors</p>
            <p className="text-2xl font-bold">{vendorList.length}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Avg Score</p>
            <p className="text-2xl font-bold">
              {(
                vendorList.reduce((sum: number, v: any) => sum + (v.overall_score || 0), 0) /
                  (vendorList.length || 1) || 0
              ).toFixed(1)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">High Performers</p>
            <p className="text-2xl font-bold text-accent">
              {vendorList.filter((v: any) => (v.overall_score || 0) >= 90).length}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">At Risk</p>
            <p className="text-2xl font-bold text-destructive">
              {vendorList.filter((v: any) => (v.overall_score || 0) < 60).length}
            </p>
          </Card>
        </div>

        <VendorScoring />
      </div>
    </DashboardLayout>
  )
}
