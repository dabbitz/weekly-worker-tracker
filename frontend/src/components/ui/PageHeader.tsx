import type { ReactNode } from 'react'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
  eyebrow?: string
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: PageHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 text-xs font-semibold tracking-wider text-worktrack-blue uppercase">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-2xl font-semibold tracking-tight text-worktrack-ink">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  )
}
