/**
 * Command Palette (Cmd+K / Ctrl+K)
 * Quick navigation and search for power users
 */
import { Fragment, useState, useEffect, useCallback } from 'react'
import { Dialog, Combobox, Transition } from '@headlessui/react'
import { useNavigate } from 'react-router-dom'
import {
  MagnifyingGlassIcon,
  DocumentTextIcon,
  HomeIcon,
  ArrowUpTrayIcon,
  ChartBarIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  SparklesIcon,
  ClockIcon,
  BuildingOfficeIcon,
  ScaleIcon,
  FolderIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline'
import { cn } from '@/lib/utils'

interface CommandItem {
  id: string
  name: string
  description?: string
  icon: React.ElementType
  shortcut?: string
  action: string | (() => void)
  category: 'navigation' | 'action' | 'recent'
}

const commands: CommandItem[] = [
  // Navigation
  { id: 'dashboard', name: 'Dashboard', description: 'Go to dashboard', icon: HomeIcon, shortcut: 'G D', action: '/dashboard', category: 'navigation' },
  { id: 'contracts', name: 'Contracts', description: 'Browse all contracts', icon: DocumentTextIcon, shortcut: 'G C', action: '/contracts', category: 'navigation' },
  { id: 'upload', name: 'Upload Contract', description: 'Upload new contracts', icon: ArrowUpTrayIcon, shortcut: 'G U', action: '/upload', category: 'navigation' },
  { id: 'compliance', name: 'Compliance', description: 'View compliance dashboard', icon: ScaleIcon, shortcut: 'G O', action: '/compliance', category: 'navigation' },
  { id: 'renewals', name: 'Renewals', description: 'Contract renewals calendar', icon: ClockIcon, shortcut: 'G R', action: '/renewals', category: 'navigation' },
  { id: 'vendors', name: 'Vendors', description: 'Vendor performance', icon: BuildingOfficeIcon, shortcut: 'G V', action: '/vendors', category: 'navigation' },
  { id: 'reports', name: 'Reports', description: 'Analytics and reports', icon: ChartBarIcon, shortcut: 'G A', action: '/reports', category: 'navigation' },

  // Actions
  { id: 'ask-ai', name: 'Ask AI', description: 'Query contracts with AI', icon: SparklesIcon, shortcut: '/', action: '/query', category: 'action' },
  { id: 'users', name: 'Manage Users', description: 'User administration', icon: UserGroupIcon, action: '/users', category: 'action' },
  { id: 'settings', name: 'Settings', description: 'Application settings', icon: Cog6ToothIcon, action: '/settings', category: 'action' },
]

const categoryLabels = {
  navigation: 'Navigation',
  action: 'Actions',
  recent: 'Recent',
}

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  // Listen for keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setIsOpen(true)
      }
      if (e.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [])

  const filteredCommands = query === ''
    ? commands
    : commands.filter((cmd) =>
        cmd.name.toLowerCase().includes(query.toLowerCase()) ||
        cmd.description?.toLowerCase().includes(query.toLowerCase())
      )

  const groupedCommands = filteredCommands.reduce((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = []
    acc[cmd.category].push(cmd)
    return acc
  }, {} as Record<string, CommandItem[]>)

  const handleSelect = useCallback((command: CommandItem) => {
    setIsOpen(false)
    setQuery('')
    if (typeof command.action === 'string') {
      navigate(command.action)
    } else {
      command.action()
    }
  }, [navigate])

  return (
    <Transition.Root show={isOpen} as={Fragment} afterLeave={() => setQuery('')}>
      <Dialog onClose={setIsOpen} className="relative z-50">
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-200"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-150"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto p-4 sm:p-6 md:p-20">
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-200"
            enterFrom="opacity-0 scale-95"
            enterTo="opacity-100 scale-100"
            leave="ease-in duration-150"
            leaveFrom="opacity-100 scale-100"
            leaveTo="opacity-0 scale-95"
          >
            <Dialog.Panel className="mx-auto max-w-2xl transform overflow-hidden rounded-2xl bg-white shadow-2xl ring-1 ring-black/5 transition-all">
              <Combobox onChange={handleSelect}>
                <div className="relative">
                  <MagnifyingGlassIcon className="pointer-events-none absolute left-4 top-3.5 h-5 w-5 text-gray-400" />
                  <Combobox.Input
                    className="h-12 w-full border-0 bg-transparent pl-11 pr-4 text-gray-900 placeholder:text-gray-400 focus:ring-0 sm:text-sm"
                    placeholder="Search commands, pages, contracts..."
                    onChange={(e) => setQuery(e.target.value)}
                  />
                  <div className="absolute right-4 top-3 flex items-center gap-1">
                    <kbd className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500 font-medium">
                      esc
                    </kbd>
                  </div>
                </div>

                {filteredCommands.length > 0 && (
                  <Combobox.Options static className="max-h-80 scroll-py-2 overflow-y-auto border-t border-gray-100">
                    {Object.entries(groupedCommands).map(([category, items]) => (
                      <div key={category}>
                        <div className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50">
                          {categoryLabels[category as keyof typeof categoryLabels]}
                        </div>
                        {items.map((cmd) => (
                          <Combobox.Option
                            key={cmd.id}
                            value={cmd}
                            className={({ active }) =>
                              cn(
                                'flex cursor-pointer select-none items-center px-4 py-3',
                                active ? 'bg-primary-50 text-primary-900' : 'text-gray-700'
                              )
                            }
                          >
                            {({ active }) => (
                              <>
                                <cmd.icon className={cn(
                                  'h-5 w-5 flex-shrink-0',
                                  active ? 'text-primary-600' : 'text-gray-400'
                                )} />
                                <div className="ml-3 flex-auto">
                                  <p className={cn(
                                    'text-sm font-medium',
                                    active ? 'text-primary-900' : 'text-gray-900'
                                  )}>
                                    {cmd.name}
                                  </p>
                                  {cmd.description && (
                                    <p className={cn(
                                      'text-xs',
                                      active ? 'text-primary-700' : 'text-gray-500'
                                    )}>
                                      {cmd.description}
                                    </p>
                                  )}
                                </div>
                                {cmd.shortcut && (
                                  <kbd className="ml-3 flex-shrink-0 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 font-mono">
                                    {cmd.shortcut}
                                  </kbd>
                                )}
                              </>
                            )}
                          </Combobox.Option>
                        ))}
                      </div>
                    ))}
                  </Combobox.Options>
                )}

                {query !== '' && filteredCommands.length === 0 && (
                  <div className="px-6 py-14 text-center sm:px-14">
                    <FolderIcon className="mx-auto h-6 w-6 text-gray-400" />
                    <p className="mt-4 text-sm text-gray-900">
                      No results found for "<span className="font-semibold">{query}</span>"
                    </p>
                    <p className="mt-2 text-xs text-gray-500">
                      Try searching for pages, actions, or contracts
                    </p>
                  </div>
                )}

                <div className="flex items-center justify-between border-t border-gray-100 px-4 py-2.5 text-xs text-gray-500">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1">
                      <kbd className="rounded bg-gray-100 px-1.5 py-0.5 font-medium">↑↓</kbd>
                      Navigate
                    </span>
                    <span className="flex items-center gap-1">
                      <kbd className="rounded bg-gray-100 px-1.5 py-0.5 font-medium">↵</kbd>
                      Select
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <CommandLineIcon className="h-3.5 w-3.5" />
                    <span>Command Palette</span>
                  </div>
                </div>
              </Combobox>
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition.Root>
  )
}
