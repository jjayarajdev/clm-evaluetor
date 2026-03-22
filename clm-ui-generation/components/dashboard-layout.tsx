'use client'

import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  LayoutGrid,
  BarChart3,
  AlertCircle,
  Users,
  Settings,
  LogOut,
  Bell,
  Zap,
  Award,
  Sparkles,
} from 'lucide-react'

interface DashboardLayoutProps {
  children: React.ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const pathname = usePathname()
  const router = useRouter()

  const menuItems = [
    { icon: LayoutGrid, label: 'Dashboard', href: '/' },
    { icon: BarChart3, label: 'Contracts', href: '/contracts' },
    { icon: AlertCircle, label: 'Risk Register', href: '/risk-register' },
    { icon: Users, label: 'Suppliers', href: '/suppliers' },
    { icon: Zap, label: 'SLA Tracking', href: '/sla-tracking' },
    { icon: Award, label: 'Vendors', href: '/vendors' },
    { icon: Settings, label: 'Governance', href: '/governance' },
  ]

  const isActive = (href: string) => pathname === href

  return (
    <div className="flex h-screen bg-background">
      {/* Modern Sidebar */}
      <aside className="w-72 bg-gradient-to-b from-sidebar-background via-sidebar-background to-[rgb(10,10,14)] border-r border-sidebar-border flex flex-col">
        {/* Logo Area */}
        <div className="p-6 border-b border-sidebar-border/50 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-primary to-accent rounded-lg flex items-center justify-center">
              <Sparkles size={24} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-foreground">Evaluetor</h1>
              <p className="text-xs text-muted-foreground">Contract Platform</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {menuItems.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group relative ${
                isActive(item.href)
                  ? 'bg-gradient-to-r from-primary/30 to-accent/20 text-primary shadow-lg shadow-primary/20'
                  : 'text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50'
              }`}
            >
              {isActive(item.href) && (
                <div className="absolute inset-0 bg-gradient-to-r from-primary/20 to-transparent rounded-xl blur opacity-50" />
              )}
              <item.icon size={20} className="flex-shrink-0 relative z-10" />
              <span className="text-sm font-medium relative z-10">{item.label}</span>
              {isActive(item.href) && (
                <div className="ml-auto w-2 h-2 bg-accent rounded-full" />
              )}
            </Link>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-sidebar-border/50 space-y-2">
          <button
            onClick={() => alert('Settings page (coming soon)')}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-muted-foreground hover:text-foreground hover:bg-sidebar-accent/50 transition-all duration-200"
          >
            <Settings size={20} />
            <span className="text-sm font-medium">Settings</span>
          </button>
          <button
            onClick={() => {
              alert('Signing out...')
              router.push('/')
            }}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-destructive hover:bg-destructive/10 transition-all duration-200"
          >
            <LogOut size={20} />
            <span className="text-sm font-medium">Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="bg-gradient-to-r from-card to-card/50 border-b border-border/50 h-20 flex items-center justify-between px-8 backdrop-blur-sm">
          <div>
            <h2 className="text-3xl font-bold bg-gradient-to-r from-primary via-accent to-primary bg-clip-text text-transparent">
              Executive Monitor
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Real-time intelligence platform
            </p>
          </div>
          <div className="flex items-center gap-6">
            <button
              onClick={() => alert('Notifications: 1 new alert about supplier performance')}
              className="relative p-3 text-muted-foreground hover:text-foreground transition-all duration-200 rounded-lg hover:bg-sidebar-accent/50 group"
            >
              <Bell size={22} />
              <span className="absolute top-2 right-2 w-2.5 h-2.5 bg-accent rounded-full animate-pulse" />
            </button>
            <button
              onClick={() => alert('User profile menu (coming soon)')}
              className="w-12 h-12 bg-gradient-to-br from-primary to-accent rounded-xl flex items-center justify-center text-primary-foreground font-bold hover:shadow-lg hover:shadow-primary/40 transition-all duration-200"
            >
              AD
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-8 space-y-6">
          <div className="space-y-6">{children}</div>
        </main>
      </div>
    </div>
  )
}
