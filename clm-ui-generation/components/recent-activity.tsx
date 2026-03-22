'use client'

import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/card'
import {
  CheckCircle,
  AlertCircle,
  FileText,
  MessageSquare,
  Clock,
  Users,
} from 'lucide-react'

export default function RecentActivity() {
  const router = useRouter()
  const activities = [
    {
      icon: CheckCircle,
      title: 'Contract Approved',
      description: 'TNT Express Services SLA - Agreement finalized',
      timestamp: '2 hours ago',
      color: 'text-green-600',
    },
    {
      icon: AlertCircle,
      title: 'Alert: Performance Below Target',
      description: 'ATOS delivery performance dropped to 85%',
      timestamp: '4 hours ago',
      color: 'text-yellow-600',
    },
    {
      icon: FileText,
      title: 'Document Uploaded',
      description: 'Q1 Performance Report - All metrics documented',
      timestamp: '6 hours ago',
      color: 'text-blue-600',
    },
    {
      icon: MessageSquare,
      title: 'Team Comment',
      description: 'Sarah commented on TNT contract compliance',
      timestamp: '1 day ago',
      color: 'text-purple-600',
    },
    {
      icon: Users,
      title: 'Supplier Meeting Scheduled',
      description: 'Q1 Review with TNT stakeholders - March 15',
      timestamp: '2 days ago',
      color: 'text-indigo-600',
    },
  ]

  return (
    <Card className="p-6">
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-bold text-foreground">Recent Activity</h3>
          <p className="text-sm text-muted-foreground">Team collaboration and contract updates</p>
        </div>

        <div className="space-y-4">
          {activities.map((activity, index) => (
            <div
              key={index}
              onClick={() => {
                if (activity.title.includes('Contract')) router.push('/contracts')
                else if (activity.title.includes('Alert') || activity.title.includes('Performance'))
                  router.push('/risk-register')
                else alert(`Viewing: ${activity.title}`)
              }}
              className="flex gap-4 p-4 rounded-lg border border-border hover:bg-secondary transition-colors duration-200 cursor-pointer group"
            >
              <div
                className={`p-2 rounded-lg bg-secondary flex-shrink-0 ${activity.color}`}
              >
                <activity.icon size={20} />
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h4 className="font-semibold text-foreground text-sm">
                      {activity.title}
                    </h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      {activity.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground flex-shrink-0">
                    <Clock size={14} />
                    {activity.timestamp}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="pt-4 border-t border-border">
          <button
            onClick={() => alert('Activity log page (coming soon)')}
            className="w-full py-2 px-4 text-primary text-sm font-medium hover:bg-primary/5 rounded-lg transition-colors duration-200"
          >
            View All Activity
          </button>
        </div>
      </div>
    </Card>
  )
}
