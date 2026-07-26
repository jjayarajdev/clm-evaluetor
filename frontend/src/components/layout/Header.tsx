import { Menu, Transition } from '@headlessui/react'
import { Fragment } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bars3Icon,
  BellIcon,
  ChevronDownIcon,
  ArrowRightOnRectangleIcon,
  LanguageIcon,
  UserCircleIcon,
} from '@heroicons/react/24/outline'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { setAppLanguage, type AppLanguage } from '@/i18n'
import api from '@/lib/api'
import { cn, userDisplayName, userInitials, formatDate } from '@/lib/utils'

interface HeaderProps {
  onMenuClick: () => void
}

const LANGUAGES: { code: AppLanguage; labelKey: string }[] = [
  { code: 'en', labelKey: 'common.english' },
  { code: 'fr', labelKey: 'common.french' },
]

const SEVERITY_DOT: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-gray-300',
}
const SEVERITY_BADGE: Record<string, string> = {
  high: 'bg-red-50 text-red-700',
  medium: 'bg-amber-50 text-amber-700',
  low: 'bg-gray-100 text-gray-600',
}

export default function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuth()
  const { t, i18n } = useTranslation()

  const { data: notif } = useQuery({
    queryKey: ['notifications-feed'],
    queryFn: () => api.getNotificationFeed(),
    enabled: !!user,
    refetchInterval: 60000,
    staleTime: 30000,
  })
  const notifCount = notif?.count ?? 0

  const changeLanguage = async (code: AppLanguage) => {
    setAppLanguage(code)
    if (user) {
      try {
        await api.updateMyPreferences(code)
      } catch {
        // Preference persists locally even if the API call fails
      }
    }
  }

  return (
    <header className="sticky top-0 z-30 bg-white border-b border-gray-200">
      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Mobile menu button */}
        <button
          type="button"
          className="lg:hidden -m-2.5 p-2.5 text-gray-700"
          onClick={onMenuClick}
        >
          <span className="sr-only">{t('nav.openSidebar')}</span>
          <Bars3Icon className="h-6 w-6" />
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Right section */}
        <div className="flex items-center gap-4">
          {/* Notifications */}
          <Menu as="div" className="relative">
            <Menu.Button className="p-2 text-gray-500 hover:text-gray-700 relative rounded-lg hover:bg-gray-50">
              <span className="sr-only">{t('nav.viewNotifications')}</span>
              <BellIcon className="h-6 w-6" />
              {notifCount > 0 && (
                <span className="absolute top-0.5 right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-semibold flex items-center justify-center">
                  {notifCount > 9 ? '9+' : notifCount}
                </span>
              )}
            </Menu.Button>
            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-10 mt-2 w-96 max-w-[calc(100vw-2rem)] origin-top-right rounded-lg bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none flex flex-col max-h-[70vh]">
                <div className="px-4 py-2.5 border-b border-gray-100 flex items-center justify-between flex-shrink-0">
                  <p className="text-sm font-semibold text-gray-900">
                    {t('notifFeed.title', { defaultValue: 'Notifications' })}
                  </p>
                  {notifCount > 0 && (
                    <span className="text-xs text-gray-400">
                      {t('notifFeed.count', { defaultValue: '{{count}} needing attention', count: notifCount })}
                    </span>
                  )}
                </div>
                <div className="overflow-y-auto flex-1 py-1">
                  {!notif || notif.items.length === 0 ? (
                    <div className="px-4 py-10 text-center">
                      <BellIcon className="h-8 w-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm text-gray-400">
                        {t('notifFeed.empty', { defaultValue: "You're all caught up" })}
                      </p>
                    </div>
                  ) : (
                    notif.items.map((item) => (
                      <Menu.Item key={item.id}>
                        {({ active }) => (
                          <Link
                            to={item.link}
                            className={cn('flex gap-3 px-4 py-2.5', active && 'bg-gray-50')}
                          >
                            <span className={cn('mt-1.5 h-2 w-2 rounded-full flex-shrink-0', SEVERITY_DOT[item.severity] || 'bg-gray-300')} />
                            <span className="flex-1 min-w-0">
                              <span className="flex items-center gap-2">
                                <span className={cn('text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded', SEVERITY_BADGE[item.severity] || 'bg-gray-100 text-gray-600')}>
                                  {item.label}
                                </span>
                                <span className="text-[11px] text-gray-400">{formatDate(item.date)}</span>
                              </span>
                              <span className="block text-sm text-gray-800 truncate mt-0.5">{item.title}</span>
                              {item.subtitle && (
                                <span className="block text-xs text-gray-400 truncate">{item.subtitle}</span>
                              )}
                            </span>
                          </Link>
                        )}
                      </Menu.Item>
                    ))
                  )}
                </div>
              </Menu.Items>
            </Transition>
          </Menu>

          {/* Language switcher */}
          <Menu as="div" className="relative">
            <Menu.Button className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-50">
              <span className="sr-only">{t('common.language')}</span>
              <LanguageIcon className="h-5 w-5" />
              <span className="text-xs font-semibold uppercase">{i18n.language}</span>
              <ChevronDownIcon className="h-3 w-3 text-gray-400" />
            </Menu.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-10 mt-2 w-36 origin-top-right rounded-lg bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                {LANGUAGES.map(({ code, labelKey }) => (
                  <Menu.Item key={code}>
                    {({ active }) => (
                      <button
                        onClick={() => changeLanguage(code)}
                        className={cn(
                          'flex w-full items-center justify-between px-4 py-2 text-sm',
                          active ? 'bg-gray-50 text-gray-900' : 'text-gray-700',
                          i18n.language === code && 'font-semibold text-primary-700'
                        )}
                      >
                        {t(labelKey)}
                        {i18n.language === code && <span aria-hidden>✓</span>}
                      </button>
                    )}
                  </Menu.Item>
                ))}
              </Menu.Items>
            </Transition>
          </Menu>

          {/* User menu */}
          <Menu as="div" className="relative">
            <Menu.Button className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-gray-50">
              <div className="hidden sm:block text-right">
                <span className="block text-sm font-semibold text-gray-900">
                  {userDisplayName(user)}
                </span>
                <span className="flex items-center justify-end gap-1.5 text-xs text-gray-500">
                  <span className={cn(
                    'inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide',
                    user?.role === 'super_admin' ? 'bg-pink-100 text-pink-700' :
                    user?.role === 'legal' ? 'bg-blue-100 text-blue-700' :
                    user?.role === 'admin' ? 'bg-primary-100 text-primary-700' :
                    'bg-gray-100 text-gray-600'
                  )}>
                    {user?.role ? t(`roles.${user.role}`) : ''}
                  </span>
                  <span className="truncate">{user?.tenant_name || t('nav.system')}</span>
                </span>
              </div>
              <div className="h-9 w-9 rounded-full bg-primary-100 flex items-center justify-center">
                <span className="text-sm font-semibold text-primary-700">
                  {userInitials(user)}
                </span>
              </div>
              <ChevronDownIcon className="h-4 w-4 text-gray-400" />
            </Menu.Button>

            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-10 mt-2 w-48 origin-top-right rounded-lg bg-white py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                <div className="px-4 py-2 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">
                    {userDisplayName(user)}
                  </p>
                  <p className="text-xs text-gray-500">@{user?.username}</p>
                  <p className="text-xs text-gray-500">{user?.email}</p>
                  <p className="text-xs font-medium text-primary-600 capitalize mt-0.5">
                    {user?.role ? t(`roles.${user.role}`) : ''} &middot; {user?.tenant_name || t('nav.system')}
                  </p>
                </div>

                <Menu.Item>
                  {({ active }) => (
                    <a
                      href="/settings"
                      className={cn(
                        'flex items-center gap-2 px-4 py-2 text-sm',
                        active ? 'bg-gray-50 text-gray-900' : 'text-gray-700'
                      )}
                    >
                      <UserCircleIcon className="h-4 w-4" />
                      {t('nav.profile')}
                    </a>
                  )}
                </Menu.Item>

                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={logout}
                      className={cn(
                        'flex w-full items-center gap-2 px-4 py-2 text-sm',
                        active ? 'bg-gray-50 text-gray-900' : 'text-gray-700'
                      )}
                    >
                      <ArrowRightOnRectangleIcon className="h-4 w-4" />
                      {t('nav.signOut')}
                    </button>
                  )}
                </Menu.Item>
              </Menu.Items>
            </Transition>
          </Menu>
        </div>
      </div>
    </header>
  )
}
