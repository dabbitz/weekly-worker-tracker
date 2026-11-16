import type {
  NarrativeSegment,
  WeeklyInterventionCandidate,
  WeeklyReportDetail,
} from '../../types'
import { formatDateTime, formatWeekRange } from '../../lib/utils'
import {
  buildReferenceRegistry,
  codesForSegments,
  codesForTokens,
  comparePriority,
  ruleActionSuggestions,
  segmentsToPlainText,
  shorten,
  sortTasksByRisk,
  taskRisk,
  type ReferenceRegistry,
} from './reportHelpers'

const PRINT_TASK_LIMIT = 6
const PRINT_RISK_LIMIT = 5

const priorityLabels = {
  high: 'Yüksek',
  medium: 'Orta',
  low: 'Düşük',
} as const

function sourceCodesForSegments(
  segments: NarrativeSegment[],
  registry: ReferenceRegistry,
): string[] {
  return codesForSegments(registry, segments)
}

interface PrintRisk {
  key: string
  priority: WeeklyInterventionCandidate['priority']
  source: 'Kural' | 'AI'
  title: string
  detail: string | null
  action: string | null
  codes: string[]
}

function buildPrintRisks(
  report: WeeklyReportDetail,
  registry: ReferenceRegistry,
): PrintRisk[] {
  const narrative = report.narrative_view

  const ruleRisks: PrintRisk[] = report.intervention_candidates.map(
    (candidate, index) => ({
      key: `rule-${candidate.code}-${index}`,
      priority: candidate.priority,
      source: 'Kural',
      title: candidate.title,
      detail: candidate.description,
      action: ruleActionSuggestions[candidate.code] ?? null,
      codes: [
        ...codesForTokens(
          registry,
          'projects',
          candidate.project_tokens,
        ),
        ...codesForTokens(registry, 'tasks', candidate.task_tokens),
        ...codesForTokens(registry, 'plans', candidate.plan_tokens),
        ...codesForTokens(registry, 'reports', candidate.report_tokens),
      ],
    }),
  )

  const aiRisks: PrintRisk[] = (
    narrative?.manager_interventions ?? []
  ).map((intervention, index) => ({
    key: `ai-${index}`,
    priority: intervention.priority,
    source: 'AI',
    title: segmentsToPlainText(intervention.title),
    detail: segmentsToPlainText(intervention.problem),
    action: segmentsToPlainText(intervention.recommended_action),
    codes: [
      ...sourceCodesForSegments(
        intervention.affected_projects,
        registry,
      ),
      ...sourceCodesForSegments(intervention.affected_tasks, registry),
      ...sourceCodesForSegments(intervention.sources, registry),
    ],
  }))

  return [...ruleRisks, ...aiRisks].sort(
    (a, b) =>
      comparePriority(a.priority, b.priority) ||
      (a.source === b.source ? 0 : a.source === 'Kural' ? -1 : 1),
  )
}

function PrintKpi({
  label,
  value,
  hint,
}: {
  label: string
  value: number
  hint?: string
}) {
  return (
    <div className="rounded-md border border-slate-300 px-2.5 py-1.5">
      <p className="text-[9px] font-semibold tracking-wide text-slate-500 uppercase">
        {label}
      </p>
      <p className="mt-0.5 text-lg leading-none font-bold text-worktrack-ink tabular-nums">
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 text-[9px] text-slate-500">{hint}</p>
      ) : null}
    </div>
  )
}

/**
 * Print-only one-page executive summary.
 *
 * It deliberately shows less than the screen report: headline KPIs, the
 * most important tasks, risks/actions and short source references. The
 * full detail stays available in the on-screen disclosures.
 */
export function WeeklyReportPrintSummary({
  report,
}: {
  report: WeeklyReportDetail
}) {
  const summary = report.metrics_snapshot.summary
  const narrative = report.narrative_view
  const registry = buildReferenceRegistry(report)

  const tasks = sortTasksByRisk(report.metrics_snapshot.tasks)
  const shownTasks = tasks.slice(0, PRINT_TASK_LIMIT)
  const hiddenTaskCount = tasks.length - shownTasks.length

  const risks = buildPrintRisks(report, registry)
  const shownRisks = risks.slice(0, PRINT_RISK_LIMIT)
  const hiddenRiskCount = risks.length - shownRisks.length

  const highlights = (narrative?.general_highlights ?? []).slice(0, 2)
  const issues = (narrative?.general_issues ?? []).slice(0, 2)

  const references = Array.from(registry.values()).slice(0, 16)

  return (
    <div className="print-report hidden text-slate-800 print:block">
      <header className="flex items-start justify-between gap-4 border-b border-slate-300 pb-2">
        <div>
          <p className="text-[9px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
            WorkTrack · Yönetim Paneli
          </p>
          <h1 className="mt-0.5 text-[17px] leading-tight font-bold text-worktrack-ink">
            Haftalık Yönetici Raporu
          </h1>
          <p className="mt-0.5 text-[10px] text-slate-600">
            {formatWeekRange(report.week_start_date, report.week_end_date)}
            {report.is_partial_week ? ' · Kısmi hafta' : ''}
          </p>
        </div>
        <div className="text-right text-[9px] text-slate-500">
          <p>v{report.version}</p>
          <p>Oluşturulma: {formatDateTime(report.created_at)}</p>
          {report.model ? <p>Model: {report.model}</p> : null}
        </div>
      </header>

      <section className="mt-2.5 grid grid-cols-5 gap-2">
        <PrintKpi label="Proje" value={summary.project_count} />
        <PrintKpi label="Görev" value={summary.task_count} />
        <PrintKpi
          label="İş raporu"
          value={summary.report_count}
          hint={
            summary.pending_review_report_count > 0
              ? `${summary.pending_review_report_count} onay bekliyor`
              : undefined
          }
        />
        <PrintKpi
          label="Engelli görev"
          value={summary.blocked_task_count}
        />
        <PrintKpi
          label="Geciken görev"
          value={summary.overdue_not_completed_count}
        />
      </section>

      {narrative ? (
        <section className="mt-2.5">
          <h2 className="border-b border-slate-200 pb-0.5 text-[10px] font-bold tracking-wide text-worktrack-ink uppercase">
            Genel durum
          </h2>
          <p className="mt-1 text-[10px] leading-4">
            {shorten(
              segmentsToPlainText(narrative.general_summary),
              520,
            )}
          </p>
          {highlights.length > 0 || issues.length > 0 ? (
            <div className="mt-1 grid grid-cols-2 gap-3">
              {highlights.length > 0 ? (
                <div>
                  <p className="text-[9px] font-semibold text-emerald-700 uppercase">
                    Öne çıkanlar
                  </p>
                  <ul className="mt-0.5 list-disc space-y-0.5 pl-3">
                    {highlights.map((block, index) => (
                      <li key={index} className="text-[9.5px] leading-4">
                        {shorten(
                          segmentsToPlainText(block.segments),
                          170,
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {issues.length > 0 ? (
                <div>
                  <p className="text-[9px] font-semibold text-red-700 uppercase">
                    Dikkat edilmesi gerekenler
                  </p>
                  <ul className="mt-0.5 list-disc space-y-0.5 pl-3">
                    {issues.map((block, index) => (
                      <li key={index} className="text-[9.5px] leading-4">
                        {shorten(
                          segmentsToPlainText(block.segments),
                          170,
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="mt-2.5">
        <h2 className="border-b border-slate-200 pb-0.5 text-[10px] font-bold tracking-wide text-worktrack-ink uppercase">
          Önemli görevler
        </h2>
        {shownTasks.length === 0 ? (
          <p className="mt-1 text-[9.5px] text-slate-500">
            Bu hafta için değerlendirilecek görev bulunmuyor.
          </p>
        ) : (
          <table className="mt-1 w-full table-fixed border-collapse">
            <thead>
              <tr className="text-left text-[8.5px] tracking-wide text-slate-500 uppercase">
                <th className="w-[20%] py-0.5 pr-2 font-semibold">
                  Proje
                </th>
                <th className="w-[28%] py-0.5 pr-2 font-semibold">
                  Görev
                </th>
                <th className="w-[14%] py-0.5 pr-2 font-semibold">
                  Durum
                </th>
                <th className="w-[10%] py-0.5 pr-2 text-right font-semibold">
                  Hedef
                </th>
                <th className="w-[10%] py-0.5 pr-2 text-right font-semibold">
                  İlerleme
                </th>
                <th className="w-[18%] py-0.5 font-semibold">Risk</th>
              </tr>
            </thead>
            <tbody>
              {shownTasks.map((task) => {
                const risk = taskRisk(task)
                const project =
                  report.references.projects[task.project_token]?.label
                const taskCode = registry.get(
                  `tasks:${task.task_token}`,
                )?.code

                return (
                  <tr
                    key={task.task_token}
                    className="border-t border-slate-200 align-top"
                  >
                    <td className="py-0.5 pr-2 text-[9px]">
                      {shorten(project ?? '—', 34)}
                    </td>
                    <td className="py-0.5 pr-2 text-[9px] font-medium text-worktrack-ink">
                      {shorten(task.title, 48)}
                      {taskCode ? (
                        <span className="ml-1 font-normal text-slate-400">
                          ({taskCode})
                        </span>
                      ) : null}
                    </td>
                    <td className="py-0.5 pr-2 text-[9px]">
                      {task.reported_status ??
                        task.classification_label}
                    </td>
                    <td className="py-0.5 pr-2 text-right text-[9px] tabular-nums">
                      {task.target_completion_percentage === null
                        ? '—'
                        : `%${task.target_completion_percentage}`}
                    </td>
                    <td className="py-0.5 pr-2 text-right text-[9px] tabular-nums">
                      {task.reported_completion_percentage === null
                        ? '—'
                        : `%${task.reported_completion_percentage}`}
                    </td>
                    <td
                      className={
                        risk?.tone === 'danger'
                          ? 'py-0.5 text-[9px] text-red-700'
                          : risk?.tone === 'warning'
                            ? 'py-0.5 text-[9px] text-amber-700'
                            : 'py-0.5 text-[9px] text-slate-500'
                      }
                    >
                      {risk?.label ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
        {hiddenTaskCount > 0 ? (
          <p className="mt-1 text-[9px] text-slate-500">
            {hiddenTaskCount} görev daha raporda gizlendi; tamamı
            ekrandaki raporda görüntülenebilir.
          </p>
        ) : null}
      </section>

      <section className="mt-2.5">
        <h2 className="border-b border-slate-200 pb-0.5 text-[10px] font-bold tracking-wide text-worktrack-ink uppercase">
          Riskler ve yönetici aksiyonları
        </h2>
        {shownRisks.length === 0 ? (
          <p className="mt-1 text-[9.5px] text-emerald-700">
            Bu hafta için müdahale gerektiren bir konu tespit
            edilmedi.
          </p>
        ) : (
          <ul className="mt-1 space-y-1">
            {shownRisks.map((risk) => (
              <li
                key={risk.key}
                className="border-l-2 border-slate-300 pl-2"
              >
                <p className="text-[9.5px] font-semibold text-worktrack-ink">
                  <span className="mr-1 font-bold text-slate-500">
                    [{priorityLabels[risk.priority]} · {risk.source}]
                  </span>
                  {shorten(risk.title, 110)}
                  {risk.codes.length > 0 ? (
                    <span className="ml-1 font-normal text-slate-400">
                      ({risk.codes.join(', ')})
                    </span>
                  ) : null}
                </p>
                {risk.detail ? (
                  <p className="text-[9px] leading-4 text-slate-600">
                    {shorten(risk.detail, 180)}
                  </p>
                ) : null}
                {risk.action ? (
                  <p className="text-[9px] leading-4 text-slate-700">
                    <span className="font-semibold">Aksiyon: </span>
                    {shorten(risk.action, 150)}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {hiddenRiskCount > 0 ? (
          <p className="mt-1 text-[9px] text-slate-500">
            {hiddenRiskCount} risk daha raporda gizlendi.
          </p>
        ) : null}
      </section>

      {references.length > 0 ? (
        <footer className="mt-2 border-t border-slate-200 pt-1.5">
          <p className="text-[8.5px] leading-3.5 text-slate-500">
            <span className="font-semibold tracking-wide text-slate-600 uppercase">
              Kaynaklar:{' '}
            </span>
            {references
              .map(
                (reference) =>
                  `${reference.code} ${shorten(reference.label, 28)}`,
              )
              .join(' · ')}
          </p>
          <p className="mt-0.5 text-[8.5px] text-slate-400">
            Tek sayfa yönetici özeti. Teknik hesaplamalar ve tam veri
            dökümü ekrandaki raporda yer alır.
          </p>
        </footer>
      ) : null}
    </div>
  )
}
