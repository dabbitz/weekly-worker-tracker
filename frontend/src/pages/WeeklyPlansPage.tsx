import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CalendarDays,
  CalendarRange,
  Check,
  MessageSquareText,
  Pencil,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError } from '../api/client'
import { projectsApi, tasksApi, weeklyPlansApi } from '../api/endpoints'
import { AIGeneratePlansDialog } from '../components/weekly-plans/AIGeneratePlansDialog'
import { WeeklyPlanFormDialog } from '../components/weekly-plans/WeeklyPlanFormDialog'
import { Alert } from '../components/ui/Alert'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { Modal } from '../components/ui/Modal'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { useToast } from '../components/ui/Toast'
import {
  formatDate,
  formatDateTime,
  formatWeekRange,
  getErrorMessage,
  weeklyPlanSourceMeta,
  weeklyPlanStatusMeta,
} from '../lib/utils'
import type {
  WeeklyPlan,
  WeeklyPlanSource,
  WeeklyPlanStatus,
} from '../types'

const PAGE_SIZE = 15

interface ConfirmState {
  title: string
  description: ReactNode
  confirmLabel: string
  tone?: 'primary' | 'danger'
  action: () => void
}

function completionTone(percentage: number | null) {
  if (percentage === null) return 'neutral' as const
  if (percentage >= 100) return 'success' as const
  if (percentage >= 50) return 'info' as const
  if (percentage > 0) return 'warning' as const
  return 'neutral' as const
}

export function WeeklyPlansPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const taskParam = searchParams.get('gorev')
  const generationParam = searchParams.get('uretim')
  const [projectId, setProjectId] = useState('')
  const [taskId, setTaskId] = useState(taskParam ?? '')
  const [weekStart, setWeekStart] = useState('')
  const [statusFilter, setStatusFilter] = useState<
    WeeklyPlanStatus | ''
  >('')
  const [sourceFilter, setSourceFilter] = useState<
    WeeklyPlanSource | ''
  >('')
  const [generationId, setGenerationId] = useState(
    generationParam ?? '',
  )
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<WeeklyPlan | null>(null)
  const [aiTaskIds, setAiTaskIds] = useState<number[] | null>(null)
  const [notesPlan, setNotesPlan] = useState<WeeklyPlan | null>(null)
  const [confirm, setConfirm] = useState<ConfirmState | null>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const projectsQuery = useQuery({
    queryKey: ['projects', 'options'],
    queryFn: projectsApi.options,
  })

  const tasksQuery = useQuery({
    queryKey: ['tasks', 'list', 'weekly-plan-filter', projectId],
    queryFn: () =>
      tasksApi.list({
        page: 1,
        page_size: 100,
        project_id: projectId ? Number(projectId) : undefined,
      }),
  })

  const plansQuery = useQuery({
    queryKey: [
      'weekly-plans',
      'list',
      page,
      projectId,
      taskId,
      weekStart,
      statusFilter,
      sourceFilter,
      generationId,
    ],
    queryFn: () =>
      weeklyPlansApi.list({
        page,
        page_size: PAGE_SIZE,
        project_id: projectId ? Number(projectId) : undefined,
        task_id: taskId ? Number(taskId) : undefined,
        week_start_date: weekStart || undefined,
        status: statusFilter || undefined,
        source: sourceFilter || undefined,
        generation_id: generationId
          ? Number(generationId)
          : undefined,
      }),
  })

  useEffect(() => {
    setTaskId(taskParam ?? '')
    setPage(1)
  }, [taskParam])

  useEffect(() => {
    setGenerationId(generationParam ?? '')
    setPage(1)
  }, [generationParam])

  const invalidatePlanData = () => {
    void queryClient.invalidateQueries({ queryKey: ['weekly-plans'] })
    void queryClient.invalidateQueries({ queryKey: ['tasks'] })
    void queryClient.invalidateQueries({ queryKey: ['projects'] })
    void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const approveMutation = useMutation({
    mutationFn: ({
      id,
      replaceExisting,
    }: {
      id: number
      replaceExisting: boolean
    }) => weeklyPlansApi.approve(id, replaceExisting),
    onSuccess: (plan) => {
      invalidatePlanData()
      setConfirm(null)
      showToast(
        plan.status === 'approved'
          ? 'Plan onaylandı ve resmî haftalık hedef oldu.'
          : 'Plan güncellendi.',
        'success',
      )
    },
    onError: (error, variables) => {
      if (
        error instanceof ApiError &&
        error.status === 409 &&
        !variables.replaceExisting &&
        error.message.includes('zaten onaylanmış')
      ) {
        setConfirm({
          title: 'Bu hafta için onaylı plan var',
          description: (
            <>
              <p>
                Aynı görev ve hafta için zaten onaylanmış bir plan
                bulunuyor. Yeni planı onaylarsanız eski plan fiziksel
                olarak silinmez; <strong>Eski Plan</strong> durumuna
                alınır ve geçmiş kayıtlar korunur.
              </p>
              <p className="mt-2">
                Yeni planı resmî hedef yapmak istiyor musunuz?
              </p>
            </>
          ),
          confirmLabel: 'Yeni planı onayla',
          tone: 'danger',
          action: () =>
            approveMutation.mutate({
              id: variables.id,
              replaceExisting: true,
            }),
        })
        return
      }

      setConfirm(null)
      showToast(getErrorMessage(error), 'error')
    },
  })

  const rejectMutation = useMutation({
    mutationFn: (id: number) => weeklyPlansApi.reject(id),
    onSuccess: () => {
      invalidatePlanData()
      setConfirm(null)
      showToast('Taslak reddedildi. Kayıt geçmişte görüntülenebilir.', 'success')
    },
    onError: (error) => {
      setConfirm(null)
      showToast(getErrorMessage(error), 'error')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => weeklyPlansApi.remove(id),
    onSuccess: () => {
      invalidatePlanData()
      setConfirm(null)
      showToast('Taslak silindi.', 'success')
    },
    onError: (error) => {
      setConfirm(null)
      showToast(getErrorMessage(error), 'error')
    },
  })

  const handleProjectChange = (value: string) => {
    setProjectId(value)
    setTaskId('')
    setPage(1)

    const next = new URLSearchParams(searchParams)
    next.delete('gorev')
    setSearchParams(next, { replace: true })
  }

  const handleTaskChange = (value: string) => {
    setTaskId(value)
    setPage(1)

    const next = new URLSearchParams(searchParams)
    if (value) {
      next.set('gorev', value)
    } else {
      next.delete('gorev')
    }
    setSearchParams(next, { replace: true })
  }

  const clearGeneration = () => {
    setGenerationId('')
    setPage(1)

    const next = new URLSearchParams(searchParams)
    next.delete('uretim')
    setSearchParams(next, { replace: true })
  }

  const clearFilters = () => {
    setProjectId('')
    setTaskId('')
    setWeekStart('')
    setStatusFilter('')
    setSourceFilter('')
    setGenerationId('')
    setPage(1)
    setSearchParams({}, { replace: true })
  }

  const openCreate = () => {
    setEditingPlan(null)
    setFormOpen(true)
  }

  const openEdit = (plan: WeeklyPlan) => {
    setEditingPlan(plan)
    setFormOpen(true)
  }

  const closeForm = () => {
    setFormOpen(false)
    setEditingPlan(null)
  }

  const openAiForTask = (plan: WeeklyPlan) => {
    setAiTaskIds([plan.task_id])
  }

  const openAiFromHeader = () => {
    if (taskId) {
      setAiTaskIds([Number(taskId)])
      return
    }

    showToast(
      'AI planı için önce Görevler sayfasından bir veya birden fazla görev seçin.',
      'info',
    )
    navigate('/gorevler')
  }

  const data = plansQuery.data
  const projects = projectsQuery.data ?? []
  const tasks = tasksQuery.data?.items ?? []
  const hasFilters = Boolean(
    projectId ||
      taskId ||
      weekStart ||
      statusFilter ||
      sourceFilter ||
      generationId,
  )
  const defaultTaskId = taskId ? Number(taskId) : undefined

  return (
    <div className="space-y-5">
      <PageHeader
        title="Haftalık Planlar"
        description="AI veya manuel oluşturulan haftalık hedefleri inceleyin; taslakları düzenleyin, onaylayın veya reddedin."
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant="soft"
              onClick={openAiFromHeader}
              leftIcon={<Sparkles className="h-4 w-4" />}
            >
              AI ile plan oluştur
            </Button>
            <Button
              onClick={openCreate}
              leftIcon={<Plus className="h-4 w-4" />}
            >
              Yeni haftalık plan
            </Button>
          </div>
        }
      />

      <div className="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
          <div className="flex flex-col gap-1">
            <label
              htmlFor="plan-project-filter"
              className="text-xs font-medium text-slate-500"
            >
              Proje
            </label>
            <select
              id="plan-project-filter"
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
              htmlFor="plan-task-filter"
              className="text-xs font-medium text-slate-500"
            >
              Görev
            </label>
            <select
              id="plan-task-filter"
              value={taskId}
              onChange={(event) => handleTaskChange(event.target.value)}
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
              htmlFor="plan-status-filter"
              className="text-xs font-medium text-slate-500"
            >
              Durum
            </label>
            <select
              id="plan-status-filter"
              value={statusFilter}
              onChange={(event) => {
                setStatusFilter(
                  event.target.value as WeeklyPlanStatus | '',
                )
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-36"
            >
              <option value="">Tüm durumlar</option>
              <option value="draft">Taslak</option>
              <option value="approved">Onaylandı</option>
              <option value="rejected">Reddedildi</option>
              <option value="superseded">Eski Plan</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="plan-source-filter"
              className="text-xs font-medium text-slate-500"
            >
              Kaynak
            </label>
            <select
              id="plan-source-filter"
              value={sourceFilter}
              onChange={(event) => {
                setSourceFilter(
                  event.target.value as WeeklyPlanSource | '',
                )
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-32"
            >
              <option value="">Tümü</option>
              <option value="ai">AI</option>
              <option value="manual">Manuel</option>
            </select>
          </div>

          <div className="flex flex-col gap-1">
            <label
              htmlFor="plan-week-filter"
              className="text-xs font-medium text-slate-500"
            >
              Hafta başlangıcı
            </label>
            <input
              id="plan-week-filter"
              type="date"
              value={weekStart}
              onChange={(event) => {
                setWeekStart(event.target.value)
                setPage(1)
              }}
              className="field-input w-full py-2 sm:w-40"
            />
          </div>

          {hasFilters ? (
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Filtreleri temizle
            </Button>
          ) : null}
        </div>

        {data ? (
          <p className="text-sm text-slate-500">{data.total} plan</p>
        ) : null}
      </div>

      {generationId ? (
        <Alert tone="info" title="AI üretim grubu">
          <div className="flex flex-wrap items-center gap-2">
            <span>
              Yalnızca AI üretim grubu #{generationId} içindeki
              taslaklar gösteriliyor. Her plan ayrı ayrı düzenlenip
              onaylanabilir.
            </span>
            <button
              type="button"
              onClick={clearGeneration}
              className="font-semibold underline underline-offset-2"
            >
              Grubu temizle
            </button>
          </div>
        </Alert>
      ) : null}

      {plansQuery.isLoading ? (
        <LoadingState rows={6} />
      ) : plansQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(plansQuery.error)}
            onRetry={() => void plansQuery.refetch()}
          />
        </Card>
      ) : data && data.items.length === 0 ? (
        <Card>
          {hasFilters ? (
            <EmptyState
              icon={CalendarDays}
              title="Eşleşen haftalık plan bulunamadı"
              description="Seçili proje, görev, hafta veya durum için tanımlanmış bir plan yok. Filtreleri değiştirin ya da yeni bir plan oluşturun."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Button variant="secondary" onClick={clearFilters}>
                    Filtreleri temizle
                  </Button>
                  <Button
                    onClick={openCreate}
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    Plan oluştur
                  </Button>
                </div>
              }
            />
          ) : (
            <EmptyState
              icon={CalendarDays}
              title="Henüz haftalık plan yok"
              description="Haftalık planlar bir göreve bağlıdır. Görevler sayfasından görev seçip AI ile taslak oluşturabilir veya manuel plan ekleyebilirsiniz."
              action={
                <div className="flex flex-wrap justify-center gap-2">
                  <Button
                    onClick={openCreate}
                    leftIcon={<Plus className="h-4 w-4" />}
                  >
                    İlk planı oluştur
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => navigate('/gorevler')}
                    leftIcon={<Sparkles className="h-4 w-4" />}
                  >
                    Görevlerden AI planı oluştur
                  </Button>
                </div>
              }
            />
          )}
        </Card>
      ) : data ? (
        <>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Görev</th>
                  <th scope="col">Hafta</th>
                  <th scope="col">Hedef Açıklaması</th>
                  <th scope="col">Hedef Tamamlanma</th>
                  <th scope="col">Kaynak</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Oluşturulma</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((plan) => {
                  const statusMeta =
                    weeklyPlanStatusMeta[plan.status]
                  const sourceMeta =
                    weeklyPlanSourceMeta[plan.source]
                  const hasNotes = Boolean(
                    plan.ai_rationale ||
                      plan.ai_assumptions ||
                      plan.ai_warnings,
                  )

                  return (
                    <tr key={plan.id}>
                      <td>
                        <div className="min-w-0">
                          <p className="font-medium text-worktrack-ink">
                            {plan.task_title}
                          </p>
                          <Link
                            to={`/projeler/${plan.project_id}`}
                            className="text-xs text-slate-500 hover:text-worktrack-blue hover:underline"
                          >
                            {plan.project_name}
                          </Link>
                        </div>
                      </td>
                      <td>
                        <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-slate-600">
                          <CalendarRange
                            className="h-3.5 w-3.5 text-slate-400"
                            aria-hidden="true"
                          />
                          {formatWeekRange(
                            plan.week_start_date,
                            plan.week_end_date,
                          )}
                        </span>
                      </td>
                      <td>
                        <p className="max-w-sm text-slate-600">
                          {plan.target_description}
                        </p>
                        {plan.status === 'approved' &&
                        plan.approved_at ? (
                          <p className="mt-1 text-xs text-slate-400">
                            Onay: {formatDateTime(plan.approved_at)}
                          </p>
                        ) : null}
                      </td>
                      <td>
                        <div className="flex min-w-28 flex-col gap-1.5">
                          <Badge
                            tone={completionTone(
                              plan.target_completion_percentage,
                            )}
                          >
                            {plan.target_completion_percentage === null
                              ? 'Belirtilmedi'
                              : `%${plan.target_completion_percentage}`}
                          </Badge>
                          {plan.target_completion_percentage !==
                          null ? (
                            <div
                              className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100"
                              role="img"
                              aria-label={`Hedef tamamlanma yüzdesi: ${plan.target_completion_percentage}`}
                            >
                              <div
                                className="h-full rounded-full bg-worktrack-blue"
                                style={{
                                  width: `${Math.min(
                                    Math.max(
                                      plan.target_completion_percentage,
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
                        <Badge tone={sourceMeta.tone}>
                          {sourceMeta.label}
                        </Badge>
                      </td>
                      <td>
                        <Badge tone={statusMeta.tone}>
                          {statusMeta.label}
                        </Badge>
                      </td>
                      <td className="text-xs text-slate-500">
                        {formatDateTime(plan.created_at)}
                      </td>
                      <td>
                        <div className="flex items-center justify-end gap-0.5">
                          {hasNotes ? (
                            <button
                              type="button"
                              onClick={() => setNotesPlan(plan)}
                              className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-worktrack-blue"
                              aria-label={`${plan.task_title} AI plan notlarını görüntüle`}
                              title="AI notlarını görüntüle"
                            >
                              <MessageSquareText
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                            </button>
                          ) : null}

                          {plan.status === 'draft' ? (
                            <>
                              <button
                                type="button"
                                onClick={() => openEdit(plan)}
                                className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                                aria-label={`${plan.task_title} haftalık planını düzenle`}
                                title="Düzenle"
                              >
                                <Pencil
                                  className="h-4 w-4"
                                  aria-hidden="true"
                                />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  approveMutation.mutate({
                                    id: plan.id,
                                    replaceExisting: false,
                                  })
                                }
                                className="rounded-md p-1.5 text-slate-400 transition hover:bg-emerald-50 hover:text-emerald-700"
                                aria-label={`${plan.task_title} haftalık planını onayla`}
                                title="Onayla"
                              >
                                <Check
                                  className="h-4 w-4"
                                  aria-hidden="true"
                                />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setConfirm({
                                    title: 'Taslağı reddet',
                                    description: (
                                      <p>
                                        Bu taslak reddedilecek. Kayıt
                                        silinmez; geçmişte
                                        görüntülenebilir ancak resmî
                                        program olarak kullanılmaz.
                                      </p>
                                    ),
                                    confirmLabel: 'Taslağı reddet',
                                    tone: 'danger',
                                    action: () =>
                                      rejectMutation.mutate(plan.id),
                                  })
                                }
                                className="rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                                aria-label={`${plan.task_title} haftalık planını reddet`}
                                title="Reddet"
                              >
                                <X
                                  className="h-4 w-4"
                                  aria-hidden="true"
                                />
                              </button>
                            </>
                          ) : null}

                          {plan.status === 'rejected' ? (
                            <button
                              type="button"
                              onClick={() =>
                                setConfirm({
                                  title: 'Reddedilen planı sil',
                                  description: (
                                    <p>
                                      Bu reddedilmiş plan kalıcı olarak
                                      silinecek. İş güncellemesiyle
                                      ilişkiliyse silme engellenir.
                                    </p>
                                  ),
                                  confirmLabel: 'Planı sil',
                                  tone: 'danger',
                                  action: () =>
                                    deleteMutation.mutate(plan.id),
                                })
                              }
                              className="rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                              aria-label={`${plan.task_title} reddedilen planını sil`}
                              title="Sil"
                            >
                              <Trash2
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                            </button>
                          ) : null}

                          {plan.status === 'draft' ? (
                            <button
                              type="button"
                              onClick={() =>
                                setConfirm({
                                  title: 'Taslağı sil',
                                  description: (
                                    <p>
                                      Bu taslak kalıcı olarak silinecek.
                                      Onaylanmış planlar ve iş
                                      güncellemesiyle ilişkili planlar
                                      silinemez.
                                    </p>
                                  ),
                                  confirmLabel: 'Taslağı sil',
                                  tone: 'danger',
                                  action: () =>
                                    deleteMutation.mutate(plan.id),
                                })
                              }
                              className="rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                              aria-label={`${plan.task_title} taslağını sil`}
                              title="Sil"
                            >
                              <Trash2
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                            </button>
                          ) : null}

                          {plan.source === 'ai' ? (
                            <button
                              type="button"
                              onClick={() => openAiForTask(plan)}
                              className="rounded-md p-1.5 text-slate-400 transition hover:bg-blue-50 hover:text-worktrack-blue"
                              aria-label={`${plan.task_title} için AI ile yeni taslak oluştur`}
                              title="Yeniden oluştur"
                            >
                              <RefreshCw
                                className="h-4 w-4"
                                aria-hidden="true"
                              />
                            </button>
                          ) : null}
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
        <CalendarRange
          className="mt-0.5 h-4 w-4 shrink-0 text-slate-400"
          aria-hidden="true"
        />
        <p className="text-xs leading-5 text-slate-500">
          Hedef tamamlanma yüzdesi, ilgili haftanın sonunda görevin
          ulaşması beklenen toplam ilerlemedir; haftalık artış değildir.
          Yalnızca <strong>Onaylandı</strong> durumundaki planlar resmî
          haftalık program sayılır. AI taslakları siz onaylamadan resmî
          plan olmaz.
        </p>
      </div>

      <WeeklyPlanFormDialog
        open={formOpen}
        onClose={closeForm}
        plan={editingPlan}
        defaultTaskId={defaultTaskId}
      />

      {aiTaskIds !== null ? (
        <AIGeneratePlansDialog
          open
          taskIds={aiTaskIds}
          onClose={() => setAiTaskIds(null)}
          onGenerated={(response) => {
            const next = new URLSearchParams(searchParams)
            next.set('uretim', String(response.generation_id))
            setSearchParams(next, { replace: true })
            setGenerationId(String(response.generation_id))
            setPage(1)
          }}
        />
      ) : null}

      <Modal
        open={notesPlan !== null}
        onClose={() => setNotesPlan(null)}
        title="AI plan notları"
        description={
          notesPlan
            ? `${notesPlan.task_title} · ${formatWeekRange(
                notesPlan.week_start_date,
                notesPlan.week_end_date,
              )}`
            : undefined
        }
        size="lg"
        footer={
          <Button variant="secondary" onClick={() => setNotesPlan(null)}>
            Kapat
          </Button>
        }
      >
        {notesPlan ? (
          <div className="space-y-3">
            <div className="rounded-lg border border-worktrack-line bg-slate-50 px-3 py-2.5 text-sm text-slate-600">
              <p className="font-semibold text-worktrack-ink">
                {notesPlan.target_description}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Durum: {weeklyPlanStatusMeta[notesPlan.status].label} ·
                Kaynak: {weeklyPlanSourceMeta[notesPlan.source].label} ·
                Hafta: {formatDate(notesPlan.week_start_date)} –{' '}
                {formatDate(notesPlan.week_end_date)}
              </p>
            </div>

            {notesPlan.ai_rationale ? (
              <Alert tone="info" title="Gerekçe">
                <p className="whitespace-pre-line">
                  {notesPlan.ai_rationale}
                </p>
              </Alert>
            ) : null}

            {notesPlan.ai_assumptions ? (
              <Alert tone="warning" title="Varsayımlar">
                <p className="whitespace-pre-line">
                  {notesPlan.ai_assumptions}
                </p>
              </Alert>
            ) : null}

            {notesPlan.ai_warnings ? (
              <Alert tone="error" title="Uyarılar">
                <p className="whitespace-pre-line">
                  {notesPlan.ai_warnings}
                </p>
              </Alert>
            ) : null}

            {!notesPlan.ai_rationale &&
            !notesPlan.ai_assumptions &&
            !notesPlan.ai_warnings ? (
              <p className="text-sm text-slate-500">
                Bu plan için AI notu bulunmuyor.
              </p>
            ) : null}
          </div>
        ) : null}
      </Modal>

      <ConfirmDialog
        open={confirm !== null}
        title={confirm?.title ?? ''}
        description={confirm?.description ?? null}
        confirmLabel={confirm?.confirmLabel ?? 'Devam et'}
        tone={confirm?.tone}
        isLoading={
          approveMutation.isPending ||
          rejectMutation.isPending ||
          deleteMutation.isPending
        }
        onConfirm={() => confirm?.action()}
        onClose={() => setConfirm(null)}
      />
    </div>
  )
}
