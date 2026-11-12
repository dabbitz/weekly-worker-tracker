import { useQuery } from '@tanstack/react-query'
import {
  CalendarDays,
  ListChecks,
  Pencil,
  Plus,
} from 'lucide-react'
import {
  useDeferredValue,
  useEffect,
  useState,
} from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  employeesApi,
  projectsApi,
  tasksApi,
} from '../api/endpoints'
import { TaskFormDialog } from '../components/tasks/TaskFormDialog'
import { AvatarGroup } from '../components/ui/Avatar'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { SearchInput } from '../components/ui/SearchInput'
import { useToast } from '../components/ui/Toast'
import { formatDate, getErrorMessage } from '../lib/utils'
import type { Task } from '../types'

const PAGE_SIZE = 15

export function TasksPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const projectParam = searchParams.get('proje')
  const taskParam = searchParams.get('gorev')
  const [projectId, setProjectId] = useState(projectParam ?? '')
  const [employeeId, setEmployeeId] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [editingTask, setEditingTask] = useState<Task | null>(null)
  const { showToast } = useToast()

  const projectsQuery = useQuery({
    queryKey: ['projects', 'options'],
    queryFn: projectsApi.options,
  })

  const employeesQuery = useQuery({
    queryKey: ['employees', 'list', 'filter-options'],
    queryFn: () =>
      employeesApi.list({ page: 1, page_size: 100, is_active: true }),
  })

  const tasksQuery = useQuery({
    queryKey: [
      'tasks',
      'list',
      page,
      projectId,
      employeeId,
      deferredSearch,
    ],
    queryFn: () =>
      tasksApi.list({
        page,
        page_size: PAGE_SIZE,
        project_id: projectId ? Number(projectId) : undefined,
        employee_id: employeeId ? Number(employeeId) : undefined,
        search: deferredSearch.trim() || undefined,
      }),
  })

  useEffect(() => {
    setProjectId(projectParam ?? '')
    setPage(1)
  }, [projectParam])

  useEffect(() => {
    if (searchParams.get('yeni') === '1') {
      setEditingTask(null)
      setFormOpen(true)
    }
  }, [searchParams])

  useEffect(() => {
    if (!taskParam) {
      return
    }

    const numericId = Number(taskParam)

    if (!Number.isFinite(numericId) || numericId <= 0) {
      return
    }

    let cancelled = false

    tasksApi
      .get(numericId)
      .then((task) => {
        if (!cancelled) {
          setEditingTask(task)
          setFormOpen(true)
        }
      })
      .catch((error) => {
        if (!cancelled) {
          showToast(getErrorMessage(error), 'error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [taskParam, showToast])

  const handleProjectChange = (value: string) => {
    setProjectId(value)
    setPage(1)

    const next = new URLSearchParams(searchParams)
    if (value) {
      next.set('proje', value)
    } else {
      next.delete('proje')
    }
    setSearchParams(next, { replace: true })
  }

  const openCreate = () => {
    setEditingTask(null)
    setFormOpen(true)
  }

  const openEdit = (task: Task) => {
    setEditingTask(task)
    setFormOpen(true)
  }

  const closeForm = () => {
    setFormOpen(false)
    setEditingTask(null)

    if (searchParams.has('yeni') || searchParams.has('gorev')) {
      const next = new URLSearchParams(searchParams)
      next.delete('yeni')
      next.delete('gorev')
      setSearchParams(next, { replace: true })
    }
  }

  const data = tasksQuery.data
  const hasFilters =
    Boolean(projectId) ||
    Boolean(employeeId) ||
    deferredSearch.trim().length > 0

  const projects = projectsQuery.data ?? []
  const employees = employeesQuery.data?.items ?? []

  return (
    <div className="space-y-5">
      <PageHeader
        title="Görevler"
        description="Projelere bağlı görevleri oluşturun, planlanan tarihleri belirleyin ve birden fazla çalışan atayın."
        actions={
          <Button
            onClick={openCreate}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Yeni görev
          </Button>
        }
      />

      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            placeholder="Görev veya proje ara"
          />

          <div className="flex items-center gap-2">
            <label
              htmlFor="task-project-filter"
              className="text-sm text-slate-500"
            >
              Proje
            </label>
            <select
              id="task-project-filter"
              value={projectId}
              onChange={(event) =>
                handleProjectChange(event.target.value)
              }
              className="field-input w-auto min-w-40 py-2"
            >
              <option value="">Tüm projeler</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <label
              htmlFor="task-employee-filter"
              className="text-sm text-slate-500"
            >
              Çalışan
            </label>
            <select
              id="task-employee-filter"
              value={employeeId}
              onChange={(event) => {
                setEmployeeId(event.target.value)
                setPage(1)
              }}
              className="field-input w-auto min-w-40 py-2"
            >
              <option value="">Tüm çalışanlar</option>
              {employees.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.full_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {data ? (
          <p className="text-sm text-slate-500">{data.total} görev</p>
        ) : null}
      </div>

      {hasFilters ? (
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span>Aktif filtreler:</span>
          {projectId ? (
            <span className="rounded-full bg-slate-200/70 px-2.5 py-1 font-medium text-slate-600">
              Proje
            </span>
          ) : null}
          {employeeId ? (
            <span className="rounded-full bg-slate-200/70 px-2.5 py-1 font-medium text-slate-600">
              Çalışan
            </span>
          ) : null}
          {deferredSearch.trim() ? (
            <span className="rounded-full bg-slate-200/70 px-2.5 py-1 font-medium text-slate-600">
              “{deferredSearch.trim()}”
            </span>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setSearch('')
              setEmployeeId('')
              handleProjectChange('')
            }}
            className="font-semibold text-worktrack-blue hover:underline"
          >
            Temizle
          </button>
        </div>
      ) : null}

      {tasksQuery.isLoading ? (
        <LoadingState rows={6} />
      ) : tasksQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(tasksQuery.error)}
            onRetry={() => void tasksQuery.refetch()}
          />
        </Card>
      ) : data && data.items.length === 0 ? (
        <Card>
          {hasFilters ? (
            <EmptyState
              icon={ListChecks}
              title="Eşleşen görev bulunamadı"
              description="Proje, çalışan veya arama filtresini değiştirerek tekrar deneyin."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch('')
                    setEmployeeId('')
                    handleProjectChange('')
                  }}
                >
                  Filtreleri temizle
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={ListChecks}
              title="Henüz görev yok"
              description="Görevler bir projeye bağlıdır. İlk görevi oluşturarak planlanan tarihleri ve çalışan atamalarını belirleyin."
              action={
                <Button
                  onClick={openCreate}
                  leftIcon={<Plus className="h-4 w-4" />}
                >
                  İlk görevi oluştur
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
                  <th scope="col">Planlanan Başlangıç</th>
                  <th scope="col">Planlanan Bitiş</th>
                  <th scope="col">Atanan Çalışanlar</th>
                  <th scope="col">Haftalık Plan</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((task) => (
                  <tr key={task.id}>
                    <td>
                      <div className="min-w-0">
                        <p className="font-medium text-worktrack-ink">
                          {task.title}
                        </p>
                        <Link
                          to={`/projeler/${task.project_id}`}
                          className="text-xs text-slate-500 hover:text-worktrack-blue hover:underline"
                        >
                          {task.project_name}
                        </Link>
                      </div>
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1 text-slate-600">
                        <CalendarDays
                          className="h-3.5 w-3.5 text-slate-400"
                          aria-hidden="true"
                        />
                        {formatDate(task.planned_start_date)}
                      </span>
                      {task.planned_start_weekday ? (
                        <p className="mt-0.5 text-xs text-slate-400">
                          {task.planned_start_weekday}
                        </p>
                      ) : null}
                    </td>
                    <td>
                      <span className="text-slate-600">
                        {formatDate(task.planned_due_date)}
                      </span>
                      {task.planned_due_weekday ? (
                        <p className="mt-0.5 text-xs text-slate-400">
                          {task.planned_due_weekday}
                        </p>
                      ) : null}
                    </td>
                    <td>
                      <AvatarGroup
                        names={task.assigned_employees.map(
                          (employee) => employee.full_name,
                        )}
                      />
                    </td>
                    <td>
                      <Link
                        to={`/haftalik-planlar?gorev=${task.id}`}
                        className="text-slate-600 hover:text-worktrack-blue hover:underline"
                      >
                        {task.weekly_plan_count} plan
                      </Link>
                    </td>
                    <td>
                      <div className="flex justify-end">
                        <button
                          type="button"
                          onClick={() => openEdit(task)}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                          aria-label={`${task.title} görevini düzenle`}
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

      <p className="text-xs text-slate-400">
        Planlanan tarihlerin haftanın günü değerleri PostgreSQL
        tarafından otomatik üretilir; bu alanlar yalnızca görüntülenir.
      </p>

      <TaskFormDialog
        open={formOpen}
        onClose={closeForm}
        task={editingTask}
        defaultProjectId={
          projectId ? Number(projectId) : undefined
        }
      />
    </div>
  )
}
