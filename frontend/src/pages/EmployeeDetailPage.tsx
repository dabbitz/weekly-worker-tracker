import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  ArrowRight,
  FolderKanban,
  ListChecks,
  UserRound,
} from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { employeesApi } from '../api/endpoints'
import { Avatar } from '../components/ui/Avatar'
import { Badge } from '../components/ui/Badge'
import { Card, CardHeader } from '../components/ui/Card'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { DeleteButton } from '../components/ui/DeleteButton'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { useToast } from '../components/ui/Toast'
import {
  formatDate,
  formatDateTime,
  getErrorMessage,
} from '../lib/utils'

export function EmployeeDetailPage() {
  const { employeeId } = useParams()
  const id = Number(employeeId)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const employeeQuery = useQuery({
    queryKey: ['employees', 'detail', id],
    queryFn: () => employeesApi.get(id),
    enabled: Number.isFinite(id) && id > 0,
  })

  const deleteMutation = useMutation({
    mutationFn: (employeeIdToDelete: number) =>
      employeesApi.remove(employeeIdToDelete),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['employees'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['weekly-plans'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setDeleteOpen(false)
      showToast('Çalışan silindi.', 'success')
      navigate('/calisanlar')
    },
    onError: (error) => {
      setDeleteOpen(false)
      showToast(getErrorMessage(error), 'error')
    },
  })

  if (!Number.isFinite(id) || id <= 0) {
    return (
      <Card>
        <ErrorState
          title="Geçersiz çalışan"
          message="Çalışan numarası geçerli değil."
        />
      </Card>
    )
  }

  if (employeeQuery.isLoading) {
    return <LoadingState variant="detail" />
  }

  if (employeeQuery.isError || !employeeQuery.data) {
    return (
      <div className="space-y-4">
        <Link
          to="/calisanlar"
          className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-worktrack-ink"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Çalışanlara dön
        </Link>
        <Card>
          <ErrorState
            message={getErrorMessage(employeeQuery.error)}
            onRetry={() => void employeeQuery.refetch()}
          />
        </Card>
      </div>
    )
  }

  const employee = employeeQuery.data
  const hasTasks = employee.assigned_tasks.length > 0

  return (
    <div className="space-y-5">
      <Link
        to="/calisanlar"
        className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-worktrack-ink"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Çalışanlara dön
      </Link>

      <PageHeader
        eyebrow="Çalışan Detayı"
        title={employee.full_name}
        description="Görev atamaları ve bu atamalar üzerinden türetilen projeler."
        actions={
          <>
            <Badge tone={employee.is_active ? 'success' : 'neutral'}>
              {employee.is_active ? 'Aktif çalışan' : 'Pasif çalışan'}
            </Badge>
            <DeleteButton
              label={`${employee.full_name} çalışanını sil`}
              onClick={() => setDeleteOpen(true)}
              disabled={deleteMutation.isPending}
              isDeleting={deleteMutation.isPending}
              className="border border-slate-300 bg-white p-2 hover:border-red-200"
            />
          </>
        }
      />

      <Card className="p-5">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <Avatar name={employee.full_name} size="lg" />
          <dl className="grid flex-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
                Rol
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-700">
                {employee.role ?? 'Belirtilmedi'}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
                Telegram ID
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-700">
                {employee.telegram_user_id ?? 'Kayıtlı değil'}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
                Kayıt Tarihi
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-700">
                {formatDateTime(employee.created_at)}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium tracking-wide text-slate-500 uppercase">
                Görev / Proje
              </dt>
              <dd className="mt-1 text-sm font-medium text-slate-700">
                {employee.task_count} görev · {employee.project_count} proje
              </dd>
            </div>
          </dl>
        </div>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <Card>
          <CardHeader
            title="Atanan Görevler"
            description="Bu çalışanın doğrudan atandığı görevler."
            action={
              <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500">
                <ListChecks className="h-4 w-4" aria-hidden="true" />
                {employee.assigned_tasks.length} görev
              </span>
            }
          />

          {!hasTasks ? (
            <EmptyState
              icon={UserRound}
              title="Henüz görev atanmamış"
              description="Bu çalışan henüz bir göreve atanmadı. Görevler sayfasından görev oluşturup çalışanı atayabilirsiniz."
              action={
                <Link to="/gorevler">
                  <span className="inline-flex items-center gap-1 text-sm font-semibold text-worktrack-blue hover:underline">
                    Görevler sayfasına git
                    <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
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
                    <th scope="col">Proje</th>
                    <th scope="col">Planlanan Başlangıç</th>
                    <th scope="col">Planlanan Bitiş</th>
                    <th scope="col">Haftalık Plan</th>
                  </tr>
                </thead>
                <tbody>
                  {employee.assigned_tasks.map((task) => (
                    <tr key={task.id}>
                      <td>
                        <Link
                          to={`/gorevler?proje=${task.project_id}&gorev=${task.id}`}
                          className="font-medium text-worktrack-ink hover:text-worktrack-blue hover:underline"
                        >
                          {task.title}
                        </Link>
                      </td>
                      <td className="text-slate-500">
                        {task.project_name}
                      </td>
                      <td>
                        {formatDate(task.planned_start_date)}
                        {task.planned_start_weekday ? (
                          <span className="ml-1.5 text-xs text-slate-400">
                            {task.planned_start_weekday}
                          </span>
                        ) : null}
                      </td>
                      <td>
                        {formatDate(task.planned_due_date)}
                        {task.planned_due_weekday ? (
                          <span className="ml-1.5 text-xs text-slate-400">
                            {task.planned_due_weekday}
                          </span>
                        ) : null}
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
            title="İlişkili Projeler"
            description="Görev atamaları üzerinden türetilen projeler."
          />
          {employee.projects.length === 0 ? (
            <EmptyState
              icon={FolderKanban}
              title="Proje ilişkisi yok"
              description="Çalışanın atanmış görevi olmadığı için herhangi bir projeyle ilişkilendirilmemiştir."
              compact
            />
          ) : (
            <ul className="divide-y divide-worktrack-line">
              {employee.projects.map((project) => (
                <li key={project.id}>
                  <Link
                    to={`/projeler/${project.id}`}
                    className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-slate-50/70"
                  >
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-worktrack-navy/5 text-worktrack-navy">
                      <FolderKanban
                        className="h-4 w-4"
                        aria-hidden="true"
                      />
                    </span>
                    <span className="min-w-0 flex-1 text-sm font-medium text-worktrack-ink">
                      {project.name}
                    </span>
                    <ArrowRight
                      className="h-4 w-4 text-slate-300"
                      aria-hidden="true"
                    />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <div className="border-t border-worktrack-line bg-slate-50/60 px-5 py-3">
            <p className="text-xs leading-5 text-slate-500">
              Doğrudan çalışan-proje üyeliği tutulmaz. İlişki yalnızca
              görev atamalarından hesaplanır.
            </p>
          </div>
        </Card>
      </div>
      <ConfirmDialog
        open={deleteOpen}
        title="Çalışanı sil"
        description={
          <>
            <p>
              <strong className="text-worktrack-ink">
                {employee.full_name}
              </strong>{' '}
              adlı çalışanı silmek istediğinizden emin misiniz?
            </p>
            <p>
              Bu işlem geri alınamaz. Çalışanın görev atamaları kaldırılır.
              Çalışana bağlı iş raporu varsa silme engellenir. Onaylı kayıt
              talebi silinmez; çalışan kaydı korunur.
            </p>
          </>
        }
        confirmLabel="Çalışanı sil"
        tone="danger"
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (!deleteMutation.isPending) {
            deleteMutation.mutate(employee.id)
          }
        }}
        onClose={() => {
          if (!deleteMutation.isPending) {
            setDeleteOpen(false)
          }
        }}
      />
    </div>
  )
}
