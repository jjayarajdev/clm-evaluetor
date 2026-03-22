'use client'

import { useState } from 'react'
import DashboardLayout from '@/components/dashboard-layout'
import VendorScoring from '@/components/vendor-scoring'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useApi } from '@/hooks/use-api'
import { APIClient } from '@/lib/api-client'
import { Search, Filter } from 'lucide-react'

export default function VendorManagementPage() {
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('')

  const { data: vendors, loading } = useApi(
    () =>
      APIClient.getVendors({
        page_size: 50,
        search: searchTerm || undefined,
        status: selectedCategory || undefined,
      }),
    [searchTerm, selectedCategory]
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

        {/* Search and Filter */}
        <Card className="p-6">
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-3 text-muted-foreground" size={20} />
                <input
                  type="text"
                  placeholder="Search vendors by name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <Button
                variant="outline"
                className="flex items-center gap-2"
                onClick={() => setSearchTerm('')}
              >
                <Filter size={16} />
                Reset
              </Button>
            </div>

            {/* Categories */}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setSelectedCategory('')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  selectedCategory === ''
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                }`}
              >
                All Vendors
              </button>
              {['Active', 'Inactive', 'On Probation', 'Preferred'].map((category) => (
                <button
                  key={category}
                  onClick={() => setSelectedCategory(category)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedCategory === category
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
                  }`}
                >
                  {category}
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* Vendor List Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Vendors</p>
            <p className="text-2xl font-bold">{vendorList.length}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Active</p>
            <p className="text-2xl font-bold text-accent">
              {vendorList.filter((v: any) => v.status === 'Active').length}
            </p>
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
            <p className="text-sm text-muted-foreground">At Risk</p>
            <p className="text-2xl font-bold text-destructive">
              {vendorList.filter((v: any) => (v.overall_score || 0) < 60).length}
            </p>
          </Card>
        </div>

        <VendorScoring />

        {/* Strategic Partnerships */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Strategic Partnership Opportunities</h3>
          <div className="space-y-3">
            <div className="p-4 bg-accent/5 border border-accent/20 rounded-lg">
              <p className="font-medium text-sm mb-1">Top Performers</p>
              <p className="text-xs text-muted-foreground">
                Consider expanding engagement with vendors scoring above 90
              </p>
            </div>
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="font-medium text-sm mb-1">Development Needed</p>
              <p className="text-xs text-muted-foreground">
                Vendors scoring 60-75 require performance improvement plans
              </p>
            </div>
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="font-medium text-sm mb-1">Critical Review</p>
              <p className="text-xs text-muted-foreground">
                Vendors below 60 should be reviewed for contingency planning
              </p>
            </div>
          </div>
        </Card>
      </div>
    </DashboardLayout>
  )
}
