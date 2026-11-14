import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Database,
  FolderKanban,
  History,
  Lightbulb,
  ListChecks,
  Printer,
  RotateCcw,
  ShieldCheck,
  Siren,
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
  WeeklyInterventionCandidate,
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
import {
  NarrativeText,
  SourceChips,
} from '../components/weekly-reports/NarrativeText'

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
  INSUFFICIENT_HISTORY:
    'Karşılaştırma için yeterli geçmiş yok',
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

const classificationTones: Record<
  string,
  'success' | 'warning' | 'danger' | 'neutral' | 'info'
> = {
  reported_completed: 'success',
  met: 'success',
  below_target: 'warning',
  partial: 'warning',
  no_report: 'neutral',
  no_target: 'neutral',
  target_missing: 'info',
  plan_conflict: 'danger',
  plan_approved_after_week: 'danger',
  no_percentage: 'info',
}

function AiLabel() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-[11px] font-semibold text-violet-700 ring-1 ring-violet-200 ring-inset">
      <Sparkles className="h-3 w-3" aria-hidden="true" />
      AI yorumu
    </span>
  )
}

function DeterministicLabel() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600 ring-1 ring-slate-200 ring-inset">
      <Database className="h-3 w-3" aria-hidden="true" />
      Deterministik veri
    </span>
  )
}

interface ReportSectionProps {
  letter: string
  title: string
  description?: string
  badge?: ReactNode
  children: ReactNode
  tone?: 'default' | 'danger'
}

function ReportSection({
  letter,
  title,
  description,
  badge,
  children,
  tone = 'default',
}: ReportSectionProps) {
  return (
    <Card
      className={cn(
        tone === 'danger' &&
          'border-red-200 shadow-[0_0_0_1px_rgba(239,68,68,0.08)]',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-worktrack-line px-5 py-4">
        <div className="flex min-w-0 items-start gap-3">
          <span
            className={cn(
              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold',
              tone === 'danger'
                ? 'bg-red-100 text-red-700'
                : 'bg-worktrack-blue/10 text-worktrack-blue-dark',
            )}
            aria-hidden="true"
          >
            {letter}
          </span>
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-worktrack-ink">
              {title}
            </h2>
            {description ? (
              <p className="mt-0.5 text-sm text-slate-500">
                {description}
              </p>
            ) : null}
          </div>
        </div>
        {badge}
      </div>
      <div className="space-y-4 px-5 py-4">{children}</div>
    </Card>
  )
}

function BlockList({
  blocks,
  emptyText,
}: {
  blocks: NarrativeBlock[]
  emptyText: string
}) {
  if (blocks.length === 0) {
    return <p className="text-sm text-slate-500">{emptyText}</p>
  }

  return (
    <ul className="space-y-2.5">
      {blocks.map((block, index) => (
        <li
          key={index}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2.5"
        >
          <p className="text-sm leading-6 text-slate-700">
            <NarrativeText segments={block.segments} />
          </p>
          <SourceChips sources={block.sources} className="mt-2" />
        </li>
      ))}
    </ul>
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
  const tasks = report.metrics_snapshot.tasks

  if (tasks.length === 0) {
    return (
      <EmptyState
        compact
        icon={ListChecks}
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
            <th scope="col">Görev</th>
            <th scope="col">Proje</th>
            <th scope="col">Plan hedefi</th>
            <th scope="col">Son bildirilen</th>
            <th scope="col">Son rapor</th>
            <th scope="col">Değerlendirme</th>
          </tr>
        </thead>
        <tbody>
          {tasks.map((task: WeeklyTaskSnapshot) => {
            const taskRef = report.references.tasks[task.task_token]
            const projectRef =
              report.references.projects[task.project_token]

            return (
              <tr key={task.task_token}>
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
                <td className="whitespace-nowrap text-slate-600">
                  {formatPercent(task.target_completion_percentage)}
                  {task.plan_conflict ? (
                    <Badge tone="danger" className="ml-2">
                      Çakışma
                    </Badge>
                  ) : null}
                </td>
                <td className="whitespace-nowrap text-slate-600">
                  {formatPercent(
                    task.reported_completion_percentage,
                  )}
                  {task.reported_status ? (
                    <span className="ml-1 text-xs text-slate-400">
                      ({task.reported_status})
                    </span>
                  ) : null}
                </td>
                <td className="text-slate-600">
                  {task.latest_report?.received_at
                    ? formatDateTime(
                        task.latest_report.received_at,
                      )
                    : 'Rapor gönderilmedi'}
                </td>
                <td>
                  <Badge
                    tone={
                      classificationTones[task.classification] ??
                      'neutral'
                    }
                  >
                    {task.classification_label}
                  </Badge>
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
}: {
  report: WeeklyReportDetail
}) {
  if (report.data_quality.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        Bu hafta için veri kalitesi uyarısı yok.
      </p>
    )
  }

  return (
    <ul className="space-y-2.5">
      {report.data_quality.map(
        (item: WeeklyDataQualityItem, index: number) => {
          const taskSources = referenceSegments(
            report,
            'tasks',
            item.task_tokens,
          )
          const projectSources = referenceSegments(
            report,
            'projects',
            item.project_tokens,
          )
          const planSources = referenceSegments(
            report,
            'plans',
            item.plan_tokens,
          )
          const reportSources = referenceSegments(
            report,
            'reports',
            item.report_tokens,
          )

          return (
            <li
              key={`${item.code}-${index}`}
              className="rounded-lg border border-amber-200 bg-amber-50/50 px-3 py-2.5"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="warning">
                  {dataQualityLabels[item.code] ?? item.code}
                </Badge>
                <span className="text-xs font-mono text-amber-800/70">
                  {item.code}
                </span>
                {item.count ? (
                  <span className="text-xs text-amber-800">
                    {item.count} kayıt
                  </span>
                ) : null}
              </div>
              <p className="mt-1.5 text-sm leading-6 text-amber-900">
                {item.message}
              </p>
              {item.task_labels && item.task_labels.length > 0 ? (
                <p className="mt-1.5 text-xs text-amber-900/80">
                  Görevler: {item.task_labels.join(', ')}
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2">
                <SourceChips
                  sources={projectSources}
                  label="Projeler"
                />
                <SourceChips sources={taskSources} label="Görevler" />
                <SourceChips sources={planSources} label="Planlar" />
                <SourceChips
                  sources={reportSources}
                  label="Raporlar"
                />
              </div>
            </li>
          )
        },
      )}
    </ul>
  )
}

function InterventionCandidateCard({
  report,
  candidate,
}: {
  report: WeeklyReportDetail
  candidate: WeeklyInterventionCandidate
}) {
  const meta = priorityMeta[candidate.priority]
  const projectSources = referenceSegments(
    report,
    'projects',
    candidate.project_tokens,
  )
  const taskSources = referenceSegments(
    report,
    'tasks',
    candidate.task_tokens,
  )
  const reportSources = referenceSegments(
    report,
    'reports',
    candidate.report_tokens,
  )
  const planSources = referenceSegments(
    report,
    'plans',
    candidate.plan_tokens,
  )

  return (
    <li className="rounded-lg border border-red-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={meta.tone}>{meta.label}</Badge>
        <Badge tone="neutral">
          {interventionLabels[candidate.code] ?? candidate.code}
        </Badge>
        <span className="text-[11px] font-medium text-slate-400">
          Kural: {candidate.code}
        </span>
      </div>
      <p className="mt-2 text-sm font-semibold text-worktrack-ink">
        {candidate.title}
      </p>
      <p className="mt-1 text-sm leading-6 text-slate-600">
        {candidate.description}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <SourceChips sources={projectSources} label="Projeler" />
        <SourceChips sources={taskSources} label="Görevler" />
        <SourceChips sources={planSources} label="Planlar" />
        <SourceChips sources={reportSources} label="Raporlar" />
      </div>
    </li>
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
  const interventions = report.intervention_candidates
  const aiInterventions = narrative?.manager_interventions ?? []

  return (
    <div className="space-y-5">
      <Link
        to="/raporlar?sekme=haftalik"
        className="print-hide inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-worktrack-ink"
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
          <div className="print-hide flex flex-wrap items-center gap-2">
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

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
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

        <dl className="mt-5 grid gap-4 border-t border-worktrack-line pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-500">Hafta</dt>
            <dd className="mt-0.5 text-sm font-semibold text-worktrack-ink">
              {formatWeekRange(
                report.week_start_date,
                report.week_end_date,
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Model</dt>
            <dd className="mt-0.5 truncate text-sm font-semibold text-worktrack-ink">
              {report.model ?? '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Kapsam</dt>
            <dd className="mt-0.5 text-sm font-semibold text-worktrack-ink">
              {summary.project_count} proje · {summary.task_count}{' '}
              görev
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">
              Onaylı iş raporu
            </dt>
            <dd className="mt-0.5 text-sm font-semibold text-worktrack-ink">
              {summary.report_count}
              {summary.pending_review_report_count > 0
                ? ` · ${summary.pending_review_report_count} onay bekliyor`
                : ''}
            </dd>
          </div>
        </dl>
      </Card>

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
            Bu rapor şu anda oluşturuluyor. Durum birkaç saniyede bir
            otomatik yenilenir.
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
          <ReportSection
            letter="A"
            title="Genel Özet"
            description="Haftanın yönetici düzeyinde özeti."
            badge={<AiLabel />}
          >
            <p className="text-sm leading-6 text-slate-700">
              <NarrativeText segments={narrative.general_summary} />
            </p>
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Öne çıkanlar
              </h3>
              <BlockList
                blocks={narrative.general_highlights}
                emptyText="Öne çıkan bir gelişme belirtilmedi."
              />
            </div>
            <div>
              <h3 className="mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Dikkat edilmesi gerekenler
              </h3>
              <BlockList
                blocks={narrative.general_issues}
                emptyText="Genel düzeyde dikkat çeken bir sorun belirtilmedi."
              />
            </div>
          </ReportSection>

          <ReportSection
            letter="B"
            title="Proje Bazında"
            description="Yalnızca görev atamaları üzerinden projeye bağlanan kayıtlar."
            badge={<AiLabel />}
          >
            {narrative.project_analyses.length === 0 ? (
              <p className="text-sm text-slate-500">
                Bu hafta için proje bazlı bir değerlendirme yok.
              </p>
            ) : (
              <div className="space-y-3">
                {narrative.project_analyses.map(
                  (project, index) => (
                    <div
                      key={index}
                      className="rounded-lg border border-slate-200 bg-slate-50/50 p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <FolderKanban
                          className="h-4 w-4 text-slate-400"
                          aria-hidden="true"
                        />
                        <span className="font-semibold text-worktrack-ink">
                          <NarrativeText
                            segments={[project.project]}
                          />
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">
                        <NarrativeText
                          segments={project.summary}
                        />
                      </p>
                      <div className="mt-3 grid gap-3 lg:grid-cols-2">
                        <div>
                          <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                            Öne çıkanlar
                          </h4>
                          <BlockList
                            blocks={project.highlights}
                            emptyText="Belirtilmedi."
                          />
                        </div>
                        <div>
                          <h4 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                            Riskler
                          </h4>
                          <BlockList
                            blocks={project.risks}
                            emptyText="Belirtilmedi."
                          />
                        </div>
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}
          </ReportSection>

          <ReportSection
            letter="C"
            title="Çalışan Bazında"
            description="Çalışanlar yalnızca kendi iş raporları ve görev atamaları üzerinden değerlendirilir."
            badge={<AiLabel />}
          >
            {narrative.employee_analyses.length === 0 ? (
              <p className="text-sm text-slate-500">
                Bu hafta için çalışan bazlı bir değerlendirme yok.
              </p>
            ) : (
              <div className="space-y-3">
                {narrative.employee_analyses.map(
                  (employee, index) => (
                    <div
                      key={index}
                      className="rounded-lg border border-slate-200 bg-white p-4"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <Users
                          className="h-4 w-4 text-slate-400"
                          aria-hidden="true"
                        />
                        <span className="font-semibold text-worktrack-ink">
                          <NarrativeText
                            segments={[employee.employee]}
                          />
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-slate-700">
                        <NarrativeText
                          segments={employee.summary}
                        />
                      </p>
                      <div className="mt-3">
                        <BlockList
                          blocks={employee.observations}
                          emptyText="Gözlem belirtilmedi."
                        />
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}
          </ReportSection>

          <ReportSection
            letter="D"
            title="Planlanan vs Gerçekleşen"
            description="Hedef yüzdesi ile bildirilen tamamlanma yüzdesi aynı şey değildir. Farklı çalışanların yüzdeleri ortalanmaz."
            badge={<AiLabel />}
          >
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <DeterministicLabel />
                <span className="text-xs text-slate-500">
                  Sayılar deterministik metriklerden gelir.
                </span>
              </div>
              <TaskTable report={report} />
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
                <ul className="space-y-2.5">
                  {narrative.task_assessments.map(
                    (task, index) => (
                      <li
                        key={index}
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2.5"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-worktrack-ink">
                            <NarrativeText segments={[task.task]} />
                          </span>
                          <Badge
                            tone={
                              classificationTones[
                                task.classification
                              ] ?? 'neutral'
                            }
                          >
                            {task.classification_label}
                          </Badge>
                        </div>
                        <p className="mt-1.5 text-sm leading-6 text-slate-700">
                          <NarrativeText
                            segments={task.assessment}
                          />
                        </p>
                        <SourceChips
                          sources={task.sources}
                          className="mt-2"
                        />
                      </li>
                    ),
                  )}
                </ul>
              )}
            </div>
          </ReportSection>

          <ReportSection
            letter="E"
            title="Gerçekleşmeyen İşler"
            description="Rapor gönderilmemesi, işin tamamlanmadığı anlamına gelmez; eksik rapor nötr değerlendirilir."
            badge={<AiLabel />}
          >
            <BlockList
              blocks={narrative.unmet_work_analysis}
              emptyText="Gerçekleşmeyen iş bildirimi yok."
            />
            {summary.no_report_task_count > 0 ? (
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                Deterministik kapsamda{' '}
                <span className="font-semibold text-worktrack-ink">
                  {summary.no_report_task_count}
                </span>{' '}
                görev için bu hafta onaylı rapor bulunmuyor. Bu
                görevler “Rapor gönderilmedi” olarak sınıflandırılır.
              </p>
            ) : null}
          </ReportSection>

          <ReportSection
            letter="F"
            title="Geçmiş Hafta Karşılaştırması"
            description="Yalnızca gerçek rapor kayıtları karşılaştırılır."
            badge={<AiLabel />}
          >
            <div className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <History
                  className="h-4 w-4 text-slate-400"
                  aria-hidden="true"
                />
                <DeterministicLabel />
              </div>
              {comparison.available ? (
                <dl className="grid gap-3 text-sm sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-slate-500">
                      Önceki hafta
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {formatWeekRange(
                        comparison.prior_week_start_date,
                        comparison.prior_week_end_date,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Onaylı rapor (bu hafta / önceki)
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {comparison.current_report_count} /{' '}
                      {comparison.prior_report_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Değişim
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {comparison.report_count_change > 0
                        ? `+${comparison.report_count_change}`
                        : comparison.report_count_change}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-slate-600">
                  Karşılaştırma için yeterli geçmiş veri yok. Bu hafta
                  tek başına değerlendirildi.
                </p>
              )}
            </div>
            <BlockList
              blocks={narrative.history_comparison}
              emptyText="Geçmiş karşılaştırma yorumu belirtilmedi."
            />
          </ReportSection>

          <ReportSection
            letter="G"
            title="Öneriler"
            description="Öneriler yönetici kararı değil, kaynaklara dayalı AI önerileridir."
            badge={<AiLabel />}
          >
            <div className="flex items-center gap-2">
              <Lightbulb
                className="h-4 w-4 text-amber-500"
                aria-hidden="true"
              />
              <span className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                Kaynaklara dayalı öneriler
              </span>
            </div>
            <BlockList
              blocks={narrative.recommendations}
              emptyText="Bu hafta için öneri belirtilmedi."
            />
          </ReportSection>

          <ReportSection
            letter="H"
            title="Veri Kalitesi"
            description="Eksik veya çelişkili veri, sayıların yorumunu etkileyebilir."
            badge={<DeterministicLabel />}
          >
            <DataQualityList report={report} />
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <AiLabel />
                <span className="text-xs text-slate-500">
                  AI veri kalitesi notları
                </span>
              </div>
              <BlockList
                blocks={narrative.data_quality_notes}
                emptyText="AI veri kalitesi notu belirtilmedi."
              />
            </div>
          </ReportSection>

          <ReportSection
            letter="I"
            title="Yönetici Müdahalesi Gerektiren Konular"
            description="Deterministik kurallar ve AI önerileri ayrı etiketlenmiştir. Öncelikler AI önerisidir; nihai karar yöneticinindir."
            badge={
              <div className="flex flex-wrap gap-1.5">
                <DeterministicLabel />
                <AiLabel />
              </div>
            }
            tone="danger"
          >
            <div>
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                <ShieldCheck
                  className="h-4 w-4 text-red-500"
                  aria-hidden="true"
                />
                Deterministik müdahale adayları
              </h3>
              {interventions.length === 0 ? (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                  Deterministik kurallara göre bu hafta müdahale
                  gerektiren bir konu tespit edilmedi.
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {interventions.map((candidate, index) => (
                    <InterventionCandidateCard
                      key={`${candidate.code}-${index}`}
                      report={report}
                      candidate={candidate}
                    />
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
                <Siren
                  className="h-4 w-4 text-violet-500"
                  aria-hidden="true"
                />
                AI müdahale önerileri
              </h3>
              {aiInterventions.length === 0 ? (
                <p className="text-sm text-slate-500">
                  AI bu hafta için ayrı bir müdahale önerisi
                  belirtmedi.
                </p>
              ) : (
                <ul className="space-y-2.5">
                  {aiInterventions.map(
                    (intervention, index) => {
                      const meta =
                        priorityMeta[intervention.priority]

                      return (
                        <li
                          key={index}
                          className="rounded-lg border border-violet-200 bg-violet-50/40 px-4 py-3"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge tone={meta.tone}>
                              {meta.label}
                            </Badge>
                            <span className="text-[11px] font-semibold text-violet-700">
                              AI önerisi
                            </span>
                          </div>
                          <p className="mt-2 text-sm font-semibold text-worktrack-ink">
                            <NarrativeText
                              segments={intervention.title}
                            />
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-700">
                            <NarrativeText
                              segments={intervention.problem}
                            />
                          </p>
                          <p className="mt-1 text-sm leading-6 text-slate-700">
                            <span className="font-semibold text-worktrack-ink">
                              Önerilen eylem:{' '}
                            </span>
                            <NarrativeText
                              segments={
                                intervention.recommended_action
                              }
                            />
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <SourceChips
                              sources={intervention.affected_projects}
                              label="Etkilenen projeler"
                            />
                            <SourceChips
                              sources={intervention.affected_tasks}
                              label="Etkilenen görevler"
                            />
                            <SourceChips
                              sources={intervention.sources}
                            />
                          </div>
                        </li>
                      )
                    },
                  )}
                </ul>
              )}
            </div>
          </ReportSection>

          <ReportSection
            letter="i"
            title="Hesaplama Açıklaması"
            description="Sayıların nasıl üretildiğini ve sınırlamaları açıklar."
            badge={<DeterministicLabel />}
          >
            <ul className="space-y-2 text-sm leading-6 text-slate-600">
              <li>
                Hafta sınırları Europe/Istanbul saat diliminde
                pazartesi–pazar olarak hesaplanır. Rapor kayıtları
                <span className="font-medium text-worktrack-ink">
                  {' '}
                  received_at
                </span>{' '}
                (veritabanına kayıt zamanı) üzerinden haftaya
                atanır. Telegram mesajının gönderilme zamanı bu
                raporda kullanılmaz; iki zaman farklı olabilir.
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
                ) ile çalışanın bildirdiği tamamlanma yüzdesi (
                <span className="font-mono text-xs">
                  completion_percentage
                </span>
                ) aynı kavram değildir.
              </li>
              <li>
                Farklı çalışanların tamamlanma yüzdeleri
                ortalanmaz. Proje düzeyinde ilerleme yüzdesi
                hesaplanmaz; proje çalışanları yalnızca görev
                atamaları üzerinden türetilir.
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
          </ReportSection>
        </>
      ) : report.status === 'completed' ? (
        <Alert tone="warning" title="Anlatı bulunamadı">
          Bu rapor tamamlandı olarak işaretlenmiş ancak kayıtlı bir
          anlatı bulunmuyor. Raporu yeniden oluşturmayı deneyin.
        </Alert>
      ) : null}

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
    </div>
  )
}
