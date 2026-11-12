import {
  AlertCircle,
  CheckCircle2,
  Info,
  X,
} from 'lucide-react'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { cn } from '../../lib/utils'

type ToastTone = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  message: string
  tone: ToastTone
}

interface ToastContextValue {
  showToast: (message: string, tone?: ToastTone) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const toneClasses: Record<ToastTone, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  info: 'border-blue-200 bg-blue-50 text-blue-800',
}

const toneIcons: Record<ToastTone, typeof CheckCircle2> = {
  success: CheckCircle2,
  error: AlertCircle,
  info: Info,
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const counter = useRef(0)
  const timers = useRef<number[]>([])

  useEffect(() => {
    const activeTimers = timers.current
    return () => {
      activeTimers.forEach((timer) => window.clearTimeout(timer))
    }
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((current) =>
      current.filter((toast) => toast.id !== id),
    )
  }, [])

  const showToast = useCallback(
    (message: string, tone: ToastTone = 'success') => {
      counter.current += 1
      const id = counter.current

      setToasts((current) => [
        ...current.slice(-3),
        { id, message, tone },
      ])

      const timer = window.setTimeout(() => {
        dismiss(id)
      }, 5000)
      timers.current.push(timer)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-[100] flex flex-col items-end gap-2 sm:left-auto sm:w-96"
      >
        {toasts.map((toast) => {
          const Icon = toneIcons[toast.tone]
          return (
            <div
              key={toast.id}
              className={cn(
                'pointer-events-auto flex w-full items-start gap-3 rounded-lg border px-4 py-3 shadow-lg',
                toneClasses[toast.tone],
              )}
              role="status"
            >
              <Icon
                className="mt-0.5 h-4 w-4 shrink-0"
                aria-hidden="true"
              />
              <p className="min-w-0 flex-1 text-sm font-medium">
                {toast.message}
              </p>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                className="rounded p-0.5 opacity-70 transition hover:opacity-100"
                aria-label="Bildirimi kapat"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)

  if (context === null) {
    throw new Error('useToast, ToastProvider içinde kullanılmalıdır.')
  }

  return context
}
