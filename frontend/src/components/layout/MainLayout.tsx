import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import ErrorBoundary from '@/components/ErrorBoundary'
import { useSidebar } from '@/contexts/SidebarContext'
import { cn } from '@/lib/utils'

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { collapsed } = useSidebar()
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content */}
      <div className={cn(
        'transition-all duration-200',
        collapsed ? 'lg:pl-[60px]' : 'lg:pl-[220px]'
      )}>
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <main className="py-6">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            {/* Contain page crashes so one bad component doesn't blank the app.
                Resets on navigation so moving away from a broken page recovers. */}
            <ErrorBoundary resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  )
}
