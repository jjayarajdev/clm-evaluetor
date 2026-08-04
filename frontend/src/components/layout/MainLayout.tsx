import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import ErrorBoundary from '@/components/ErrorBoundary'
import CommandPalette from '@/components/ui/CommandPalette'

/* Direction B shell: in-flow sidebar column + top bar + scrollable content.
   Relies on the html/body/#root height chain set in index.css. */
export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="flex h-full overflow-hidden" style={{ background: 'var(--pg)' }}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header onMenuClick={() => setSidebarOpen(true)} />

        <main className="scroll flex-1 min-h-0">
          <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
            {/* Contain page crashes so one bad component doesn't blank the app.
                Resets on navigation so moving away from a broken page recovers. */}
            <ErrorBoundary resetKey={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>
        </main>
      </div>

      <CommandPalette />
    </div>
  )
}
