'use client'

import { Card } from '@/components/ui/card'
import { useApi } from '@/hooks/use-api'
import { APIClient } from '@/lib/api-client'
import { Star, TrendingDown, TrendingUp, Award } from 'lucide-react'

export default function VendorScoring() {
  const { data: vendors, loading } = useApi(
    () => APIClient.getVendors({ page_size: 10 }),
    []
  )

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 bg-muted rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  const vendorList = vendors?.vendors || []

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-accent'
    if (score >= 75) return 'text-yellow-500'
    if (score >= 60) return 'text-orange-500'
    return 'text-destructive'
  }

  const getScoreBgColor = (score: number) => {
    if (score >= 90) return 'bg-accent/10 border-accent/30'
    if (score >= 75) return 'bg-yellow-50 border-yellow-200'
    if (score >= 60) return 'bg-orange-50 border-orange-200'
    return 'bg-red-50 border-red-200'
  }

  const getTrendIcon = (trend: string) => {
    return trend === 'up' ? (
      <TrendingUp className="text-accent" size={16} />
    ) : (
      <TrendingDown className="text-destructive" size={16} />
    )
  }

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold">Vendor Performance Scores</h3>
            <p className="text-sm text-muted-foreground">
              Top vendors ranked by overall performance metrics
            </p>
          </div>
          <Award className="text-primary" size={24} />
        </div>

        <div className="space-y-4">
          {vendorList.length > 0 ? (
            vendorList.map((vendor: any, index: number) => (
              <div
                key={vendor.id}
                className={`p-4 rounded-lg border transition-all hover:shadow-sm ${getScoreBgColor(
                  vendor.overall_score || 0
                )}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="text-xl font-bold text-muted-foreground">#{index + 1}</span>
                      <div>
                        <p className="font-semibold">{vendor.name}</p>
                        <p className="text-xs text-muted-foreground">{vendor.category}</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6 text-right">
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Overall Score</p>
                      <div className="flex items-center gap-2">
                        <p className={`text-2xl font-bold ${getScoreColor(vendor.overall_score || 0)}`}>
                          {(vendor.overall_score || 0).toFixed(1)}
                        </p>
                        <div className="flex">
                          {[...Array(5)].map((_, i) => (
                            <Star
                              key={i}
                              size={14}
                              className={
                                i < Math.round((vendor.overall_score || 0) / 20)
                                  ? 'fill-accent text-accent'
                                  : 'text-muted'
                              }
                            />
                          ))}
                        </div>
                      </div>
                    </div>

                    {vendor.score_trend && (
                      <div className="flex items-center gap-1">
                        {getTrendIcon(vendor.score_trend)}
                        <span className="text-xs font-medium">
                          {vendor.score_trend === 'up' ? '+' : '−'}
                          {Math.abs(vendor.trend_value || 0).toFixed(1)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Sub-metrics */}
                {vendor.metrics && (
                  <div className="mt-4 pt-4 border-t border-current/10 grid grid-cols-2 md:grid-cols-4 gap-4">
                    {Object.entries(vendor.metrics).map(([key, value]: [string, any]) => (
                      <div key={key} className="text-sm">
                        <p className="text-xs text-muted-foreground capitalize">
                          {key.replace(/_/g, ' ')}
                        </p>
                        <p className="font-semibold">{typeof value === 'number' ? value.toFixed(1) : value}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="text-center py-8">
              <p className="text-muted-foreground">No vendor data available</p>
            </div>
          )}
        </div>
      </Card>

      {/* Scoring Criteria */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Scoring Criteria</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-3 h-3 rounded-full bg-accent mt-1.5 flex-shrink-0" />
              <div>
                <p className="font-medium text-sm">Quality & Compliance</p>
                <p className="text-xs text-muted-foreground">Product/service quality and regulatory compliance</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-3 h-3 rounded-full bg-primary mt-1.5 flex-shrink-0" />
              <div>
                <p className="font-medium text-sm">Delivery & Performance</p>
                <p className="text-xs text-muted-foreground">On-time delivery and SLA adherence</p>
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-3 h-3 rounded-full bg-yellow-500 mt-1.5 flex-shrink-0" />
              <div>
                <p className="font-medium text-sm">Cost & Value</p>
                <p className="text-xs text-muted-foreground">Price competitiveness and ROI</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <div className="w-3 h-3 rounded-full bg-orange-500 mt-1.5 flex-shrink-0" />
              <div>
                <p className="font-medium text-sm">Risk & Stability</p>
                <p className="text-xs text-muted-foreground">Financial health and business continuity</p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
