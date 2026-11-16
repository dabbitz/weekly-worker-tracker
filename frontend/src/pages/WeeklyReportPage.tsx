import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ChevronDown,
  Database,
  FolderKanban,
  History,
  Printer,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Trash2,
  Users,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { weeklyReportsApi } from '../api/endpoints'
import {
  cn,
  formatDateTime,
  formatWeekRange,
  getErrorMessage,
} from '../lib/utils'
import type {
  InterventionPriority,
  NarrativeBlock,
  NarrativeSegment,
  WeeklyDataQualityItem,
  WeeklyReportDetail,
  WeeklyReportStatus,
  WeeklyTaskSnapshot,
} from '../types'
import { Alert } from '../components/ui/Alert'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { useToast } from '../components/ui/Toast'
import { NarrativeText } from '../components/weekly-reports/NarrativeText'
import { WeeklyReportPrintSummary } from '../components/weekly-reports/WeeklyReportPrintSummary'
import {
  buildReferenceRegistry,
  codesForTokens,
  comparePriority,
  resolveReference,
  ruleActionSuggestions,
  sortTasksByRisk,
  taskRisk,
  type ReferenceRegistry,
} from '../components/weekly-reports/reportHelpers'

const statusMeta: Record<
  WeeklyReportStatus,
  { label: string; tone: 'warning' | 'success' | 'danger' }
> = {
  pending: { label: 'Hazırlanıyor', tone: 'warning' },
  completed: { label: 'Tamamlandı', tone: 'success' },
  failed: { label: 'Oluşturulamadı', tone: 'danger' },
}

const priorityMeta: Record<
  InterventionPriority,
  { label: string; tone: 'danger' | 'warning' | 'neutral' }
> = {
  high: { label: 'Yüksek öncelik', tone: 'danger' },
  medium: { label: 'Orta öncelik', tone: 'warning' },
  low: { label: 'Düşük öncelik', tone: 'neutral' },
}

const riskBorder: Record<InterventionPriority, string> = {
  high: 'border-l-red-400',
  medium: 'border-l-amber-400',
  low: 'border-l-slate-300',
}

const dataQualityLabels: Record<string, string> = {
  TASK_WITHOUT_REPORT: 'Rapor gönderilmedi',
  PLAN_CONFLICT: 'Haftalık plan çakışması',
  MISSING_TARGET_PERCENTAGE: 'Hedef yüzdesi eksik',
  PENDING_REVIEW_REPORTS: 'Onay bekleyen raporlar',
  OVERDUE_NOT_REPORTED_COMPLETE:
    'Süresi geçmiş, tamamlandı bildirilmedi',
  UNASSIGNED_ACTIVE_TASK: 'Atanmamış aktif görev',
  CONFLICTING_REPORTS: 'Çelişkili raporlar',
  DELAY_REASON_MISSING: 'Gecikme nedeni eksik',
  TASK_WITHOUT_DATES: 'Tarihsiz görev',
  INSUFFICIENT_HISTORY: 'Karşılaştırma için yeterli geçmiş yok',
  UNLINKED_REPORT: 'Görevle ilişkilendirilmemiş rapor',
}

const interventionLabels: Record<string, string> = {
  BLOCKED_TASK: 'Engelli görev',
  OVERDUE_NOT_REPORTED_COMPLETE: 'Süresi geçmiş görev',
  NO_REPORT_ON_PLANNED_TASK: 'Planlı göreve rapor yok',
  REPEATED_BLOCKER: 'Tekrarlayan engel',
  ETA_SLIPPED: 'Tahmini bitiş ötelenmiş',
  PLAN_CONFLICT: 'Plan çakışması',
  PLAN_APPROVED_AFTER_WEEK: 'Hafta sonrası onaylanan plan',
  MISSING_TARGET_PERCENTAGE: 'Hedef yüzdesi eksik',
  UNASSIGNED_ACTIVE_TASK: 'Atanmamış görev',
  CONFLICTING_REPORTS: 'Çelişkili rapor',
  PENDING_REVIEW_REPORTS: 'Onay bekleyen rapor',
}

const workStatusLabels: Record<string, string> = {
  completed: 'Tamamlandı',
  in_progress: 'Devam ediyor',
  blocked: 'Engellendi',
  not_started: 'Henüz başlanmadı',
  unknown: 'Belirsiz',
}

const riskToneClass = {
  danger: 'text-red-700',
  warning: 'text-amber-700',
  neutral: 'text-slate-500',
}

function AiLabel() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-violet-200 ring-inset">
      <Sparkles className="h-3 w-3" aria-hidden="true" />
      AI yorumu
    </span>
  )
}

function RuleLabel() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200 ring-inset">
      <Database className="h-3 w-3" aria-hidden="true" />
      Deterministik veri
    </span>
  )
}

interface DisclosureProps {
  title: string
  description?: string
  children: ReactNode
  defaultOpen?: boolean
}

function Disclosure({
  title,
  description,
  children,
  defaultOpen = false,
}: DisclosureProps) {
  return (
    <details
      className="card group"
      open={defaultOpen ? true : undefined}
    >
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-3.5 transition hover:bg-slate-50/70 [&::-webkit-details-marker]:hidden">
        <div className="min-w-0">
          <span className="text-sm font-semibold text-worktrack-ink">
            {title}
          </span>
          {description ? (
            <span className="ml-2 text-xs text-slate-500">
              {description}
            </span>
          ) : null}
        </div>
        <ChevronDown
          className="h-4 w-4 shrink-0 text-slate-400 transition group-open:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="space-y-4 border-t border-worktrack-line px-5 py-4">
        {children}
      </div>
    </details>
  )
}

function Kpi({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string
  value: number
  hint?: string
  tone?: 'default' | 'danger' | 'warning'
}) {
  const valueTone =
    value > 0 && tone === 'danger'
      ? 'text-red-600'
      : value > 0 && tone === 'warning'
        ? 'text-amber-600'
        : 'text-worktrack-ink'

  return (
    <div className="rounded-xl border border-worktrack-line bg-white px-4 py-3 shadow-[0_1px_2px_rgba(15,35,60,0.04)]">
      <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">
        {label}
      </p>
      <p
        className={cn(
          'mt-1 text-2xl font-semibold tabular-nums',
          valueTone,
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 text-[11px] text-slate-400">{hint}</p>
      ) : null}
    </div>
  )
}

function CompactSources({
  sources,
  registry,
  className,
}: {
  sources: NarrativeSegment[]
  registry: ReferenceRegistry
  className?: string
}) {
  if (sources.length === 0) {
    return null
  }

  const items: Array<{
    key: string
    label: string
    code: string | null
    href: string | null
  }> = []
  const seen = new Set<string>()

  for (const segment of sources) {
    const reference = resolveReference(segment, registry)

    if (reference) {
      if (seen.has(reference.code)) {
        continue
      }
      seen.add(reference.code)
      items.push({
        key: reference.code,
        label: reference.label,
        code: reference.code,
        href: reference.href,
      })
      continue
    }

    const label = segment.label ?? segment.text

    if (!label || seen.has(`label:${label}`)) {
      continue
    }

    seen.add(`label:${label}`)
    items.push({
      key: `label:${label}`,
      label,
      code: null,
      href: null,
    })
  }

  if (items.length === 0) {
    return null
  }

  return (
    <div
      className={cn(
        'flex flex-wrap items-center gap-1 text-[11px]',
        className,
      )}
    >
      <span className="font-semibold tracking-wide text-slate-400 uppercase">
        Kaynak
      </span>
      {items.map((item) =>
        item.href ? (
          <Link
            key={item.key}
            to={item.href}
            title={item.label}
            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono font-semibold text-slate-600 ring-1 ring-slate-200 ring-inset transition hover:bg-slate-200"
          >
            {item.code ?? item.label}
          </Link>
        ) : (
          <span
            key={item.key}
            title={item.label}
            className="rounded bg-slate-100 px-1.5 py-0.5 font-mono font-semibold text-slate-500 ring-1 ring-slate-200 ring-inset"
          >
            {item.code ?? item.label}
          </span>
        ),
      )}
    </div>
  )
}

function BlockItems({
  blocks,
  registry,
}: {
  blocks: NarrativeBlock[]
  registry: ReferenceRegistry
}) {
  return (
    <ul className="space-y-1.5">
      {blocks.map((block, index) => (
        <li
          key={index}
          className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5"
        >
          <p className="text-sm leading-6 text-slate-700">
            <NarrativeText segments={block.segments} />
          </p>
          <CompactSources
            sources={block.sources}
            registry={registry}
            className="mt-1"
          />
        </li>
      ))}
    </ul>
  )
}

function NarrativeBlocks({
  blocks,
  registry,
  emptyText,
  max,
}: {
  blocks: NarrativeBlock[]
  registry: ReferenceRegistry
  emptyText: string
  max?: number
}) {
  if (blocks.length === 0) {
    return <p className="text-sm text-slate-500">{emptyText}</p>
  }

  if (!max || blocks.length <= max) {
    return <BlockItems blocks={blocks} registry={registry} />
  }

  return (
    <div className="space-y-2">
      <BlockItems blocks={blocks.slice(0, max)} registry={registry} />
      <details>
        <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-worktrack-ink">
          Tümünü göster ({blocks.length})
        </summary>
        <div className="mt-2">
          <BlockItems blocks={blocks.slice(max)} registry={registry} />
        </div>
      </details>
    </div>
  )
}

function referenceSegments(
  report: WeeklyReportDetail,
  kind: 'projects' | 'tasks' | 'reports' | 'plans',
  tokens: string[],
): NarrativeSegment[] {
  return tokens.map((token) => {
    const reference = report.references[kind]?.[token]

    return {
      type: 'reference',
      text: null,
      token,
      kind: kind.slice(0, -1),
      ref_id: reference?.id ?? null,
      label: reference?.label ?? token,
      href: reference?.href ?? null,
    }
  })
}

function formatPercent(value: number | null): string {
  return value === null ? '—' : `%${value}`
}

function TaskTable({ report }: { report: WeeklyReportDetail }) {
  const tasks = sortTasksByRisk(report.metrics_snapshot.tasks)

  if (tasks.length === 0) {
    return (
      <EmptyState
        compact
        icon={FolderKanban}
        title="Görev kapsamı boş"
        description="Bu hafta için değerlendirilecek görev bulunmuyor."
      />
    )
  }

  return (
    <div className="table-shell overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Proje</th>
            <th scope="col">Görev</th>
            <th scope="col">Son bildirilen durum</th>
            <th scope="col" className="text-right">
              Planlanan kümülatif hedef
            </th>
            <th scope="col" className="text-right">
              Son bildirilen toplam ilerleme
            </th>
            <th scope="col">Kısa risk</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task: WeeklyTaskSnapshot) => {
            const taskRef = report.references.tasks[task.task_token]
            const projectRef =
              report.references.projects[task.project_token]
            const risk = taskRisk(task)

            return (
              <tr key={task.task_token}>
                <td className="text-slate-600">
                  {projectRef?.href ? (
                    <Link
                      to={projectRef.href}
                      className="hover:text-worktrack-blue-dark hover:underline"
                    >
                      {projectRef.label ?? '—'}
                    </Link>
                  ) : (
                    (projectRef?.label ?? '—')
                  )}
                </td>
                <td>
                  {taskRef?.href ? (
                    <Link
                      to={taskRef.href}
                      className="font-medium text-worktrack-ink hover:text-worktrack-blue-dark hover:underline"
                    >
                      {task.title}
                    </Link>
                  ) : (
                    <span className="font-medium text-worktrack-ink">
                      {task.title}
                    </span>
                  )}
                </td>
                <td className="whitespace-nowrap text-slate-600">
                  {task.reported_status
                    ? (workStatusLabels[task.reported_status] ??
                      task.reported_status)
                    : 'Rapor yok'}
                </td>
                <td className="text-right whitespace-nowrap text-slate-600 tabular-nums">
                  {formatPercent(task.target_completion_percentage)}
                  {task.plan_conflict ? (
                    <Badge tone="danger" className="ml-2">
                      Çakışma
                    </Badge>
                  ) : null}
                </td>
                <td className="text-right whitespace-nowrap text-slate-600 tabular-nums">
                  {formatPercent(task.reported_completion_percentage)}
                </td>
                <td
                  className={cn(
                    'text-xs',
                    risk ? riskToneClass[risk.tone] : 'text-slate-400',
                  )}
                >
                  {risk?.label ?? '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DataQualityList({
  report,
  registry,
}: {
  report: WeeklyReportDetail
  registry: ReferenceRegistry
}) {
  if (report.data_quality.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Bu hafta için veri kalitesi uyarısı yok.
      </p>
    )
  }

  return (
    <ul className="space-y-2">
      {report.data_quality.map(
        (item: WeeklyDataQualityItem, index: number) => {
          const codes = [
            ...codesForTokens(
              registry,
              'projects',
              item.project_tokens,
            ),
            ...codesForTokens(registry, 'tasks', item.task_tokens),
            ...codesForTokens(registry, 'plans', item.plan_tokens),
            ...codesForTokens(registry, 'reports', item.report_tokens),
          ]

          return (
            <li
              key={`${item.code}-${index}`}
              className="rounded-lg border border-amber-200 bg-amber-50/50 px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="warning">
                  {dataQualityLabels[item.code] ?? item.code}
                </Badge>
                {item.count ? (
                  <span className="text-xs text-amber-800">
                    {item.count} kayıt
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-sm leading-6 text-amber-900">
                {item.message}
              </p>
              {item.task_labels && item.task_labels.length > 0 ? (
                <p className="mt-1 text-xs text-amber-900/80">
                  Görevler: {item.task_labels.join(', ')}
                </p>
              ) : null}
              {codes.length > 0 ? (
                <p className="mt-1 font-mono text-[11px] text-amber-800/70">
                  Kaynak: {codes.join(', ')}
                </p>
              ) : null}
            </li>
          )
        },
      )}
    </ul>
  )
}

interface UnifiedRisk {
  key: string
  priority: InterventionPriority
  source: 'rule' | 'ai'
  code: string | null
  title: ReactNode
  problem: ReactNode
  action: ReactNode | null
  sources: NarrativeSegment[]
}

function buildUnifiedRisks(
  report: WeeklyReportDetail,
): UnifiedRisk[] {
  const rules: UnifiedRisk[] = report.intervention_candidates.map(
    (candidate, index) => ({
      key: `rule-${candidate.code}-${index}`,
      priority: candidate.priority,
      source: 'rule',
      code: candidate.code,
      title: candidate.title,
      problem: candidate.description,
      action: ruleActionSuggestions[candidate.code] ?? null,
      sources: [
        ...referenceSegments(
          report,
          'projects',
          candidate.project_tokens,
        ),
        ...referenceSegments(report, 'tasks', candidate.task_tokens),
        ...referenceSegments(report, 'plans', candidate.plan_tokens),
        ...referenceSegments(report, 'reports', candidate.report_tokens),
      ],
    }),
  )

  const ai: UnifiedRisk[] = (
    report.narrative_view?.manager_interventions ?? []
  ).map((intervention, index) => ({
    key: `ai-${index}`,
    priority: intervention.priority,
    source: 'ai',
    code: null,
    title: <NarrativeText segments={intervention.title} />,
    problem: <NarrativeText segments={intervention.problem} />,
    action: (
      <NarrativeText segments={intervention.recommended_action} />
    ),
    sources: [
      ...intervention.affected_projects,
      ...intervention.affected_tasks,
      ...intervention.sources,
    ],
  }))

  return [...rules, ...ai].sort(
    (a, b) =>
      comparePriority(a.priority, b.priority) ||
      (a.source === b.source ? 0 : a.source === 'rule' ? -1 : 1),
  )
}

function RiskList({
  risks,
  registry,
}: {
  risks: UnifiedRisk[]
  registry: ReferenceRegistry
}) {
  if (risks.length === 0) {
    return (
      <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
        Deterministik kurallara ve AI değerlendirmesine göre bu hafta
        müdahale gerektiren bir konu tespit edilmedi.
      </p>
    )
  }

  return (
    <ul className="space-y-2">
      {risks.map((risk) => {
        const meta = priorityMeta[risk.priority]

        return (
          <li
            key={risk.key}
            className={cn(
              'rounded-lg border border-slate-200 border-l-4 bg-white px-3.5 py-2.5',
              riskBorder[risk.priority],
            )}
          >
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge tone={meta.tone}>{meta.label}</Badge>
              {risk.source === 'rule' ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200 ring-inset">
                  <Database className="h-3 w-3" aria-hidden="true" />
                  Kural
                  {risk.code
                    ? ` · ${interventionLabels[risk.code] ?? risk.code}`
                    : ''}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-violet-200 ring-inset">
                  <Sparkles className="h-3 w-3" aria-hidden="true" />
                  AI önerisi
                </span>
              )}
            </div>
            <p className="mt-1.5 text-sm font-semibold text-worktrack-ink">
              {risk.title}
            </p>
            <p className="mt-0.5 text-sm leading-6 text-slate-600">
              {risk.problem}
            </p>
            {risk.action ? (
              <p className="mt-0.5 text-sm leading-6 text-slate-700">
                <span className="font-semibold text-worktrack-ink">
                  Önerilen aksiyon:{' '}
                </span>
                {risk.action}
              </p>
            ) : null}
            <CompactSources
              sources={risk.sources}
              registry={registry}
              className="mt-1.5"
            />
          </li>
        )
      })}
    </ul>
  )
}

function ReferenceList({
  registry,
}: {
  registry: ReferenceRegistry
}) {
  const entries = Array.from(registry.entries())

  if (entries.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Bu rapor için kaynak referansı bulunmuyor.
      </p>
    )
  }

  return (
    <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2 xl:grid-cols-3">
      {entries.map(([key, reference]) => (
        <div key={key} className="flex items-start gap-2 text-xs">
          <dt className="font-mono font-semibold text-slate-500">
            {reference.code}
          </dt>
          <dd className="min-w-0 text-slate-600">
            {reference.href ? (
              <Link
                to={reference.href}
                className="break-words hover:text-worktrack-blue-dark hover:underline"
              >
                {reference.label}
              </Link>
            ) : (
              <span className="break-words">{reference.label}</span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function EmployeeActivity({
  report,
}: {
  report: WeeklyReportDetail
}) {
  const employees = report.metrics_snapshot.employees

  if (employees.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Bu hafta için çalışan faaliyeti bulunmuyor.
      </p>
    )
  }

  const renderEmployee = (
    employee: (typeof employees)[number],
  ) => (
    <li
      key={employee.employee_token}
      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-worktrack-ink">
          {employee.full_name}
        </p>
        <p className="text-[11px] text-slate-500">
          {employee.role ?? 'Pozisyon belirtilmedi'}
          {employee.is_active ? '' : ' · Pasif'}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge
          tone={employee.report_count > 0 ? 'info' : 'neutral'}
        >
          {employee.report_count > 0
            ? `${employee.report_count} rapor`
            : 'Rapor gönderilmedi'}
        </Badge>
        <Badge tone="neutral">
          {employee.assigned_task_tokens.length} görev
        </Badge>
        {employee.blocker_count > 0 ? (
          <Badge tone="danger">
            {employee.blocker_count} engel
          </Badge>
        ) : null}
        {employee.pending_report_count > 0 ? (
          <Badge tone="warning">
            {employee.pending_report_count} onay bekliyor
          </Badge>
        ) : null}
      </div>
    </li>
  )

  const shown = employees.slice(0, 6)
  const rest = employees.slice(6)

  return (
    <div className="space-y-2">
      <ul className="space-y-1.5">
        {shown.map((employee) => renderEmployee(employee))}
      </ul>
      {rest.length > 0 ? (
        <details>
          <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-worktrack-ink">
            Tüm çalışanları göster ({employees.length})
          </summary>
          <ul className="mt-2 space-y-1.5">
            {rest.map((employee) => renderEmployee(employee))}
          </ul>
        </details>
      ) : null}
      <p className="text-xs text-slate-500">
        Eksik rapor, işin yapılmadığının kanıtı olarak
        değerlendirilmez. Kişisel verimlilik puanı veya sıralaması
        oluşturulmaz.
      </p>
    </div>
  )
}

export function WeeklyReportPage() {
  const { reportId } = useParams<{ reportId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const id = Number(reportId)
  const validId = Number.isFinite(id) && id > 0

  const reportQuery = useQuery({
    queryKey: ['weekly-report', id],
    queryFn: () => weeklyReportsApi.get(id),
    enabled: validId,
    refetchInterval: (query) =>
      query.state.data?.status === 'pending' ? 4000 : false,
  })

  const retryMutation = useMutation({
    mutationFn: () => weeklyReportsApi.retry(id),
    onSuccess: () => {
      showToast('Rapor yeniden oluşturuldu.', 'success')
      void queryClient.invalidateQueries({
        queryKey: ['weekly-report', id],
      })
      void queryClient.invalidateQueries({
        queryKey: ['weekly-reports'],
      })
    },
    onError: (error) => {
      showToast(getErrorMessage(error), 'error')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => weeklyReportsApi.remove(id),
    onSuccess: () => {
      showToast('Rapor belgesi silindi.', 'success')
      void queryClient.invalidateQueries({
        queryKey: ['weekly-reports'],
      })
      navigate('/raporlar?sekme=haftalik', { replace: true })
    },
    onError: (error) => {
      showToast(getErrorMessage(error), 'error')
    },
  })

  if (!validId) {
    return (
      <ErrorState
        title="Rapor bulunamadı"
        message="Geçersiz rapor kimliği."
      />
    )
  }

  if (reportQuery.isLoading) {
    return <LoadingState variant="detail" rows={8} />
  }

  if (reportQuery.isError) {
    return (
      <ErrorState
        title="Rapor yüklenemedi"
        message={getErrorMessage(reportQuery.error)}
        onRetry={() => void reportQuery.refetch()}
      />
    )
  }

  const report = reportQuery.data

  if (!report) {
    return (
      <ErrorState
        title="Rapor bulunamadı"
        message="Bu rapor bulunamadı veya erişim yetkiniz yok."
      />
    )
  }

  const meta = statusMeta[report.status]
  const narrative = report.narrative_view
  const summary = report.metrics_snapshot.summary
  const comparison = report.metrics_snapshot.comparison
  const registry = buildReferenceRegistry(report)
  const risks = buildUnifiedRisks(report)

  return (
    <>
      <div className="space-y-5 print:hidden">
        <Link
          to="/raporlar?sekme=haftalik"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-worktrack-ink"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Raporlara dön
        </Link>

        <PageHeader
          title="Haftalık Yönetici Raporu"
          description={`${formatWeekRange(
            report.week_start_date,
            report.week_end_date,
          )} · ${report.version}. sürüm`}
          actions={
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                onClick={() => window.print()}
                leftIcon={<Printer className="h-4 w-4" />}
              >
                Yazdır
              </Button>
              {report.status === 'failed' ? (
                <Button
                  variant="secondary"
                  onClick={() => retryMutation.mutate()}
                  isLoading={retryMutation.isPending}
                  leftIcon={<RotateCcw className="h-4 w-4" />}
                >
                  Yeniden dene
                </Button>
              ) : null}
              <Button
                variant="danger"
                onClick={() => setConfirmDelete(true)}
                disabled={report.status === 'pending'}
                leftIcon={<Trash2 className="h-4 w-4" />}
              >
                Sil
              </Button>
            </div>
          }
        />

        <Card className="px-5 py-3.5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={meta.tone}>{meta.label}</Badge>
              <Badge tone="info">v{report.version}</Badge>
              {report.is_partial_week ? (
                <Badge tone="warning">Kısmi hafta</Badge>
              ) : (
                <Badge tone="success">Tamamlanmış hafta</Badge>
              )}
              {narrative ? (
                narrative.source === 'deterministic_empty' ? (
                  <Badge tone="neutral">Yapay zekâ çağrılmadı</Badge>
                ) : (
                  <Badge tone="info">AI destekli yorum</Badge>
                )
              ) : null}
            </div>
            <p className="text-xs text-slate-500">
              Oluşturulma: {formatDateTime(report.created_at)}
              {report.completed_at
                ? ` · Tamamlanma: ${formatDateTime(
                    report.completed_at,
                  )}`
                : ''}
            </p>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
            <span>
              Dönem:{' '}
              <span className="font-medium text-worktrack-ink">
                {formatWeekRange(
                  report.week_start_date,
                  report.week_end_date,
                )}
              </span>
            </span>
            <span>
              Model:{' '}
              <span className="font-medium text-worktrack-ink">
                {report.model ?? '—'}
              </span>
            </span>
          </div>
        </Card>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          <Kpi label="Proje sayısı" value={summary.project_count} />
          <Kpi label="Görev sayısı" value={summary.task_count} />
          <Kpi
            label="İş raporu"
            value={summary.report_count}
            hint={
              summary.pending_review_report_count > 0
                ? `${summary.pending_review_report_count} onay bekliyor`
                : undefined
            }
          />
          <Kpi
            label="Engelli görev"
            value={summary.blocked_task_count}
            tone="danger"
          />
          <Kpi
            label="Geciken görev"
            value={summary.overdue_not_completed_count}
            tone="warning"
          />
        </div>

        {report.status === 'failed' ? (
          <Alert tone="error" title="Rapor oluşturulamadı">
            <p>
              {report.error_message ??
                'Rapor oluşturulurken bir hata oluştu. Lütfen yeniden deneyin.'}
            </p>
            <p className="mt-2 text-xs">
              Bu sürüm için anlatı kaydedilmedi. Yeniden deneme aynı
              sürümü kullanır; yeni bir sürüm oluşturmaz.
            </p>
          </Alert>
        ) : null}

        {report.status === 'pending' ? (
          <Alert tone="info" title="Rapor hazırlanıyor">
            <p>
              Bu rapor şu anda oluşturuluyor. Durum birkaç saniyede
              bir otomatik yenilenir.
            </p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={() => void reportQuery.refetch()}
              isLoading={reportQuery.isFetching}
            >
              Durumu yenile
            </Button>
          </Alert>
        ) : null}

        {narrative?.partial_week_note ? (
          <Alert tone="warning" title="Kısmi değerlendirme">
            <NarrativeText segments={narrative.partial_week_note} />
          </Alert>
        ) : null}

        {narrative?.source === 'deterministic_empty' ? (
          <Alert tone="info" title="Veri bulunmayan hafta">
            Bu hafta için değerlendirilecek görev, iş raporu veya
            haftalık plan bulunmadığından yapay zekâ çağrılmadı. Boş
            rapor deterministik olarak oluşturuldu.
          </Alert>
        ) : null}

        {narrative ? (
          <>
            <Card>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-worktrack-line px-5 py-3.5">
                <div>
                  <h2 className="text-sm font-semibold text-worktrack-ink">
                    Genel durum
                  </h2>
                  <p className="text-xs text-slate-500">
                    Haftanın kısa yönetici özeti.
                  </p>
                </div>
                <AiLabel />
              </div>
              <div className="space-y-3 px-5 py-4">
                <p className="text-sm leading-6 text-slate-700">
                  <NarrativeText segments={narrative.general_summary} />
                </p>
                <div className="grid gap-3 lg:grid-cols-2">
                  <div>
                    <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                      Öne çıkan gelişmeler
                    </h3>
                    <NarrativeBlocks
                      blocks={narrative.general_highlights}
                      registry={registry}
                      emptyText="Öne çıkan bir gelişme belirtilmedi."
                      max={3}
                    />
                  </div>
                  <div>
                    <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                      Önemli sorunlar
                    </h3>
                    <NarrativeBlocks
                      blocks={narrative.general_issues}
                      registry={registry}
                      emptyText="Genel düzeyde dikkat çeken bir sorun belirtilmedi."
                      max={3}
                    />
                  </div>
                </div>
              </div>
            </Card>

            <Card>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-worktrack-line px-5 py-3.5">
                <div>
                  <h2 className="text-sm font-semibold text-worktrack-ink">
                    Proje ve görev durumu
                  </h2>
                  <p className="text-xs text-slate-500">
                    Hedef ile son bildirilen toplam ilerleme ayrı
                    değerlerdir.
                  </p>
                </div>
                <RuleLabel />
              </div>
              <div className="px-5 py-4">
                <TaskTable report={report} />
              </div>
            </Card>

            <Card className="border-red-200">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-red-100 bg-red-50/40 px-5 py-3.5">
                <div>
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-worktrack-ink">
                    <ShieldCheck
                      className="h-4 w-4 text-red-500"
                      aria-hidden="true"
                    />
                    Riskler ve yönetici aksiyonları
                  </h2>
                  <p className="text-xs text-slate-500">
                    Kural tespitleri ile AI önerileri tek listede,
                    öncelik sırasına göre.
                  </p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  <RuleLabel />
                  <AiLabel />
                </div>
              </div>
              <div className="px-5 py-4">
                <RiskList risks={risks} registry={registry} />
              </div>
            </Card>

            <Card>
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-worktrack-line px-5 py-3.5">
                <div>
                  <h2 className="flex items-center gap-2 text-sm font-semibold text-worktrack-ink">
                    <Users
                      className="h-4 w-4 text-slate-400"
                      aria-hidden="true"
                    />
                    Çalışan faaliyetleri ve geçmiş
                  </h2>
                  <p className="text-xs text-slate-500">
                    Yalnızca bildirilen faaliyetler; kişisel sıralama
                    yok.
                  </p>
                </div>
              </div>
              <div className="space-y-4 px-5 py-4">
                <EmployeeActivity report={report} />

                <div className="rounded-lg border border-slate-200 bg-slate-50/60 px-3 py-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <History
                      className="h-4 w-4 text-slate-400"
                      aria-hidden="true"
                    />
                    <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                      Geçmiş hafta karşılaştırması
                    </span>
                  </div>
                  {comparison.available ? (
                    <p className="mt-1 text-sm text-slate-700">
                      {formatWeekRange(
                        comparison.prior_week_start_date,
                        comparison.prior_week_end_date,
                      )}{' '}
                      haftasında{' '}
                      <span className="font-semibold text-worktrack-ink">
                        {comparison.prior_report_count}
                      </span>{' '}
                      onaylı rapor vardı; bu hafta{' '}
                      <span className="font-semibold text-worktrack-ink">
                        {comparison.current_report_count}
                      </span>{' '}
                      rapor var (
                      {comparison.report_count_change > 0
                        ? `+${comparison.report_count_change}`
                        : comparison.report_count_change}
                      ).
                    </p>
                  ) : (
                    <p className="mt-1 text-sm text-slate-600">
                      Karşılaştırma için yeterli geçmiş veri yok. Bu
                      hafta tek başına değerlendirildi.
                    </p>
                  )}
                </div>
              </div>
            </Card>

            <Disclosure
              title="Hesaplama ve kaynak ayrıntıları"
              description="Teknik sınırlamalar, veri kalitesi ve kaynak referansları."
            >
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <RuleLabel />
                  <span className="text-xs text-slate-500">
                    Veri kalitesi uyarıları
                  </span>
                </div>
                <DataQualityList report={report} registry={registry} />
              </div>

              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <AiLabel />
                  <span className="text-xs text-slate-500">
                    AI veri kalitesi notları
                  </span>
                </div>
                <NarrativeBlocks
                  blocks={narrative.data_quality_notes}
                  registry={registry}
                  emptyText="AI veri kalitesi notu belirtilmedi."
                />
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Proje değerlendirmeleri
                </h3>
                {narrative.project_analyses.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    Bu hafta için proje bazlı bir değerlendirme yok.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {narrative.project_analyses.map(
                      (project, index) => (
                        <div
                          key={index}
                          className="rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2"
                        >
                          <p className="flex items-center gap-2 text-sm font-semibold text-worktrack-ink">
                            <FolderKanban
                              className="h-4 w-4 text-slate-400"
                              aria-hidden="true"
                            />
                            <NarrativeText
                              segments={[project.project]}
                            />
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-700">
                            <NarrativeText
                              segments={project.summary}
                            />
                          </p>
                          <div className="mt-2 grid gap-2 lg:grid-cols-2">
                            <div>
                              <p className="mb-1 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                                Öne çıkanlar
                              </p>
                              <NarrativeBlocks
                                blocks={project.highlights}
                                registry={registry}
                                emptyText="Belirtilmedi."
                                max={2}
                              />
                            </div>
                            <div>
                              <p className="mb-1 text-[11px] font-semibold tracking-wide text-slate-500 uppercase">
                                Riskler
                              </p>
                              <NarrativeBlocks
                                blocks={project.risks}
                                registry={registry}
                                emptyText="Belirtilmedi."
                                max={2}
                              />
                            </div>
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Çalışan değerlendirmeleri
                </h3>
                {narrative.employee_analyses.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    Bu hafta için çalışan bazlı bir değerlendirme yok.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {narrative.employee_analyses.map(
                      (employee, index) => (
                        <div
                          key={index}
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2"
                        >
                          <p className="text-sm font-semibold text-worktrack-ink">
                            <NarrativeText
                              segments={[employee.employee]}
                            />
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-700">
                            <NarrativeText
                              segments={employee.summary}
                            />
                          </p>
                          <div className="mt-2">
                            <NarrativeBlocks
                              blocks={employee.observations}
                              registry={registry}
                              emptyText="Gözlem belirtilmedi."
                              max={2}
                            />
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Görev değerlendirmeleri
                </h3>
                {narrative.task_assessments.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    Görev değerlendirmesi belirtilmedi.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {narrative.task_assessments.map(
                      (task, index) => (
                        <li
                          key={index}
                          className="rounded-lg border border-slate-200 bg-white px-3 py-2"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-worktrack-ink">
                              <NarrativeText segments={[task.task]} />
                            </span>
                            <Badge tone="neutral">
                              {task.classification_label}
                            </Badge>
                          </div>
                          <p className="mt-1 text-sm leading-6 text-slate-700">
                            <NarrativeText
                              segments={task.assessment}
                            />
                          </p>
                          <CompactSources
                            sources={task.sources}
                            registry={registry}
                            className="mt-1.5"
                          />
                        </li>
                      ),
                    )}
                  </ul>
                )}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Gerçekleşmeyen işler
                </h3>
                <NarrativeBlocks
                  blocks={narrative.unmet_work_analysis}
                  registry={registry}
                  emptyText="Gerçekleşmeyen iş bildirimi yok."
                  max={3}
                />
                {summary.no_report_task_count > 0 ? (
                  <p className="mt-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    Deterministik kapsamda{' '}
                    <span className="font-semibold text-worktrack-ink">
                      {summary.no_report_task_count}
                    </span>{' '}
                    görev için bu hafta onaylı rapor bulunmuyor. Bu
                    görevler “Rapor gönderilmedi” olarak sınıflandırılır
                    ve işin yapılmadığı anlamına gelmez.
                  </p>
                ) : null}
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Öneriler
                </h3>
                <NarrativeBlocks
                  blocks={narrative.recommendations}
                  registry={registry}
                  emptyText="Bu hafta için öneri belirtilmedi."
                  max={3}
                />
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Geçmiş karşılaştırma yorumu
                </h3>
                <NarrativeBlocks
                  blocks={narrative.history_comparison}
                  registry={registry}
                  emptyText="Geçmiş karşılaştırma yorumu belirtilmedi."
                  max={2}
                />
              </div>

              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <RuleLabel />
                  <span className="text-xs text-slate-500">
                    Hesaplama açıklaması ve sınırlamalar
                  </span>
                </div>
                <ul className="space-y-1.5 text-sm leading-6 text-slate-600">
                  <li>
                    Hafta sınırları Europe/Istanbul saat diliminde
                    pazartesi–pazar olarak hesaplanır. Rapor kayıtları{' '}
                    <span className="font-medium text-worktrack-ink">
                      received_at
                    </span>{' '}
                    (veritabanına kayıt zamanı) üzerinden haftaya atanır.
                    Telegram mesajının gönderilme zamanı bu raporda
                    kullanılmaz.
                  </li>
                  <li>
                    Faaliyet metriklerine yalnızca{' '}
                    <span className="font-medium text-worktrack-ink">
                      onaylanmış
                    </span>{' '}
                    iş raporları girer. Onay bekleyen raporlar ayrı
                    sayılır, reddedilen raporlar hariç tutulur.
                  </li>
                  <li>
                    Hedef tamamlanma yüzdesi (
                    <span className="font-mono text-xs">
                      target_completion_percentage
                    </span>
                    ) ile çalışanın bildirdiği toplam ilerleme (
                    <span className="font-mono text-xs">
                      completion_percentage
                    </span>
                    ) aynı kavram değildir. Farklı çalışanların
                    yüzdeleri ortalanmaz.
                  </li>
                  <li>
                    Kısmi hafta değerlendirmesi kesin bir performans
                    sonucu değildir; hafta tamamlanmadan verilen
                    rapordur.
                  </li>
                  <li>
                    Eksik rapor “Rapor gönderilmedi” olarak nötr
                    biçimde gösterilir; işin tamamlanmadığı anlamına
                    gelmez.
                  </li>
                  {Object.entries(
                    report.metrics_snapshot.methodology,
                  ).map(([key, value]) => (
                    <li key={key}>
                      <span className="font-mono text-xs text-slate-400">
                        {key}
                      </span>
                      : {value}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  Kaynaklar
                </h3>
                <ReferenceList registry={registry} />
              </div>
            </Disclosure>
          </>
        ) : report.status === 'completed' ? (
          <Alert tone="warning" title="Anlatı bulunamadı">
            Bu rapor tamamlandı olarak işaretlenmiş ancak kayıtlı bir
            anlatı bulunmuyor. Raporu yeniden oluşturmayı deneyin.
          </Alert>
        ) : null}
      </div>

      <WeeklyReportPrintSummary report={report} />

      <ConfirmDialog
        open={confirmDelete}
        title="Rapor belgesini sil"
        tone="danger"
        confirmLabel="Raporu sil"
        isLoading={deleteMutation.isPending}
        onClose={() => {
          if (!deleteMutation.isPending) {
            setConfirmDelete(false)
          }
        }}
        onConfirm={() => deleteMutation.mutate()}
        description={
          <>
            <p>
              <span className="font-semibold text-worktrack-ink">
                {formatWeekRange(
                  report.week_start_date,
                  report.week_end_date,
                )}{' '}
                · v{report.version}
              </span>{' '}
              raporu silinecek.
            </p>
            <p>
              Yalnızca bu rapor belgesi silinir. Görevler, çalışanlar,
              haftalık planlar ve çalışan iş raporları korunur. Bu
              işlem geri alınamaz.
            </p>
          </>
        }
      />
    </>
  )
}
