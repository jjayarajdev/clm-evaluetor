'use client'

import { Card } from '@/components/ui/card'
import { TrendingUp } from 'lucide-react'

export default function PerformanceMetrics() {
  const metrics = [
    {
      label: 'Supplier Performance',
      value: '87%',
      color: 'bg-green-500',
      status: 'Above Target',
    },
    {
      label: 'Delivery On-Time',
      value: '92%',
      color: 'bg-blue-500',
      status: 'Excellent',
    },
    {
      label: 'Cost Efficiency',
      value: '78%',
      color: 'bg-yellow-500',
      status: 'Good',
    },
  ]

  return (
    <Card className="p-6 lg:col-span-1 bg-gradient-to-br from-card to-card/50 border border-border/50 backdrop-blur hover:border-accent/30 transition-all duration-300 shadow-xl hover:shadow-accent/20">
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-accent/30 to-primary/20 rounded-xl backdrop-blur">
            <TrendingUp className="text-accent" size={24} />
          </div>
          <div>
            <h3 className="text-sm text-muted-foreground font-medium">Performance Metrics</h3>
            <p className="text-3xl font-bold text-foreground">Q1 Average</p>
          </div>
        </div>

        <div className="space-y-4 pt-3 border-t border-border/30">
          {metrics.map((metric) => (
            <div key={metric.label} className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">{metric.label}</span>
                <span className="text-sm font-semibold text-accent">{metric.value}</span>
              </div>
              <div className="w-full bg-secondary/50 rounded-full h-2.5">
                <div
                  className={`${metric.color} h-2.5 rounded-full shadow-lg`}
                  style={{ width: metric.value }}
                />
              </div>
              <p className="text-xs text-muted-foreground">{metric.status}</p>
            </div>
          ))}
        </div>

        <button className="w-full py-2.5 px-4 border border-border/50 bg-gradient-to-r from-primary/20 to-accent/20 text-foreground rounded-xl text-sm font-semibold hover:border-primary/50 transition-all duration-200 mt-4">
          View Details
        </button>
      </div>
    </Card>
  )
}
