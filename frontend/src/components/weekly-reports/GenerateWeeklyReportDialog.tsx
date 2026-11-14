import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Sparkles } from 'lucide-react'
import { useEffect, useId, useState } from 'react'

import { weeklyReportsApi } from '../../api/endpoints'
import { getErrorMessage } from '../../lib/utils'
import type {
  WeekPeriod,
  WeeklyReportDetail,
} from '../../types'
import { Alert } from '../ui/Alert'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { Field, Select, Textarea } from '../ui/Form'
import { LoadingState } from '../ui/LoadingState'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'

interface GenerateWeeklyReportDialogProps {
  open: boolean
  onClose: () => void
  onOpenReport: (reportId: number) => void
}

function newRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID().replace(/-/g, '')
  }

  return `req${Date.now().toString(36)}${Math.random()
    .toString(36)
    .slice(2, 12)}`
}

function periodHint(period: WeekPeriod): string {
  const hints: string[] = []

  if (period.is_default) hints.push('Varsayılan')
  if (period.is_current_week) hints.push('Bu hafta')
  if (period.is_partial_week) hints.push('Kısmi hafta')

  return hints.length > 0 ? ` (${hints.join(' · ')})` : ''
}

export function GenerateWeeklyReportDialog({
  open,
  onClose,
  onOpenReport,
}: GenerateWeeklyReportDialogProps) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const weekFieldId = useId()
  const instructionsFieldId = useId()

  const [selectedWeek, setSelectedWeek] = useState('')
  const [instructions, setInstructions] = useState('')
  const [requestId, setRequestId] = useState(newRequestId)
  const [attempted, setAttempted] = useState(false)
  const [created, setCreated] = useState<WeeklyReportDetail | null>(null)

  useEffect(() => {
    if (!open) {
      return
    }

    setSelectedWeek('')
    setInstructions('')
    setRequestId(newRequestId())
    setAttempted(false)
    setCreated(null)
  }, [open])

  const periodsQuery = useQuery({
    queryKey: ['weekly-report-periods'],
    queryFn: () => weeklyReportsApi.periods(12),
    enabled: open,
    staleTime: 5 * 60_000,
  })

  const periods = periodsQuery.data?.periods ?? []

  const defaultWeek = periodsQuery.data?.default_week_start_date ?? ''
  const activeWeek = selectedWeek || defaultWeek

  useEffect(() => {
    if (!selectedWeek && defaultWeek) {
      setSelectedWeek(defaultWeek)
    }
  }, [defaultWeek, selectedWeek])

  const previewQuery = useQuery({
    queryKey: ['weekly-report-preview', activeWeek],
    queryFn: () => weeklyReportsApi.preview(activeWeek),
    enabled: open && activeWeek.length > 0 && !created,
    staleTime: 60_000,
  })

  const createMutation = useMutation({
    mutationFn: () =>
      weeklyReportsApi.create({
        week_start_date: activeWeek,
        request_id: requestId,
        extra_instructions:
          instructions.trim().length > 0
            ? instructions.trim()
            : undefined,
      }),
    onSuccess: (report) => {
      setCreated(report)
      showToast('Haftalık yönetici raporu oluşturuldu.', 'success')
      void queryClient.invalidateQueries({
        queryKey: ['weekly-reports'],
      })
    },
  })

  const locked =
    createMutation.isPending || (attempted && createMutation.isError)
  const selectedPeriod = periods.find(
    (period) => period.week_start_date === activeWeek,
  )

  const handleClose = () => {
    if (createMutation.isPending) {
      return
    }

    onClose()
  }

  const handleSubmit = () => {
    if (!activeWeek || createMutation.isPending) {
      return
    }

    setAttempted(true)
    createMutation.mutate()
  }

  const footer = created ? (
    <>
      <Button variant="secondary" onClick={handleClose}>
        Kapat
      </Button>
      <Button onClick={() => onOpenReport(created.id)}>
        Raporu Aç
      </Button>
    </>
  ) : (
    <>
      <Button
        variant="secondary"
        onClick={handleClose}
        disabled={createMutation.isPending}
      >
        Vazgeç
      </Button>
      <Button
        onClick={handleSubmit}
        isLoading={createMutation.isPending}
        disabled={
          !activeWeek ||
          createMutation.isPending ||
          previewQuery.isLoading
        }
        leftIcon={<Sparkles className="h-4 w-4" />}
      >
        {createMutation.isPending
          ? 'Rapor Oluşturuluyor'
          : createMutation.isError
            ? 'Tekrar dene'
            : 'Rapor Oluştur'}
      </Button>
    </>
  )

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Haftalık Yönetici Raporu Oluştur"
      description="Sayılar deterministik metriklerden gelir; yapay zekâ yalnızca yorumlar."
      size="lg"
      footer={footer}
    >
      {created ? (
        <div className="space-y-4">
          <Alert tone="success" title="Rapor hazır">
            {created.is_partial_week
              ? 'Kısmi değerlendirme: seçilen hafta henüz tamamlanmadı. '
              : ''}
            {created.week_start_date} – {created.week_end_date} dönemi
            için {created.version}. sürüm oluşturuldu.
          </Alert>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <p>
              <span className="font-semibold text-worktrack-ink">
                Görev:
              </span>{' '}
              {created.task_count} ·{' '}
              <span className="font-semibold text-worktrack-ink">
                İş raporu:
              </span>{' '}
              {created.report_count} ·{' '}
              <span className="font-semibold text-worktrack-ink">
                Müdahale adayı:
              </span>{' '}
              {created.intervention_count}
            </p>
            {created.model ? (
              <p className="mt-1 text-xs text-slate-500">
                Model: {created.model}
              </p>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="space-y-5">
          {periodsQuery.isLoading ? (
            <LoadingState variant="cards" />
          ) : periodsQuery.isError ? (
            <ErrorState
              message={getErrorMessage(periodsQuery.error)}
              onRetry={() => void periodsQuery.refetch()}
              compact
            />
          ) : (
            <Field
              label="Hafta"
              htmlFor={weekFieldId}
              required
              hint="Haftalar pazartesi–pazar aralığındadır. Gelecek haftalar seçilemez."
            >
              <Select
                id={weekFieldId}
                value={activeWeek}
                disabled={locked}
                onChange={(event) => {
                  setSelectedWeek(event.target.value)
                  createMutation.reset()
                }}
              >
                {periods.map((period) => (
                  <option
                    key={period.week_start_date}
                    value={period.week_start_date}
                  >
                    {period.label}
                    {periodHint(period)}
                  </option>
                ))}
              </Select>
            </Field>
          )}

          {selectedPeriod?.is_partial_week ? (
            <Alert tone="warning" title="Kısmi hafta">
              Seçilen hafta henüz tamamlanmadı. Rapor “Kısmi
              değerlendirme” etiketiyle oluşturulur ve hafta sonu
              itibarıyla kesinleşmez.
            </Alert>
          ) : null}

          {activeWeek && previewQuery.isLoading ? (
            <LoadingState variant="cards" />
          ) : previewQuery.isError ? (
            <ErrorState
              message={getErrorMessage(previewQuery.error)}
              onRetry={() => void previewQuery.refetch()}
              compact
            />
          ) : previewQuery.data ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-slate-200">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-slate-50/70 px-4 py-2.5">
                  <p className="text-sm font-semibold text-worktrack-ink">
                    {previewQuery.data.label}
                  </p>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {previewQuery.data.is_partial_week ? (
                      <Badge tone="warning">Kısmi hafta</Badge>
                    ) : (
                      <Badge tone="success">Tamamlanmış hafta</Badge>
                    )}
                    <Badge tone="info">Yapay zekâ önizlemesi yok</Badge>
                  </div>
                </div>
                <dl className="grid grid-cols-2 gap-3 px-4 py-3 text-sm sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-slate-500">Proje</dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.project_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">Görev</dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.task_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Onaylı iş raporu
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.report_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Bekleyen rapor
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.pending_review_report_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Haftalık plan
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.plan_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Müdahale adayı
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.intervention_candidate_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Raporsuz görev
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.no_report_task_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-slate-500">
                      Plan çakışması
                    </dt>
                    <dd className="font-semibold text-worktrack-ink">
                      {previewQuery.data.plan_conflict_count}
                    </dd>
                  </div>
                </dl>
              </div>

              {!previewQuery.data.has_data ? (
                <Alert tone="info" title="Veri bulunmayan hafta">
                  Bu hafta için değerlendirilecek görev, iş raporu veya
                  haftalık plan yok. Boş rapor deterministik olarak
                  oluşturulur; yapay zekâ çağrılmaz.
                </Alert>
              ) : null}

              {previewQuery.data.warnings.length > 0 ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-4">
                  <p className="text-sm font-semibold text-amber-900">
                    Veri kalitesi uyarıları
                  </p>
                  <ul className="mt-2 space-y-1.5 text-sm text-amber-900">
                    {previewQuery.data.warnings.map((warning) => (
                      <li
                        key={warning.code}
                        className="flex gap-2"
                      >
                        <span
                          className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"
                          aria-hidden="true"
                        />
                        <span>
                          <span className="font-medium">
                            {warning.code}
                          </span>{' '}
                          — {warning.message}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {previewQuery.data.projects.length > 0 ? (
                <div className="rounded-lg border border-slate-200">
                  <p className="border-b border-slate-200 px-4 py-2.5 text-sm font-semibold text-worktrack-ink">
                    Kapsamdaki projeler
                  </p>
                  <ul className="divide-y divide-slate-100">
                    {previewQuery.data.projects.map((project) => (
                      <li
                        key={project.project_token}
                        className="flex items-center justify-between gap-3 px-4 py-2 text-sm"
                      >
                        <span className="truncate text-slate-700">
                          {project.name}
                        </span>
                        <span className="shrink-0 text-xs text-slate-500">
                          {project.task_count} görev ·{' '}
                          {project.report_count} rapor
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {previewQuery.data.has_data &&
              previewQuery.data.projects.length === 0 ? (
                <EmptyState
                  compact
                  icon={CalendarDays}
                  title="Proje kapsamı boş"
                  description="Bu hafta için proje bazlı bir değerlendirme oluşturulacak veri bulunmuyor."
                />
              ) : null}
            </div>
          ) : null}

          <Field
            label="Ek talimatlar (isteğe bağlı)"
            htmlFor={instructionsFieldId}
            hint={`${instructions.length}/2000 karakter. Yalnızca yorum odağını belirtir; sayıları değiştiremez.`}
          >
            <Textarea
              id={instructionsFieldId}
              value={instructions}
              maxLength={2000}
              rows={3}
              disabled={locked}
              onChange={(event) =>
                setInstructions(event.target.value)
              }
              placeholder="Örn. riskli işlere ve gecikme nedenlerine odaklan."
            />
          </Field>

          {createMutation.isError ? (
            <Alert tone="error" title="Rapor oluşturulamadı">
              {getErrorMessage(createMutation.error)}
              {attempted ? (
                <p className="mt-2 text-xs">
                  Aynı istek kimliğiyle yeniden denenecek. Hafta ve
                  talimatlar bu nedenle sabitlendi.
                </p>
              ) : null}
            </Alert>
          ) : null}

          {createMutation.isPending ? (
            <Alert tone="info" title="Rapor hazırlanıyor">
              Yapay zekâ çağrısı sürüyor. Bu işlem birkaç saniye
              sürebilir; pencereyi kapatmayın.
            </Alert>
          ) : null}
        </div>
      )}
    </Modal>
  )
}
