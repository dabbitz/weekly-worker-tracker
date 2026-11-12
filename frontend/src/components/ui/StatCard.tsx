import type { LucideIcon } from 'lucide-react'

import { cn } from '../../lib/utils'

interface StatCardProps {
  label: string
  value: number
  hint?: string
  icon: LucideIcon
  tone?: 'blue' | 'green' | 'amber' | 'navy'
  isLoading?: boolean
}

const toneClasses = {
  blue: 'bg-blue-50 text-worktrack-blue',
  green: 'bg-emerald-50 text-emerald-600',
  amber: 'bg-amber-50 text-amber-600',
  navy: 'bg-worktrack-navy/10 text-worktrack-navy',
}

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'blue',
  isLoading = false,
}: StatCardProps) {
  return (
    <div className="card flex items-start justify-between gap-4 p-5">
      <div className="min-w-0">
        <p className="text-sm font-medium text-slate-500">{label}</p>
        {isLoading ? (
          <div className="mt-2 h-8 w-14 animate-pulse rounded bg-slate-200" />
        ) : (
          <p className="mt-1 text-3xl font-semibold tracking-tight text-worktrack-ink">
            {value.toLocaleString('tr-TR')}
          </p>
        )}
        {hint ? (
          <p className="mt-1 text-xs text-slate-500">{hint}</p>
        ) : null}
      </div>
      <div
        className={cn(
          'flex h-11 w-11 shrink-0 items-center justify-center rounded-lg',
          toneClasses[tone],
        )}
      >
        <Icon className="h-5 w-5" aria-hidden="true" />
      </div>
    </div>
  )
}
