import { Link2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { cn } from '../../lib/utils'
import type { NarrativeSegment } from '../../types'

interface NarrativeTextProps {
  segments: NarrativeSegment[]
  className?: string
}

function segmentLabel(segment: NarrativeSegment): string {
  return segment.label ?? segment.token ?? ''
}

/**
 * Renders backend-resolved narrative segments.
 *
 * The frontend never guesses a token: the backend decides whether a token is
 * a real reference (and supplies its label and href) or plain text.
 */
export function NarrativeText({
  segments,
  className,
}: NarrativeTextProps) {
  return (
    <span className={className}>
      {segments.map((segment, index) => {
        if (segment.type === 'reference' && segment.href) {
          return (
            <Link
              key={`${segment.token ?? 'ref'}-${index}`}
              to={segment.href}
              className="rounded bg-worktrack-blue/10 px-1 py-0.5 font-medium text-worktrack-blue-dark underline-offset-2 transition hover:bg-worktrack-blue/20 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worktrack-blue"
            >
              {segmentLabel(segment)}
            </Link>
          )
        }

        return (
          <span key={`text-${index}`}>
            {segment.type === 'text' ? segment.text : segmentLabel(segment)}
          </span>
        )
      })}
    </span>
  )
}

interface SourceChipsProps {
  sources: NarrativeSegment[]
  className?: string
  label?: string
}

export function SourceChips({
  sources,
  className,
  label = 'Kaynaklar',
}: SourceChipsProps) {
  if (sources.length === 0) {
    return null
  }

  return (
    <div
      className={cn('flex flex-wrap items-center gap-1.5', className)}
    >
      <span className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">
        {label}
      </span>
      {sources.map((source, index) => {
        const content = (
          <>
            <Link2 className="h-3 w-3" aria-hidden="true" />
            {segmentLabel(source)}
          </>
        )

        if (source.href) {
          return (
            <Link
              key={`${source.token ?? 'source'}-${index}`}
              to={source.href}
              className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200 ring-inset transition hover:bg-slate-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worktrack-blue"
            >
              {content}
            </Link>
          )
        }

        return (
          <span
            key={`${source.token ?? 'source'}-${index}`}
            className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600 ring-1 ring-slate-200 ring-inset"
          >
            {content}
          </span>
        )
      })}
    </div>
  )
}
