import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BellRing,
  ClipboardCheck,
  ShieldCheck,
} from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link } from 'react-router-dom'

import { registrationRequestsApi } from '../api/endpoints'
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
import { SearchInput } from '../components/ui/SearchInput'
import { useToast } from '../components/ui/Toast'
import {
  formatDateTime,
  getErrorMessage,
  pluralize,
  registrationStatusMeta,
} from '../lib/utils'
import type {
  RegistrationRequest,
  RegistrationStatus,
} from '../types'

const PAGE_SIZE = 15

const statusFilters: Array<{
  value: RegistrationStatus | ''
  label: string
}> = [
  { value: '', label: 'Tümü' },
  { value: 'pending', label: 'Bekleyen' },
  { value: 'approved', label: 'Onaylanan' },
  { value: 'rejected', label: 'Reddedilen' },
]

export function RegistrationRequestsPage() {
  const [status, setStatus] = useState<RegistrationStatus | ''>('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [page, setPage] = useState(1)
  const [deletingRequest, setDeletingRequest] =
    useState<RegistrationRequest | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const requestsQuery = useQuery({
    queryKey: [
      'registration-requests',
      'list',
      page,
      status,
      deferredSearch,
    ],
    queryFn: () =>
      registrationRequestsApi.list({
        page,
        page_size: PAGE_SIZE,
        status: status || undefined,
        search: deferredSearch.trim() || undefined,
      }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => registrationRequestsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['registration-requests'],
      })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      setDeletingRequest(null)
      showToast('Kayıt talebi silindi.', 'success')
    },
    onError: (error) => {
      setDeletingRequest(null)
      showToast(getErrorMessage(error), 'error')
    },
  })

  const data = requestsQuery.data
  const hasFilters =
    status !== '' || deferredSearch.trim().length > 0

  const changeStatus = (value: RegistrationStatus | '') => {
    setStatus(value)
    setPage(1)
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Kayıt Talepleri"
        description="Telegram üzerinden gelen çalışan kayıt başvurularını ve yönetici kararlarını görüntüleyin."
      />

      <Alert tone="info" title="Karar yetkisi Telegram'da">
        <p>
          Kayıt talepleri Telegram <code>/register</code> akışıyla
          oluşturulur. Onay ve reddetme işlemleri, bildirim mesajındaki
          düğmelerle yapılandırılmış Telegram yöneticisi tarafından
          verilir. Bu panel kararları gösterir; yönetici geçmiş talepleri
          silebilir. Talep silmek, onaylanmış olsa bile çalışan kaydını
          silmez.
        </p>
      </Alert>

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div
            className="flex flex-wrap gap-1 rounded-lg border border-worktrack-line bg-white p-1"
            role="group"
            aria-label="Duruma göre filtrele"
          >
            {statusFilters.map((filter) => {
              const isActive = status === filter.value

              return (
                <button
                  key={filter.value || 'all'}
                  type="button"
                  onClick={() => changeStatus(filter.value)}
                  aria-pressed={isActive}
                  className={
                    isActive
                      ? 'rounded-md bg-worktrack-navy px-3 py-1.5 text-xs font-semibold text-white'
                      : 'rounded-md px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 hover:text-worktrack-ink'
                  }
                >
                  {filter.label}
                </button>
              )
            })}
          </div>

          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value)
              setPage(1)
            }}
            placeholder="Talep eden adı ara"
          />
        </div>

        {data ? (
          <p className="text-sm text-slate-500">
            {pluralize(data.total, 'kayıt talebi', 'kayıt talebi')}
          </p>
        ) : null}
      </div>

      {requestsQuery.isLoading ? (
        <LoadingState rows={6} />
      ) : requestsQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(requestsQuery.error)}
            onRetry={() => void requestsQuery.refetch()}
          />
        </Card>
      ) : data && data.items.length === 0 ? (
        <Card>
          {hasFilters ? (
            <EmptyState
              icon={ClipboardCheck}
              title="Eşleşen kayıt talebi bulunamadı"
              description="Seçili durum veya arama kriterine uyan bir talep yok. Filtreleri temizleyerek tüm talepleri görebilirsiniz."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setStatus('')
                    setSearch('')
                    setPage(1)
                  }}
                >
                  Filtreleri temizle
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={ClipboardCheck}
              title="Kayıt talebi yok"
              description="Telegram botuna /register komutuyla başvuran çalışanlar burada listelenir. Yeni bir başvuru geldiğinde durum bilgisiyle birlikte görünür."
            />
          )}
        </Card>
      ) : data ? (
        <>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Talep Eden</th>
                  <th scope="col">Telegram ID</th>
                  <th scope="col">Talep Tarihi</th>
                  <th scope="col">Bildirim</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Bağlı Çalışan</th>
                  <th scope="col">Yönetici Kararı</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((request) => {
                  const meta = registrationStatusMeta[request.status]

                  return (
                    <tr key={request.id}>
                      <td>
                        <p className="font-medium text-worktrack-ink">
                          {request.requested_full_name}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          Pozisyon: {request.requested_role ?? 'Belirtilmedi'}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-400">
                          Talep #{request.id}
                        </p>
                      </td>
                      <td className="font-mono text-xs text-slate-600">
                        {request.telegram_user_id}
                      </td>
                      <td className="text-slate-600">
                        {formatDateTime(request.created_at)}
                      </td>
                      <td>
                        {request.notification_sent_at ? (
                          <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
                            <BellRing
                              className="h-3.5 w-3.5 text-emerald-500"
                              aria-hidden="true"
                            />
                            {formatDateTime(request.notification_sent_at)}
                          </span>
                        ) : (
                          <span className="text-xs text-slate-400">
                            Gönderilmedi
                          </span>
                        )}
                      </td>
                      <td>
                        <Badge tone={meta?.tone ?? 'neutral'}>
                          {meta?.label ?? request.status}
                        </Badge>
                      </td>
                      <td>
                        {request.employee_id ? (
                          <Link
                            to={`/calisanlar/${request.employee_id}`}
                            className="text-slate-700 hover:text-worktrack-blue hover:underline"
                          >
                            {request.employee_full_name ??
                              `Çalışan #${request.employee_id}`}
                          </Link>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td>
                        {request.reviewed_at ? (
                          <div className="text-xs">
                            <p className="text-slate-600">
                              {formatDateTime(request.reviewed_at)}
                            </p>
                            {request.reviewed_by_telegram_user_id ? (
                              <p className="mt-0.5 text-slate-400">
                                Telegram:{' '}
                                {request.reviewed_by_telegram_user_id}
                              </p>
                            ) : null}
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                            <ShieldCheck
                              className="h-3.5 w-3.5"
                              aria-hidden="true"
                            />
                            Bekliyor
                          </span>
                        )}
                      </td>
                      <td>
                        <div className="flex justify-end">
                          <DeleteButton
                            label={`${request.requested_full_name} kayıt talebini sil`}
                            onClick={() => setDeletingRequest(request)}
                            disabled={deleteMutation.isPending}
                            isDeleting={
                              deleteMutation.isPending &&
                              deleteMutation.variables === request.id
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

      <ConfirmDialog
        open={deletingRequest !== null}
        title="Kayıt talebini sil"
        description={
          <>
            <p>
              <strong className="text-worktrack-ink">
                {deletingRequest?.requested_full_name}
              </strong>{' '}
              adına ait kayıt talebini silmek istediğinizden emin misiniz?
            </p>
            <p>
              Bu işlem geri alınamaz. Yalnızca seçili kayıt talebi silinir;
              onaylanmış talep silinse bile ilgili çalışan kaydı korunur.
            </p>
          </>
        }
        confirmLabel="Kayıt talebini sil"
        tone="danger"
        isLoading={deleteMutation.isPending}
        onConfirm={() => {
          if (deletingRequest && !deleteMutation.isPending) {
            deleteMutation.mutate(deletingRequest.id)
          }
        }}
        onClose={() => {
          if (!deleteMutation.isPending) {
            setDeletingRequest(null)
          }
        }}
      />
    </div>
  )
}
