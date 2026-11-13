import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Users } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link } from 'react-router-dom'

import { employeesApi } from '../api/endpoints'
import { Avatar } from '../components/ui/Avatar'
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
import { SearchInput } from '../components/ui/SearchInput'
import { useToast } from '../components/ui/Toast'
import { formatDate, getErrorMessage } from '../lib/utils'
import type { Employee } from '../types'

type ActiveFilter = 'all' | 'active' | 'inactive'

const PAGE_SIZE = 15

export function EmployeesPage() {
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [filter, setFilter] = useState<ActiveFilter>('all')
  const [page, setPage] = useState(1)
  const [deletingEmployee, setDeletingEmployee] =
    useState<Employee | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const employeesQuery = useQuery({
    queryKey: ['employees', 'list', page, deferredSearch, filter],
    queryFn: () =>
      employeesApi.list({
        page,
        page_size: PAGE_SIZE,
        search: deferredSearch.trim() || undefined,
        is_active:
          filter === 'all' ? undefined : filter === 'active',
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => employeesApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['employees'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['weekly-plans'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setDeletingEmployee(null)
      showToast('Çalışan silindi.', 'success')
    },
    onError: (error) => {
      setDeletingEmployee(null)
      showToast(getErrorMessage(error), 'error')
    },
  })

  const data = employeesQuery.data

  return (
    <div className="space-y-5">
      <PageHeader
        title="Çalışanlar"
        description="Telegram kayıt talebi onaylanan çalışanlar. Durum ve görev atamalarını görüntüleyin."
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            placeholder="Ad soyad veya rol ara"
          />
          <div className="flex items-center gap-2">
            <label
              htmlFor="employee-status-filter"
              className="text-sm text-slate-500"
            >
              Durum
            </label>
            <select
              id="employee-status-filter"
              value={filter}
              onChange={(event) => {
                setFilter(event.target.value as ActiveFilter)
                setPage(1)
              }}
              className="field-input w-auto min-w-32 py-2"
            >
              <option value="all">Tümü</option>
              <option value="active">Aktif</option>
              <option value="inactive">Pasif</option>
            </select>
          </div>
        </div>
        {data ? (
          <p className="text-sm text-slate-500">
            {data.total} çalışan
          </p>
        ) : null}
      </div>

      {employeesQuery.isLoading ? (
        <LoadingState rows={6} />
      ) : employeesQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(employeesQuery.error)}
            onRetry={() => void employeesQuery.refetch()}
          />
        </Card>
      ) : data && data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={Users}
            title={
              search || filter !== 'all'
                ? 'Eşleşen çalışan bulunamadı'
                : 'Henüz çalışan yok'
            }
            description={
              search || filter !== 'all'
                ? 'Arama veya durum filtresini değiştirerek tekrar deneyin.'
                : 'Çalışanlar Telegram botunda /register komutuyla talep oluşturur. Yönetici onayından sonra aktif çalışan olarak burada görünür.'
            }
            action={
              search || filter !== 'all' ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch('')
                    setFilter('all')
                    setPage(1)
                  }}
                >
                  Filtreleri temizle
                </Button>
              ) : (
                <Link to="/kayit-talepleri">
                  <Button variant="secondary">
                    Kayıt taleplerini görüntüle
                  </Button>
                </Link>
              )
            }
          />
        </Card>
      ) : data ? (
        <>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Çalışan</th>
                  <th scope="col">Telegram ID</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Görev</th>
                  <th scope="col">Proje</th>
                  <th scope="col">Kayıt Tarihi</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((employee) => (
                  <tr key={employee.id}>
                    <td>
                      <div className="flex items-center gap-3">
                        <Avatar name={employee.full_name} />
                        <div className="min-w-0">
                          <Link
                            to={`/calisanlar/${employee.id}`}
                            className="font-medium text-worktrack-ink hover:text-worktrack-blue hover:underline"
                          >
                            {employee.full_name}
                          </Link>
                          <p className="text-xs text-slate-500">
                            {employee.role ?? 'Rol belirtilmedi'}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="text-slate-500">
                      {employee.telegram_user_id ?? 'Kayıtlı değil'}
                    </td>
                    <td>
                      <Badge
                        tone={
                          employee.is_active ? 'success' : 'neutral'
                        }
                      >
                        {employee.is_active ? 'Aktif' : 'Pasif'}
                      </Badge>
                    </td>
                    <td>{employee.task_count}</td>
                    <td>{employee.project_count}</td>
                    <td className="text-slate-500">
                      {formatDate(employee.created_at)}
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          to={`/calisanlar/${employee.id}`}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-worktrack-blue"
                          aria-label={`${employee.full_name} detayını aç`}
                          title="Detay"
                        >
                          <ArrowRight
                            className="h-4 w-4"
                            aria-hidden="true"
                          />
                        </Link>
                        <DeleteButton
                          label={`${employee.full_name} çalışanını sil`}
                          onClick={() => setDeletingEmployee(employee)}
                          disabled={deleteMutation.isPending}
                          isDeleting={
                            deleteMutation.isPending &&
                            deleteMutation.variables === employee.id
                          }
                        />
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

      <ConfirmDialog
        open={deletingEmployee !== null}
        title="Çalışanı sil"
        description={
          <>
            <p>
              <strong className="text-worktrack-ink">
                {deletingEmployee?.full_name}
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
          if (deletingEmployee && !deleteMutation.isPending) {
            deleteMutation.mutate(deletingEmployee.id)
          }
        }}
        onClose={() => {
          if (!deleteMutation.isPending) {
            setDeletingEmployee(null)
          }
        }}
      />
    </div>
  )
}
