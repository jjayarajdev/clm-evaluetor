'use client'

import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { AlertTriangle } from 'lucide-react'

export default function RiskIndicators() {
  const router = useRouter()
  const risks = [
    { label: 'High Priority', count: 2, color: 'text-red-500', bgColor: 'bg-red-50' },
    { label: 'Medium Priority', count: 5, color: 'text-yellow-500', bgColor: 'bg-yellow-50' },
    { label: 'Low Priority', count: 8, color: 'text-blue-500', bgColor: 'bg-blue-50' },
  ]

  return (
    <Card className="p-6 lg:col-span-1 bg-gradient-to-br from-card to-card/50 border border-border/50 backdrop-blur hover:border-destructive/30 transition-all duration-300 shadow-xl hover:shadow-destructive/20">
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-destructive/30 to-red-900/20 rounded-xl backdrop-blur">
            <AlertTriangle className="text-destructive" size={24} />
          </div>
          <div>
            <h3 className="text-sm text-muted-foreground font-medium">Risk Register</h3>
            <p className="text-3xl font-bold text-foreground">15 Issues</p>
          </div>
        </div>

        <div className="space-y-2 pt-3 border-t border-border/30">
          {risks.map((risk) => (
            <div key={risk.label} className="p-3 rounded-xl bg-secondary/50 border border-border/30 backdrop-blur hover:border-border/50 transition-all">
              <div className="flex items-center justify-between">
                <span className={`text-sm font-medium ${risk.color}`}>{risk.label}</span>
                <span className={`text-lg font-bold ${risk.color}`}>{risk.count}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="pt-4 border-t border-border/30 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground font-medium">Go to Green Actions</span>
            <span className="text-sm font-semibold text-accent">8 Active</span>
          </div>
          <button
            onClick={() => router.push('/risk-register')}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-destructive to-red-600 text-destructive-foreground rounded-xl text-sm font-semibold hover:shadow-lg hover:shadow-destructive/30 transition-all duration-200"
          >
            View Risk Details
          </button>
        </div>
      </div>
    </Card>
  )
}
