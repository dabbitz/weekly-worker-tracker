import { ApiError } from '../api/client'
import type { ReportReviewStatus, WorkStatus } from '../types'

export function cn(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(' ')
}

const dateFormatter = new Intl.DateTimeFormat('tr-TR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

const longDateFormatter = new Intl.DateTimeFormat('tr-TR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

const dateTimeFormatter = new Intl.DateTimeFormat('tr-TR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function toDate(value: string): Date | null {
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value)
    ? new Date(`${value}T00:00:00`)
    : new Date(value)

  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDate(
  value: string | null | undefined,
  fallback = '—',
): string {
  if (!value) {
    return fallback
  }
  const date = toDate(value)
  return date ? dateFormatter.format(date) : fallback
}

export function formatLongDate(
  value: string | null | undefined,
  fallback = '—',
): string {
  if (!value) {
    return fallback
  }
  const date = toDate(value)
  return date ? longDateFormatter.format(date) : fallback
}

export function formatDateTime(
  value: string | null | undefined,
  fallback = '—',
): string {
  if (!value) {
    return fallback
  }
  const date = toDate(value)
  return date ? dateTimeFormatter.format(date) : fallback
}

export function formatWeekRange(
  start: string,
  end: string,
): string {
  return `${formatDate(start)} – ${formatDate(end)}`
}

export function getInitials(fullName: string): string {
  const parts = fullName
    .trim()
    .split(/\s+/)
    .filter(Boolean)

  if (parts.length === 0) {
    return '?'
  }

  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? parts[parts.length - 1]?.[0] ?? '' : ''

  return `${first}${last}`.toLocaleUpperCase('tr-TR')
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Beklenmeyen bir hata oluştu.'
}

export function todayIso(): string {
  const today = new Date()
  const offset = today.getTimezoneOffset() * 60_000
  return new Date(today.getTime() - offset).toISOString().slice(0, 10)
}

export function addDaysIso(isoDate: string, days: number): string {
  const date = new Date(`${isoDate}T00:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export const weeklyPlanStatusMeta = {
  draft: {
    label: 'Taslak',
    tone: 'warning' as const,
  },
  approved: {
    label: 'Onaylandı',
    tone: 'success' as const,
  },
  rejected: {
    label: 'Reddedildi',
    tone: 'danger' as const,
  },
  superseded: {
    label: 'Eski Plan',
    tone: 'neutral' as const,
  },
}

export const weeklyPlanSourceMeta = {
  ai: {
    label: 'AI',
    tone: 'info' as const,
  },
  manual: {
    label: 'Manuel',
    tone: 'neutral' as const,
  },
}

export const registrationStatusMeta = {
  pending: {
    label: 'Bekliyor',
    tone: 'warning' as const,
  },
  approved: {
    label: 'Onaylandı',
    tone: 'success' as const,
  },
  rejected: {
    label: 'Reddedildi',
    tone: 'danger' as const,
  },
}

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

export const workStatusMeta: Record<
  WorkStatus,
  { label: string; tone: BadgeTone }
> = {
  completed: {
    label: 'Tamamlandı',
    tone: 'success',
  },
  in_progress: {
    label: 'Devam ediyor',
    tone: 'info',
  },
  blocked: {
    label: 'Engellendi',
    tone: 'danger',
  },
  not_started: {
    label: 'Başlanmadı',
    tone: 'warning',
  },
  unknown: {
    label: 'Belirsiz',
    tone: 'neutral',
  },
}

export const reportReviewStatusMeta: Record<
  ReportReviewStatus,
  { label: string; tone: BadgeTone }
> = {
  pending: {
    label: 'Çalışan onayı bekliyor',
    tone: 'warning',
  },
  approved: {
    label: 'Çalışan onayladı',
    tone: 'success',
  },
  rejected: {
    label: 'Çalışan reddetti',
    tone: 'danger',
  },
}

export function pluralize(
  count: number,
  singular: string,
  plural: string,
): string {
  return `${count} ${count === 1 ? singular : plural}`
}
