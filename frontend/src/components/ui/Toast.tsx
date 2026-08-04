import { ReactNode, createContext, useCallback, useContext, useEffect, useState } from 'react'
import { CheckCircleIcon, ExclamationCircleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { Button, IconButton } from './Button'

export interface ToastData {
  text: string
  error?: boolean
  action?: { label: string; run: () => void }
}

interface ToastContextValue {
  toast: (t: ToastData) => void
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<ToastData | null>(null)
  const toast = useCallback((t: ToastData) => setCurrent(t), [])
  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <ToastView toast={current} onClose={() => setCurrent(null)} />
    </ToastContext.Provider>
  )
}

export function ToastView({ toast, onClose }: { toast: ToastData | null; onClose: () => void }) {
  useEffect(() => {
    if (toast) {
      const t = setTimeout(onClose, 4200)
      return () => clearTimeout(t)
    }
  }, [toast, onClose])
  if (!toast) return null
  const Icon = toast.error ? ExclamationCircleIcon : CheckCircleIcon
  return (
    <div
      style={{
        position: 'fixed', left: '50%', bottom: 24, transform: 'translateX(-50%)',
        zIndex: 120, animation: 'pop .2s var(--ease-out)',
      }}
    >
      <div className="row card" style={{ gap: 10, padding: '10px 10px 10px 14px', boxShadow: 'var(--sh-lg)', minWidth: 320 }} role="status">
        <Icon style={{ width: 17, height: 17, flexShrink: 0, color: toast.error ? 'var(--da)' : 'var(--ok)' }} aria-hidden />
        <span className="grow" style={{ fontSize: 'var(--fs-md)' }}>{toast.text}</span>
        {toast.action && (
          <Button variant="ghost" size="sm" onClick={toast.action.run}>
            {toast.action.label}
          </Button>
        )}
        <IconButton icon={XMarkIcon} label="Dismiss" size="sm" onClick={onClose} />
      </div>
    </div>
  )
}
