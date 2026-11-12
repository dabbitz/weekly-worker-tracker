import type { ReactNode } from 'react'

import { cn } from '../../lib/utils'

interface BadgeProps {
  tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'
  children: ReactNode
  className?: string
}

const toneClasses = {
  neutral: 'bg-slate-100 text-slate-600 ring-slate-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-amber-50 text-amber-700 ring-amber-200',
  danger: 'bg-red-50 text-red-700 ring-red-200',
  info: 'bg-blue-50 text-blue-700 ring-blue-200',
}

export function Badge({
  tone = 'neutral',
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset',
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
