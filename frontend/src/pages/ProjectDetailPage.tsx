import { useQuery } from '@tanstack/react-query'
import {
  ArrowLeft,
  CalendarDays,
  ListChecks,
  MapPin,
  Pencil,
  Plus,
  Users,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { projectsApi } from '../api/endpoints'
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog'
import { Avatar, AvatarGroup } from '../components/ui/Avatar'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import {
  formatDate,
  formatDateTime,
  getErrorMessage,
} from '../lib/utils'

export function ProjectDetailPage() {
  const { projectId } = useParams()
  const id = Number(projectId)
  const [editOpen, setEditOpen] = useState(false)

  const projectQuery = useQuery({
    queryKey: ['projects', 'detail', id],
    queryFn: () => projectsApi.get(id),
    enabled: Number.isFinite(id) && id > 0,
  })

  if (!Number.isFinite(id) || id <= 0) {
    return (
      <Card>
        <ErrorState
          title="Geçersiz proje"
          message="Proje numarası geçerli değil."
        />
      </Card>
    )
  }

  if (projectQuery.isLoading) {
    return <LoadingState variant="detail" />
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <div className="space-y-4">
        <Link
          to="/projeler"
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-worktrack-ink"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Projelere dön
        </Link>
        <Card>
          <ErrorState
            message={getErrorMessage(projectQuery.error)}
            onRetry={() => void projectQuery.refetch()}
          />
        </Card>
      </div>
    )
  }

  const project = projectQuery.data

  return (
    <div className="space-y-5">
      <Link
        to="/projeler"
        className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-worktrack-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Projelere dön
      </Link>

      <PageHeader
        eyebrow="Proje Detayı"
        title={project.name}
        description={
          project.description ??
          'Bu proje için henüz bir açıklama girilmedi.'
        }
        actions={
          <Button
            variant="secondary"
            onClick={() => setEditOpen(true)}
            leftIcon={<Pencil className="h-4 w-4" />}
          >
            Projeyi düzenle
          </Button>
        }
      />

      <Card className="p-5">
        <dl className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
              Konum
            </dt>
            <dd className="mt-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
              <MapPin
                className="h-4 w-4 text-slate-400"
                aria-hidden="true"
              />
              {project.location ?? 'Belirtilmedi'}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
              Beklenen Tamamlanma
            </dt>
            <dd className="mt-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
              <CalendarDays
                className="h-4 w-4 text-slate-400"
                aria-hidden="true"
              />
              {formatDate(project.expected_completion_date)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
              Oluşturma
            </dt>
            <dd className="mt-1 text-sm font-medium text-slate-700">
              {formatDateTime(project.created_at)}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
              Görev / Ekip
            </dt>
            <dd className="mt-1 text-sm font-medium text-slate-700">
              {project.task_count} görev · {project.employee_count} çalışan
            </dd>
          </div>
        </dl>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <Card>
          <CardHeader
            title="Proje Görevleri"
            description="Bu projeye bağlı görevler ve atanmış çalışanlar."
            action={
              <Link
                to={`/gorevler?proje=${project.id}&yeni=1`}
                className="inline-flex items-center gap-1 rounded-lg bg-worktrack-blue px-3 py-2 text-xs font-semibold text-white transition hover:bg-worktrack-blue-dark"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                Görev ekle
              </Link>
            }
          />

          {project.tasks.length === 0 ? (
            <EmptyState
              icon={ListChecks}
              title="Bu projede henüz görev yok"
              description="Görev ekleyerek planlanan tarihleri belirleyin ve çalışanları göreve atayın. Proje ekibi, görev atamalarından otomatik olarak türetilir."
              action={
                <Link
                  to={`/gorevler?proje=${project.id}&yeni=1`}
                >
                  <Button leftIcon={<Plus className="h-4 w-4" />}>
                    İlk görevi ekle
                  </Button>
                </Link>
              }
              compact
            />
          ) : (
            <div className="table-shell rounded-none border-0">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Görev</th>
                    <th scope="col">Planlanan Başlangıç</th>
                    <th scope="col">Planlanan Bitiş</th>
                    <th scope="col">Atanan Çalışanlar</th>
                    <th scope="col">Haftalık Plan</th>
                  </tr>
                </thead>
                <tbody>
                  {project.tasks.map((task) => (
                    <tr key={task.id}>
                      <td>
                        <Link
                          to={`/gorevler?proje=${project.id}&gorev=${task.id}`}
                          className="font-medium text-worktrack-ink hover:text-worktrack-blue hover:underline"
                        >
                          {task.title}
                        </Link>
                      </td>
                      <td>
                        <span className="text-slate-600">
                          {formatDate(task.planned_start_date)}
                        </span>
                        {task.planned_start_weekday ? (
                          <span className="ml-1.5 text-xs text-slate-400">
                            {task.planned_start_weekday}
                          </span>
                        ) : null}
                      </td>
                      <td>
                        <span className="text-slate-600">
                          {formatDate(task.planned_due_date)}
                        </span>
                        {task.planned_due_weekday ? (
                          <span className="ml-1.5 text-xs text-slate-400">
                            {task.planned_due_weekday}
                          </span>
                        ) : null}
                      </td>
                      <td>
                        <AvatarGroup
                          names={task.assigned_employees.map(
                            (employee) => employee.full_name,
                          )}
                        />
                      </td>
                      <td>{task.weekly_plan_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Proje Ekibi"
            description="Yalnızca bu projenin görevlerine atanmış çalışanlar."
          />
          {project.employees.length === 0 ? (
            <EmptyState
              icon={Users}
              title="Henüz atanmış çalışan yok"
              description="Proje ekibi, görevlere yapılan çalışan atamalarından türetilir. Doğrudan proje üyeliği tutulmaz."
              compact
            />
          ) : (
            <ul className="divide-y divide-worktrack-line">
              {project.employees.map((employee) => (
                <li key={employee.id}>
                  <Link
                    to={`/calisanlar/${employee.id}`}
                    className="flex items-center gap-3 px-5 py-3 transition hover:bg-slate-50/70"
                  >
                    <Avatar name={employee.full_name} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-worktrack-ink">
                        {employee.full_name}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {employee.role ?? 'Görev atamasıyla eklendi'}
                      </p>
                    </div>
                    <Badge
                      tone={employee.is_active ? 'success' : 'neutral'}
                    >
                      {employee.is_active ? 'Aktif' : 'Pasif'}
                    </Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-worktrack-line bg-slate-50/60 px-5 py-3">
            <p className="text-xs leading-5 text-slate-500">
              Çalışanlar projelere doğrudan bağlanmaz. Bu liste,
              <span className="font-medium text-slate-600">
                {' '}
                görev → atama → çalışan
              </span>{' '}
              zinciriyle oluşturulur.
            </p>
          </div>
        </Card>
      </div>

      <ProjectFormDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        project={project}
      />
    </div>
  )
}
