import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BarChart3,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Eye,
  Lock,
  OctagonAlert,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import {
  employeesApi,
  projectsApi,
  reportsApi,
  tasksApi,
} from '../api/endpoints'
import { ReportDetailModal } from '../components/reports/ReportDetailModal'
import { Alert } from '../components/ui/Alert'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { DeleteButton } from '../components/ui/DeleteButton'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { StatCard } from '../components/ui/StatCard'
import { useToast } from '../components/ui/Toast'
import { GenerateWeeklyReportDialog } from '../components/weekly-reports/GenerateWeeklyReportDialog'
import { WeeklyReportHistory } from '../components/weekly-reports/WeeklyReportHistory'
import {
  cn,
  formatDateTime,
  getErrorMessage,
  reportReviewStatusMeta,
  workStatusMeta,
} from '../lib/utils'
import type { ReportListItem, WorkStatus } from '../types'

const PAGE_SIZE = 15

const statusOptions: WorkStatus[] = [
  'completed',
  'in_progress',
  'blocked',
  'not_started',
  'unknown',
]

function completionTone(percentage: number | null) {
  if (percentage === null) return 'neutral' as const
  if (percentage >= 100) return 'success' as const
  if (percentage >= 50) return 'info' as const
  if (percentage > 0) return 'warning' as const
  return 'neutral' as const
}

function EmployeeReportsTab() {
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [projectId, setProjectId] = useState('')
  const [employeeId, setEmployeeId] = useState('')
  const [taskId, setTaskId] = useState('')
  const [statusFilter, setStatusFilter] = useState<WorkStatus | ''>('')
  const [blockerOnly, setBlockerOnly] = useState(false)
  const [delayOnly, setDelayOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [selectedReportId, setSelectedReportId] = useState<number | null>(
    null,
  )
  const [deletingReport, setDeletingReport] =
    useState<ReportListItem | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()

  const reportParam = searchParams.get('rapor')

  useEffect(() => {
    if (!reportParam) {
      return
    }

    const parsed = Number(reportParam)

    if (Number.isFinite(parsed) && parsed > 0) {
      setSelectedReportId(parsed)
    }
  }, [reportParam])

  const closeSelectedReport = () => {
    setSelectedReportId(null)

    if (reportParam) {
      const next = new URLSearchParams(searchParams)
      next.delete('rapor')
      setSearchParams(next, { replace: true })
    }
  }

  const projectsQuery = useQuery({
    queryKey: ['projects', 'options'],
    queryFn: projectsApi.options,
  })

  const employeesQuery = useQuery({
    queryKey: ['employees', 'list', 'report-filter'],
    queryFn: () =>
      employeesApi.list({ page: 1, page_size: 100 }),
  })

  const tasksQuery = useQuery({
    queryKey: ['tasks', 'list', 'report-filter', projectId],
    queryFn: () =>
      tasksApi.list({
        page: 1,
        page_size: 100,
        project_id: projectId ? Number(projectId) : undefined,
      }),
  })

  const reportsQuery = useQuery({
    queryKey: [
      'reports',
      'list',
      page,
      dateFrom,
      dateTo,
      projectId,
      employeeId,
      taskId,
      statusFilter,
      blockerOnly,
      delayOnly,
    ],
    queryFn: () =>
      reportsApi.list({
        page,
        page_size: PAGE_SIZE,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        project_id: projectId ? Number(projectId) : undefined,
        employee_id: employeeId ? Number(employeeId) : undefined,
        task_id: taskId ? Number(taskId) : undefined,
        status: statusFilter || undefined,
        has_blocker: blockerOnly ? true : undefined,
        has_delay: delayOnly ? true : undefined,
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => reportsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reports'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      if (deletingReport?.id === selectedReportId) {
        setSelectedReportId(null)
      }
      setDeletingReport(null)
      showToast('Rapor silindi.', 'success')
    },
    onError: (error) => {
      setDeletingReport(null)
      showToast(getErrorMessage(error), 'error')
    },
  })

  const projects = projectsQuery.data ?? []
  const employees = employeesQuery.data?.items ?? []
  const tasks = tasksQuery.data?.items ?? []
  const data = reportsQuery.data
  const stats = data?.stats

  const hasFilters = Boolean(
    dateFrom ||
      dateTo ||
      projectId ||
      employeeId ||
      taskId ||
      statusFilter ||
      blockerOnly ||
      delayOnly,
  )

  const handleProjectChange = (value: string) => {
    setProjectId(value)
    setTaskId('')
    setPage(1)
  }

  const clearFilters = () => {
    setDateFrom('')
    setDateTo('')
    setProjectId('')
    setEmployeeId('')
    setTaskId('')
    setStatusFilter('')
    setBlockerOnly(false)
    setDelayOnly(false)
    setPage(1)
  }

  return (
    <div className="space-y-5">
      {reportsQuery.isError ? null : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <StatCard
            label="Toplam rapor"
            value={stats?.total ?? 0}
            hint="Aktif filtrelerle eşleşen"
            icon={ClipboardList}
            tone="blue"
            isLoading={reportsQuery.isLoading}
          />
          <StatCard
            label="Engellenmiş işler"
            value={stats?.blocked_count ?? 0}
            hint="Durum: Engellendi"
            icon={OctagonAlert}
            tone="amber"
            isLoading={reportsQuery.isLoading}
          />
          <StatCard
            label="Engel bildirilen"
            value={stats?.with_blocker_count ?? 0}
            hint="Engel metni dolu"
            icon={TriangleAlert}
            tone="amber"
            isLoading={reportsQuery.isLoading}
          />
          <StatCard
            label="Gecikme bildirilen"
            value={stats?.with_delay_count ?? 0}
            hint="Gecikme nedeni dolu"
            icon={Clock3}
            tone="amber"
            isLoading={reportsQuery.isLoading}
          />
          <StatCard
            label="Tamamlanmış işler"
            value={stats?.completed_count ?? 0}
            hint="Durum: Tamamlandı"
            icon={CheckCircle2}
            tone="green"
            isLoading={reportsQuery.isLoading}
          />
        </div>
      )}

      <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="report-date-from"
              className="text-xs font-medium text-slate-500"
            >
              Başlangıç tarihi
            </label>
            <input
              id="report-date-from"
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(event) => {
                setDateFrom(event.target.value)
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-40"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="report-date-to"
              className="text-xs font-medium text-slate-500"
            >
              Bitiş tarihi
            </label>
            <input
              id="report-date-to"
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(event) => {
                setDateTo(event.target.value)
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-40"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="report-project-filter"
              className="text-xs font-medium text-slate-500"
            >
              Proje
            </label>
            <select
              id="report-project-filter"
              value={projectId}
              onChange={(event) =>
                handleProjectChange(event.target.value)
              }
              className="field-input w-full py-2 sm:w-44"
            >
              <option value="">Tüm projeler</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="report-employee-filter"
              className="text-xs font-medium text-slate-500"
            >
              Çalışan
            </label>
            <select
              id="report-employee-filter"
              value={employeeId}
              onChange={(event) => {
                setEmployeeId(event.target.value)
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-44"
            >
              <option value="">Tüm çalışanlar</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="report-task-filter"
              className="text-xs font-medium text-slate-500"
            >
              Görev
            </label>
            <select
              id="report-task-filter"
              value={taskId}
              onChange={(event) => {
                setTaskId(event.target.value)
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-52"
            >
              <option value="">Tüm görevler</option>
              {tasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {task.title}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="report-status-filter"
              className="text-xs font-medium text-slate-500"
            >
              Durum
            </label>
            <select
              id="report-status-filter"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(
                  event.target.value as WorkStatus | '',
                )
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-40"
            >
              <option value="">Tüm durumlar</option>
              {statusOptions.map((status) => (
                <option key={status} value={status}>
                  {workStatusMeta[status].label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-4 pb-1">
            <label className="inline-flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={blockerOnly}
                onChange={(event) => {
                  setBlockerOnly(event.target.checked)
                  setPage(1)
                }}
                className="h-4 w-4 rounded border-slate-300 text-worktrack-blue focus:ring-worktrack-blue/30"
              />
              Engel bildirenler
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={delayOnly}
                onChange={(event) => {
                  setDelayOnly(event.target.checked)
                  setPage(1)
                }}
                className="h-4 w-4 rounded border-slate-300 text-worktrack-blue focus:ring-worktrack-blue/30"
              />
              Gecikme bildirenler
            </label>
          </div>

          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Filtreleri temizle
            </Button>
          ) : null}
        </div>

        {data ? (
          <p className="text-sm text-slate-500">{data.total} rapor</p>
        ) : null}
      </div>

      <Alert tone="info" title="İki gösterge farklı şeyleri sayar">
        <strong>Engellenmiş işler</strong> yalnızca durumu
        <em> Engellendi </em> olan raporları sayar.
        <strong> Engel bildirilen</strong> ise durumu farklı olsa da
        engel metni dolu olan raporları sayar. Gecikme bildirimi de
        aynı şekilde yalnızca gecikme nedenine bakar.
      </Alert>

      {reportsQuery.isLoading ? (
        <LoadingState rows={6} />
      ) : reportsQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(reportsQuery.error)}
            onRetry={() => void reportsQuery.refetch()}
          />
        </Card>
      ) : data && data.items.length === 0 ? (
        <Card>
          {hasFilters ? (
            <EmptyState
              icon={ClipboardList}
              title="Eşleşen rapor bulunamadı"
              description="Seçili tarih aralığı, proje, çalışan, görev veya durum için kayıtlı bir rapor yok. Filtreleri değiştirerek tekrar deneyin."
              action={
                <Button variant="secondary" onClick={clearFilters}>
                  Filtreleri temizle
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={ClipboardList}
              title="Henüz iş raporu yok"
              description="Çalışanlar iş güncellemesi gönderdiğinde kayıtlar burada listelenecek. Bu ekranda örnek veya sahte rapor gösterilmez."
            />
          )}
        </Card>
      ) : data ? (
        <>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Rapor tarihi</th>
                  <th scope="col">Çalışan</th>
                  <th scope="col">Proje</th>
                  <th scope="col">Görev</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Genel ilerleme</th>
                  <th scope="col">Engel / Gecikme</th>
                  <th scope="col">Çalışan onayı</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((report) => {
                  const statusMeta = workStatusMeta[report.status]
                  const reviewMeta =
                    reportReviewStatusMeta[report.review_status]

                  return (
                    <tr
                      key={report.id}
                      className="cursor-pointer"
                      onClick={() =>
                        setSelectedReportId(report.id)
                      }
                    >
                      <td className="text-xs whitespace-nowrap text-slate-500">
                        {formatDateTime(report.received_at)}
                      </td>
                      <td>
                        <span className="font-medium text-worktrack-ink">
                          {report.employee_name ?? '—'}
                        </span>
                      </td>
                      <td>
                        {report.project_name ? (
                          <span className="text-slate-600">
                            {report.project_name}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td>
                        {report.task_title ? (
                          <span className="text-slate-700">
                            {report.task_title}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td>
                        <Badge tone={statusMeta.tone}>
                          {statusMeta.label}
                        </Badge>
                      </td>
                      <td>
                        <div className="flex min-w-24 flex-col gap-1.5">
                          <Badge
                            tone={completionTone(
                              report.completion_percentage,
                            )}
                          >
                            {report.completion_percentage === null
                              ? 'Belirtilmedi'
                              : `%${report.completion_percentage}`}
                          </Badge>
                          {report.completion_percentage !== null ? (
                            <div
                              className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
                              role="img"
                              aria-label={`Genel ilerleme: ${report.completion_percentage}`}
                            >
                              <div
                                className="h-full rounded-full bg-worktrack-blue"
                                style={{
                                  width: `${Math.min(
                                    Math.max(
                                      report.completion_percentage,
                                      0,
                                    ),
                                    100,
                                  )}%`,
                                }}
                              />
                            </div>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {report.has_blocker ? (
                            <Badge tone="danger">Engel</Badge>
                          ) : null}
                          {report.has_delay ? (
                            <Badge tone="warning">Gecikme</Badge>
                          ) : null}
                          {!report.has_blocker &&
                          !report.has_delay ? (
                            <span className="text-slate-400">—</span>
                          ) : null}
                        </div>
                      </td>
                      <td>
                        <Badge tone={reviewMeta.tone}>
                          {reviewMeta.label}
                        </Badge>
                      </td>
                      <td>
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              setSelectedReportId(report.id)
                            }
                            aria-label={`Raporu görüntüle: ${
                              report.task_title ?? report.id
                            }`}
                            leftIcon={
                              <Eye
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                            }
                          >
                            Görüntüle
                          </Button>
                          <DeleteButton
                            label={`Raporu sil: ${
                              report.task_title ?? report.id
                            }`}
                            onClick={() => setDeletingReport(report)}
                            disabled={deleteMutation.isPending}
                            isDeleting={
                              deleteMutation.isPending &&
                              deleteMutation.variables === report.id
                            }
                          />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            onPageChange={setPage}
          />
        </>
      ) : null}

      <div className="flex items-start gap-2 rounded-xl border border-worktrack-line bg-white px-4 py-3">
        <Lock
          className="mt-0.5 h-4 w-4 shrink-0 text-slate-400"
          aria-hidden="true"
        />
        <p className="text-xs leading-5 text-slate-500">
          Yönetici yalnızca seçili raporu silebilir. Rapor silme işlemi
          görevi, haftalık planı, çalışan kaydını veya diğer raporları
          değiştirmez. Çalışan onayı, çalışanın AI analizini onayladığını
          gösterir; yönetici onayı değildir.
        </p>
      </div>

      <ConfirmDialog
        open={deletingReport !== null}
        title="Raporu sil"
        description={
          <>
            <p>
              <strong className="text-worktrack-ink">
                {deletingReport?.task_title ?? 'Seçili rapor'}
              </strong>{' '}
              raporunu silmek istediğinizden emin misiniz?
            </p>
            <p>
              Bu işlem geri alınamaz. Yalnızca bu rapor kaydı silinir;
              ilgili görev, haftalık plan ve çalışan kayıtları korunur.
            </p>
          </>
        }
        confirmLabel="Raporu sil"
        tone="danger"
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (deletingReport && !deleteMutation.isPending) {
            deleteMutation.mutate(deletingReport.id)
          }
        }}
        onClose={() => {
          if (!deleteMutation.isPending) {
            setDeletingReport(null)
          }
        }}
      />

      <ReportDetailModal
        reportId={selectedReportId}
        onClose={closeSelectedReport}
      />
    </div>
  )
}

type ReportsTab = 'employee' | 'weekly'

export function ReportsPage() {
  const [generateOpen, setGenerateOpen] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()

  const tab: ReportsTab =
    searchParams.get('sekme') === 'haftalik' ? 'weekly' : 'employee'

  const changeTab = (next: ReportsTab) => {
    const params = new URLSearchParams(searchParams)

    if (next === 'weekly') {
      params.set('sekme', 'haftalik')
    } else {
      params.delete('sekme')
    }

    setSearchParams(params, { replace: true })
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Raporlar"
        description="Çalışanların ilettiği iş raporlarını inceleyin veya seçilen hafta için AI destekli yönetici raporu oluşturun. Rapor belgesi silmek görev, plan veya çalışan kayıtlarını değiştirmez."
        actions={
          <Button
            onClick={() => setGenerateOpen(true)}
            leftIcon={<Sparkles className="h-4 w-4" />}
          >
            Haftalık Yönetici Raporu Oluştur
          </Button>
        }
      />

      <div
        className="flex flex-wrap gap-1 rounded-lg border border-worktrack-line bg-white p-1"
        role="tablist"
        aria-label="Rapor türleri"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'employee'}
          onClick={() => changeTab('employee')}
          className={cn(
            'inline-flex items-center gap-2 rounded-md px-3.5 py-2 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worktrack-blue',
            tab === 'employee'
              ? 'bg-worktrack-blue/10 text-worktrack-blue-dark'
              : 'text-slate-600 hover:bg-slate-50 hover:text-worktrack-ink',
          )}
        >
          <ClipboardList className="h-4 w-4" aria-hidden="true" />
          Çalışan İş Raporları
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'weekly'}
          onClick={() => changeTab('weekly')}
          className={cn(
            'inline-flex items-center gap-2 rounded-md px-3.5 py-2 text-sm font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worktrack-blue',
            tab === 'weekly'
              ? 'bg-worktrack-blue/10 text-worktrack-blue-dark'
              : 'text-slate-600 hover:bg-slate-50 hover:text-worktrack-ink',
          )}
        >
          <BarChart3 className="h-4 w-4" aria-hidden="true" />
          Haftalık Yönetici Raporları
        </button>
      </div>

      {tab === 'employee' ? (
        <EmployeeReportsTab />
      ) : (
        <WeeklyReportHistory
          onGenerate={() => setGenerateOpen(true)}
        />
      )}

      <GenerateWeeklyReportDialog
        open={generateOpen}
        onClose={() => setGenerateOpen(false)}
        onOpenReport={(reportId) => {
          setGenerateOpen(false)
          navigate(`/raporlar/haftalik/${reportId}`)
        }}
      />
    </div>
  )
}
