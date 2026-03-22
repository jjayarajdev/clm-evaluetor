'use client'

import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/card'
import { FileText, TrendingUp } from 'lucide-react'

export default function ContractOverview() {
  const router = useRouter()
  const stats = [
    { label: 'Active Contracts', value: '24', trend: '+2' },
    { label: 'Compliance Score', value: '94%', trend: '+5%' },
    { label: 'At Risk', value: '3', trend: '-1' },
  ]

  return (
    <Card className="p-6 lg:col-span-1 bg-gradient-to-br from-card to-card/50 border border-border/50 backdrop-blur hover:border-primary/30 transition-all duration-300 shadow-xl hover:shadow-primary/20">
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-primary/30 to-accent/20 rounded-xl backdrop-blur">
            <FileText className="text-primary" size={24} />
          </div>
          <div>
            <h3 className="text-sm text-muted-foreground font-medium">Contracts</h3>
            <p className="text-3xl font-bold text-foreground">24</p>
          </div>
        </div>

        <div className="space-y-3 pt-3 border-t border-border/30">
          {stats.map((stat) => (
            <div key={stat.label} className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">{stat.label}</span>
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold text-foreground">{stat.value}</span>
                <span className="text-xs px-2.5 py-1 bg-accent/20 text-accent rounded-full font-medium">
                  {stat.trend}
                </span>
              </div>
            </div>
          ))}
        </div>

        <button
          onClick={() => router.push('/contracts')}
          className="w-full py-2.5 px-4 bg-gradient-to-r from-primary to-accent text-primary-foreground rounded-xl text-sm font-semibold hover:shadow-lg hover:shadow-primary/30 transition-all duration-200 mt-4"
        >
          View All Contracts
        </button>
      </div>
    </Card>
  )
}
