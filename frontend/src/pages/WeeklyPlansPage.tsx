import { useQuery } from '@tanstack/react-query'
import {
  CalendarDays,
  CalendarRange,
  Pencil,
  Plus,
  Target,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { projectsApi, tasksApi, weeklyPlansApi } from '../api/endpoints'
import { WeeklyPlanFormDialog } from '../components/weekly-plans/WeeklyPlanFormDialog'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import {
  formatDateTime,
  formatWeekRange,
  getErrorMessage,
} from '../lib/utils'
import type { WeeklyPlan } from '../types'

const PAGE_SIZE = 15

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
  const [projectId, setProjectId] = useState('')
  const [taskId, setTaskId] = useState(taskParam ?? '')
  const [weekStart, setWeekStart] = useState('')
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<WeeklyPlan | null>(null)

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
    ],
    queryFn: () =>
      weeklyPlansApi.list({
        page,
        page_size: PAGE_SIZE,
        project_id: projectId ? Number(projectId) : undefined,
        task_id: taskId ? Number(taskId) : undefined,
        week_start_date: weekStart || undefined,
      }),
  })

  useEffect(() => {
    setTaskId(taskParam ?? '')
    setPage(1)
  }, [taskParam])

  const handleProjectChange = (value: string) => {
    setProjectId(value)
    setTaskId('')
    setPage(1)
    setSearchParams({}, { replace: true })
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

  const clearFilters = () => {
    setProjectId('')
    setTaskId('')
    setWeekStart('')
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

  const data = plansQuery.data
  const projects = projectsQuery.data ?? []
  const tasks = tasksQuery.data?.items ?? []
  const hasFilters = Boolean(projectId || taskId || weekStart)
  const defaultTaskId = taskId ? Number(taskId) : undefined

  return (
    <div className="space-y-5">
      <PageHeader
        title="Haftalık Planlar"
        description="Her görev için haftalık hedefi, hafta aralığını ve beklenen tamamlanma yüzdesini tanımlayın."
        actions={
          <Button
            onClick={openCreate}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Yeni haftalık plan
          </Button>
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
              className="field-input w-full py-2 sm:w-48"
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
              className="field-input w-full py-2 sm:w-56"
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
              className="field-input w-full py-2 sm:w-44"
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
              description="Seçili proje, görev veya hafta için tanımlanmış bir plan yok. Filtreleri değiştirin ya da bu görev için yeni bir plan oluşturun."
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
              description="Haftalık planlar bir göreve bağlıdır. İlk planı oluşturarak haftanın hedefini ve beklenen tamamlanma yüzdesini belirleyin."
              action={
                <Button
                  onClick={openCreate}
                  leftIcon={<Plus className="h-4 w-4" />}
                >
                  İlk planı oluştur
                </Button>
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
                  <th scope="col">Güncelleme</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((plan) => (
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
                      <span className="inline-flex items-center gap-1.5 text-slate-600">
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
                    </td>
                    <td>
                      <div className="flex min-w-32 flex-col gap-1.5">
                        <Badge tone={completionTone(plan.target_completion_percentage)}>
                          {plan.target_completion_percentage === null
                            ? 'Belirtilmedi'
                            : `%${plan.target_completion_percentage}`}
                        </Badge>
                        {plan.target_completion_percentage !== null ? (
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
                    <td className="text-xs text-slate-500">
                      {formatDateTime(plan.updated_at)}
                    </td>
                    <td>
                      <div className="flex justify-end">
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
                      </div>
                    </td>
                  </tr>
                ))}
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
        <Target
          className="mt-0.5 h-4 w-4 shrink-0 text-slate-400"
          aria-hidden="true"
        />
        <p className="text-xs leading-5 text-slate-500">
          Haftalık planlar görevin genel planlanan başlangıç ve bitiş
          tarihlerinden ayrıdır. Bu sayfadaki yüzdeler hedeflenen
          tamamlanmayı gösterir; gerçek iş ilerlemesi raporlanana kadar
          performans sonucu olarak yorumlanmamalıdır.
        </p>
      </div>

      <WeeklyPlanFormDialog
        open={formOpen}
        onClose={closeForm}
        plan={editingPlan}
        defaultTaskId={defaultTaskId}
      />
    </div>
  )
}
