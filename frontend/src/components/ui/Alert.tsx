import { AlertCircle, CheckCircle2, Info } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '../../lib/utils'

interface AlertProps {
  tone?: 'info' | 'warning' | 'error' | 'success'
  title?: string
  children: ReactNode
  className?: string
}

const toneClasses = {
  info: 'border-blue-200 bg-blue-50 text-blue-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
}

const toneIcons = {
  info: Info,
  warning: AlertCircle,
  error: AlertCircle,
  success: CheckCircle2,
}

export function Alert({
  tone = 'info',
  title,
  children,
  className,
}: AlertProps) {
  const Icon = toneIcons[tone]

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border px-4 py-3 text-sm',
        toneClasses[tone],
        className,
      )}
      role={tone === 'error' ? 'alert' : undefined}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        {title ? <p className="font-semibold">{title}</p> : null}
        <div className={title ? 'mt-0.5' : ''}>{children}</div>
      </div>
    </div>
  )
}
