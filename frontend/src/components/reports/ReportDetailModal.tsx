import { useQuery } from '@tanstack/react-query'
import {
  BadgeCheck,
  FileText,
  Info,
  Sparkles,
  Target,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { reportsApi } from '../../api/endpoints'
import {
  formatDate,
  formatDateTime,
  formatWeekRange,
  getErrorMessage,
  reportReviewStatusMeta,
  weeklyPlanStatusMeta,
  workStatusMeta,
} from '../../lib/utils'
import type { ReportDetail } from '../../types'
import { Alert } from '../ui/Alert'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { ErrorState } from '../ui/ErrorState'
import { LoadingState } from '../ui/LoadingState'
import { Modal } from '../ui/Modal'

interface ReportDetailModalProps {
  reportId: number | null
  onClose: () => void
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: LucideIcon
  children: ReactNode
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2 border-b border-worktrack-line pb-2">
        <Icon
          className="h-4 w-4 shrink-0 text-worktrack-blue"
          aria-hidden="true"
        />
        <h3 className="text-sm font-semibold text-worktrack-ink">
          {title}
        </h3>
      </div>
      {children}
    </section>
  )
}

function Value({
  label,
  children,
  preserveWhitespace = false,
}: {
  label: string
  children: ReactNode
  preserveWhitespace?: boolean
}) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-medium text-slate-500">{label}</dt>
      <dd
        className={
          preserveWhitespace
            ? 'mt-1 text-sm break-words whitespace-pre-line text-slate-700'
            : 'mt-1 text-sm break-words text-slate-700'
        }
      >
        {children}
      </dd>
    </div>
  )
}

function textOrPlaceholder(value: string | null): string {
  return value?.trim() ? value : 'Belirtilmedi'
}

function percentageOrPlaceholder(value: number | null): string {
  return value === null ? 'Belirtilmedi' : `%${value}`
}

function EtaValue({ report }: { report: ReportDetail }) {
  const parts = []

  if (report.reported_eta_text) {
    parts.push(report.reported_eta_text)
  }

  if (report.reported_eta_date) {
    const weekday = report.reported_eta_weekday
      ? ` (${report.reported_eta_weekday})`
      : ''
    parts.push(`${formatDate(report.reported_eta_date)}${weekday}`)
  }

  return <>{parts.length > 0 ? parts.join(' · ') : 'Belirtilmedi'}</>
}

function WeeklyPlanSection({ report }: { report: ReportDetail }) {
  const plan = report.weekly_plan

  if (!plan) {
    return (
      <Alert tone="info" title="Haftalık plan bulunmuyor">
        Bu rapor bir onaylı haftalık planla ilişkilendirilmemiş.
      </Alert>
    )
  }

  const planStatus = weeklyPlanStatusMeta[plan.status]

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={planStatus.tone}>{planStatus.label}</Badge>
        <span className="text-xs text-slate-500">
          Plan aralığı:{' '}
          {formatWeekRange(plan.week_start_date, plan.week_end_date)}
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-worktrack-line bg-slate-50/70 p-4">
          <p className="text-xs font-medium text-slate-500">
            Hafta sonu için onaylanan hedef
          </p>
          <p className="mt-1 text-2xl font-semibold text-worktrack-ink">
            {percentageOrPlaceholder(
              plan.target_completion_percentage,
            )}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            {plan.target_description}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            {formatWeekRange(plan.week_start_date, plan.week_end_date)}
          </p>
        </div>

        <div className="rounded-lg border border-worktrack-line bg-white p-4">
          <p className="text-xs font-medium text-slate-500">
            Çalışanın rapor anındaki genel ilerlemesi
          </p>
          <p className="mt-1 text-2xl font-semibold text-worktrack-ink">
            {percentageOrPlaceholder(report.completion_percentage)}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            Rapor tarihi: {formatDateTime(report.received_at)}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Bu değer, raporun gönderildiği andaki genel görev
            ilerlemesidir.
          </p>
        </div>
      </div>

      {plan.status !== 'approved' ? (
        <Alert tone="warning" title="Plan şu anda onaylı değil">
          Rapor bu planla ilişkilendirildiğinde plan onaylıydı; şu anki
          durumu <strong>{planStatus.label}</strong>. Haftalık hedef
          bilgisi tarihsel kayıt olarak gösterilmektedir.
        </Alert>
      ) : null}

      <p className="text-xs leading-5 text-slate-500">
        Haftalık hedef, hafta sonunda ulaşılması beklenen kümülatif
        görev tamamlanma yüzdesidir; haftalık artış değildir. Rapor
        hafta devam ederken alınmışsa iki yüzde arasındaki fark
        otomatik olarak gecikme veya başarısızlık sayılmaz.
      </p>
    </div>
  )
}

export function ReportDetailModal({
  reportId,
  onClose,
}: ReportDetailModalProps) {
  const reportQuery = useQuery({
    queryKey: ['reports', 'detail', reportId],
    queryFn: () => reportsApi.get(reportId as number),
    enabled: reportId !== null,
  })

  const report = reportQuery.data
  const workStatus = report ? workStatusMeta[report.status] : null

  return (
    <Modal
      open={reportId !== null}
      onClose={onClose}
      title="Rapor detayı"
      description={
        report
          ? `${report.task_title ?? 'Görev bilgisi yok'} · ${formatDateTime(
              report.received_at,
            )}`
          : undefined
      }
      size="lg"
      footer={
        <Button variant="secondary" onClick={onClose}>
          Kapat
        </Button>
      }
    >
      {reportQuery.isLoading ? (
        <LoadingState variant="detail" rows={3} />
      ) : reportQuery.isError ? (
        <ErrorState
          message={getErrorMessage(reportQuery.error)}
          onRetry={() => void reportQuery.refetch()}
        />
      ) : report && workStatus ? (
        <div className="space-y-6">
          <Section title="Çalışanın mesajı" icon={FileText}>
            <div className="rounded-lg border border-worktrack-line bg-slate-50 px-4 py-3">
              <p className="text-sm leading-6 break-words whitespace-pre-wrap text-slate-700">
                {report.original_message}
              </p>
            </div>
            <p className="text-xs leading-5 text-slate-500">
              Bu metin çalışanın gönderdiği orijinal içeriktir; AI
              özetiyle karıştırılmamalıdır.
            </p>
          </Section>

          <Section title="AI analizi" icon={Sparkles}>
            <dl className="grid gap-4 sm:grid-cols-2">
              <Value label="AI özeti" preserveWhitespace>
                {textOrPlaceholder(report.summary)}
              </Value>
              <Value label="Görev referansı">
                {textOrPlaceholder(report.task_reference_text)}
              </Value>
              <Value label="Durum">
                <Badge tone={workStatus.tone}>
                  {workStatus.label}
                </Badge>
              </Value>
              <Value label="Genel görev ilerlemesi">
                {percentageOrPlaceholder(
                  report.completion_percentage,
                )}
              </Value>
              <Value label="Engel" preserveWhitespace>
                {textOrPlaceholder(report.blocker)}
              </Value>
              <Value label="Gecikme nedeni" preserveWhitespace>
                {textOrPlaceholder(report.delay_reason)}
              </Value>
              <Value label="Sonraki adım" preserveWhitespace>
                {textOrPlaceholder(report.next_step)}
              </Value>
              <Value label="Tahmini bitiş">
                <EtaValue report={report} />
              </Value>
              <Value label="AI modeli">
                {textOrPlaceholder(report.ai_model)}
              </Value>
            </dl>
          </Section>

          <Section
            title="Haftalık hedef ile gerçekleşen ilerleme"
            icon={Target}
          >
            <WeeklyPlanSection report={report} />
          </Section>

          <Section title="Çalışan onayı" icon={BadgeCheck}>
            <div className="flex flex-wrap items-center gap-2">
              <Badge
                tone={
                  reportReviewStatusMeta[report.review_status].tone
                }
              >
                {reportReviewStatusMeta[report.review_status].label}
              </Badge>
              {report.reviewed_at ? (
                <span className="text-xs text-slate-500">
                  Onay tarihi: {formatDateTime(report.reviewed_at)}
                </span>
              ) : null}
            </div>

            {report.reviewed_by_employee_name ? (
              <p className="text-sm text-slate-600">
                Onaylayan çalışan:{' '}
                <span className="font-medium text-worktrack-ink">
                  {report.reviewed_by_employee_name}
                </span>
              </p>
            ) : null}

            <Alert tone="info" title="Bu bir yönetici onayı değildir">
              Çalışan onayı, çalışanın AI tarafından hazırlanan raporu
              inceleyip onayladığını gösterir. Yönetici değerlendirmesi
              bu ekranın kapsamında değildir.
            </Alert>
          </Section>

          <Section title="Raporun kaynağı" icon={Info}>
            <dl className="grid gap-4 sm:grid-cols-2">
              <Value label="Rapor tarihi">
                {formatDateTime(report.received_at)}
              </Value>
              <Value label="Çalışan">
                {report.employee_id ? (
                  <Link
                    to={`/calisanlar/${report.employee_id}`}
                    className="font-medium text-worktrack-blue hover:underline"
                  >
                    {report.employee_name ?? 'Çalışan'}
                  </Link>
                ) : (
                  textOrPlaceholder(report.employee_name)
                )}
              </Value>
              <Value label="Proje">
                {report.project_id ? (
                  <Link
                    to={`/projeler/${report.project_id}`}
                    className="font-medium text-worktrack-blue hover:underline"
                  >
                    {report.project_name ?? 'Proje'}
                  </Link>
                ) : (
                  textOrPlaceholder(report.project_name)
                )}
              </Value>
              <Value label="Görev">
                {textOrPlaceholder(report.task_title)}
              </Value>
            </dl>
            {report.task_description ? (
              <div className="rounded-lg border border-worktrack-line bg-slate-50/70 px-4 py-3">
                <p className="text-xs font-medium text-slate-500">
                  Görev açıklaması
                </p>
                <p className="mt-1 text-sm break-words whitespace-pre-line text-slate-700">
                  {report.task_description}
                </p>
              </div>
            ) : null}
          </Section>
        </div>
      ) : null}
    </Modal>
  )
}
