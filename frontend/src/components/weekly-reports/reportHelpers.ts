import type {
  InterventionPriority,
  NarrativeSegment,
  WeeklyReportDetail,
  WeeklyTaskSnapshot,
} from '../../types'

export type ReferenceKind =
  | 'projects'
  | 'tasks'
  | 'reports'
  | 'plans'
  | 'employees'
  | 'weeks'

export interface ReferenceEntry {
  code: string
  label: string
  href: string | null
}

export type ReferenceRegistry = Map<string, ReferenceEntry>

const refKinds: ReferenceKind[] = [
  'projects',
  'tasks',
  'reports',
  'plans',
  'employees',
  'weeks',
]

const refPrefix: Record<ReferenceKind, string> = {
  projects: 'P',
  tasks: 'G',
  reports: 'R',
  plans: 'H',
  employees: 'Ç',
  weeks: 'W',
}

const refKindBySegmentKind: Record<string, ReferenceKind> = {
  project: 'projects',
  task: 'tasks',
  report: 'reports',
  plan: 'plans',
  employee: 'employees',
  week: 'weeks',
}

export function buildReferenceRegistry(
  report: WeeklyReportDetail,
): ReferenceRegistry {
  const registry: ReferenceRegistry = new Map()

  for (const kind of refKinds) {
    const entries = report.references[kind] ?? {}

    Object.entries(entries).forEach(([token, entry], index) => {
      registry.set(`${kind}:${token}`, {
        code: `${refPrefix[kind]}${index + 1}`,
        label: entry?.label ?? token,
        href: entry?.href ?? null,
      })
    })
  }

  return registry
}

export function resolveReference(
  segment: NarrativeSegment,
  registry: ReferenceRegistry,
): ReferenceEntry | null {
  if (!segment.kind || !segment.token) {
    return null
  }

  const kind = refKindBySegmentKind[segment.kind]

  if (!kind) {
    return null
  }

  return registry.get(`${kind}:${segment.token}`) ?? null
}

export function segmentsToPlainText(
  segments: NarrativeSegment[],
): string {
  return segments
    .map((segment) =>
      segment.type === 'text'
        ? (segment.text ?? '')
        : (segment.label ?? segment.token ?? ''),
    )
    .join('')
}

export function codesForTokens(
  registry: ReferenceRegistry,
  kind: ReferenceKind,
  tokens: string[],
): string[] {
  return Array.from(
    new Set(
      tokens
        .map((token) => registry.get(`${kind}:${token}`)?.code)
        .filter((code): code is string => Boolean(code)),
    ),
  )
}

export function codesForSegments(
  registry: ReferenceRegistry,
  segments: NarrativeSegment[],
): string[] {
  return Array.from(
    new Set(
      segments
        .map(
          (segment) =>
            resolveReference(segment, registry)?.code ?? null,
        )
        .filter((code): code is string => Boolean(code)),
    ),
  )
}

export function shorten(value: string, limit: number): string {
  const cleaned = value.trim()

  if (cleaned.length <= limit) {
    return cleaned
  }

  return `${cleaned.slice(0, Math.max(limit - 1, 0)).trimEnd()}…`
}

export interface TaskRisk {
  label: string
  tone: 'danger' | 'warning' | 'neutral'
}

export function taskRisk(task: WeeklyTaskSnapshot): TaskRisk | null {
  if (task.latest_report?.blocker) {
    return {
      label: shorten(task.latest_report.blocker, 64),
      tone: 'danger',
    }
  }

  if (task.reported_status === 'blocked') {
    return { label: 'Engelli bildirildi', tone: 'danger' }
  }

  if (task.overdue && !task.completed_reported) {
    return {
      label: 'Süresi geçti, tamamlandı bildirilmedi',
      tone: 'danger',
    }
  }

  if (task.plan_conflict) {
    return { label: 'Haftalık plan çakışması', tone: 'warning' }
  }

  if (task.eta_slipped) {
    return { label: 'Tahmini bitiş ötelenmiş', tone: 'warning' }
  }

  if (task.repeated_blocker) {
    return { label: 'Tekrarlayan engel', tone: 'warning' }
  }

  if (task.pending_review_report_count > 0) {
    return {
      label: `${task.pending_review_report_count} rapor onay bekliyor`,
      tone: 'warning',
    }
  }

  if (!task.latest_report) {
    return { label: 'Rapor gönderilmedi', tone: 'neutral' }
  }

  return null
}

const riskWeight = (task: WeeklyTaskSnapshot): number => {
  if (task.latest_report?.blocker || task.reported_status === 'blocked') {
    return 0
  }

  if (task.overdue && !task.completed_reported) {
    return 1
  }

  if (task.plan_conflict) {
    return 2
  }

  if (task.eta_slipped || task.repeated_blocker) {
    return 3
  }

  if (task.pending_review_report_count > 0) {
    return 4
  }

  if (!task.latest_report) {
    return 5
  }

  return 6
}

export function sortTasksByRisk(
  tasks: WeeklyTaskSnapshot[],
): WeeklyTaskSnapshot[] {
  return [...tasks].sort((a, b) => riskWeight(a) - riskWeight(b))
}

const priorityRank: Record<InterventionPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
}

export function comparePriority(
  a: InterventionPriority,
  b: InterventionPriority,
): number {
  return priorityRank[a] - priorityRank[b]
}

/**
 * Short, neutral next steps for deterministic findings. They are
 * presentation hints, not new business decisions; the administrator
 * still decides the action.
 */
export const ruleActionSuggestions: Record<string, string> = {
  BLOCKED_TASK:
    'Engelin kaldırılması için bağımlılığı ve sorumluyu netleştirin.',
  OVERDUE_NOT_REPORTED_COMPLETE:
    'Görevin güncel durumunu teyit edin ve teslim tarihini yeniden planlayın.',
  NO_REPORT_ON_PLANNED_TASK:
    'Çalışandan haftalık rapor isteyin; rapor yokluğunu tamamlanmadı saymayın.',
  REPEATED_BLOCKER:
    'Tekrarlayan engelin kök nedenini ele alın ve sorumlu atayın.',
  ETA_SLIPPED:
    'Tahmini bitiş değişiminin nedenini ve yeni planı onaylayın.',
  PLAN_CONFLICT:
    'Çakışan haftalık planlardan geçerli hedefi netleştirin.',
  PLAN_APPROVED_AFTER_WEEK:
    'Hafta sonrası onaylanan planın kapsamını kontrol edin.',
  MISSING_TARGET_PERCENTAGE:
    'Görev için hedef tamamlanma yüzdesini tamamlayın.',
  UNASSIGNED_ACTIVE_TASK:
    'Aktif göreve uygun çalışan atamasını yapın.',
  CONFLICTING_REPORTS:
    'Çelişkili raporları çalışanla birlikte netleştirin.',
  PENDING_REVIEW_REPORTS:
    'Onay bekleyen iş raporlarını değerlendirin.',
}
