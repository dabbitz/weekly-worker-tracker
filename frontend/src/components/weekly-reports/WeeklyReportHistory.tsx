import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Eye,
  FileClock,
  RotateCcw,
  Sparkles,
  Trash2,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { weeklyReportsApi } from '../../api/endpoints'
import {
  formatDateTime,
  formatWeekRange,
  getErrorMessage,
} from '../../lib/utils'
import type {
  WeeklyReportListItem,
  WeeklyReportStatus,
} from '../../types'
import { Alert } from '../ui/Alert'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card, CardHeader } from '../ui/Card'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { LoadingState } from '../ui/LoadingState'
import { Pagination } from '../ui/Pagination'
import { useToast } from '../ui/Toast'

interface WeeklyReportHistoryProps {
  onGenerate: () => void
}

const statusMeta: Record<
  WeeklyReportStatus,
  { label: string; tone: 'warning' | 'success' | 'danger' }
> = {
  pending: { label: 'Hazırlanıyor', tone: 'warning' },
  completed: { label: 'Tamamlandı', tone: 'success' },
  failed: { label: 'Oluşturulamadı', tone: 'danger' },
}

export function WeeklyReportHistory({
  onGenerate,
}: WeeklyReportHistoryProps) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState<WeeklyReportStatus | ''>('')
  const [pendingDelete, setPendingDelete] =
    useState<WeeklyReportListItem | null>(null)

  const listQuery = useQuery({
    queryKey: ['weekly-reports', page, status],
    queryFn: () =>
      weeklyReportsApi.list({
        page,
        page_size: 10,
        status: status === '' ? undefined : status,
      }),
  })

  const retryMutation = useMutation({
    mutationFn: (reportId: number) =>
      weeklyReportsApi.retry(reportId),
    onSuccess: () => {
      showToast('Rapor yeniden oluşturuldu.', 'success')
      void queryClient.invalidateQueries({
        queryKey: ['weekly-reports'],
      })
    },
    onError: (error) => {
      showToast(getErrorMessage(error), 'error')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (reportId: number) =>
      weeklyReportsApi.remove(reportId),
    onSuccess: () => {
      showToast('Rapor belgesi silindi.', 'success')
      setPendingDelete(null)
      void queryClient.invalidateQueries({
        queryKey: ['weekly-reports'],
      })
    },
    onError: (error) => {
      showToast(getErrorMessage(error), 'error')
    },
  })

  const data = listQuery.data

  return (
    <Card>
      <CardHeader
        title="Haftalık yönetici raporları"
        description="Her sürüm saklanır. Yeni bir rapor eski sürümleri silmez."
        action={
          <div className="flex flex-wrap items-center gap-2">
            <label
              htmlFor="weekly-report-status"
              className="sr-only"
            >
              Duruma göre filtrele
            </label>
            <select
              id="weekly-report-status"
              className="field-input h-9 w-auto cursor-pointer py-1 text-sm"
              value={status}
              onChange={(event) => {
                setStatus(
                  event.target.value as WeeklyReportStatus | '',
                )
                setPage(1)
              }}
            >
              <option value="">Tüm durumlar</option>
              <option value="completed">Tamamlandı</option>
              <option value="pending">Hazırlanıyor</option>
              <option value="failed">Oluşturulamadı</option>
            </select>
            <Button
              size="sm"
              onClick={onGenerate}
              leftIcon={<Sparkles className="h-4 w-4" />}
            >
              Rapor Oluştur
            </Button>
          </div>
        }
      />

      {listQuery.isLoading ? (
        <LoadingState />
      ) : listQuery.isError ? (
        <ErrorState
          message={getErrorMessage(listQuery.error)}
          onRetry={() => void listQuery.refetch()}
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={FileClock}
          title="Henüz haftalık yönetici raporu yok"
          description="Bir hafta seçip yönetici raporu oluşturduğunuzda sürümler burada listelenir. Raporlar yalnızca sizin başlattığınız üretimle oluşur."
          action={
            <Button
              onClick={onGenerate}
              leftIcon={<Sparkles className="h-4 w-4" />}
            >
              İlk raporu oluştur
            </Button>
          }
        />
      ) : (
        <>
          {retryMutation.isError ? (
            <div className="px-5 pt-4">
              <Alert tone="error" title="Yeniden deneme başarısız">
                {getErrorMessage(retryMutation.error)}
              </Alert>
            </div>
          ) : null}

          <div className="table-shell rounded-none border-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Hafta</th>
                  <th scope="col">Sürüm</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Kapsam</th>
                  <th scope="col">Oluşturulma</th>
                  <th scope="col">Model</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((report) => {
                  const meta = statusMeta[report.status]

                  return (
                    <tr key={report.id}>
                      <td className="whitespace-nowrap">
                        <Link
                          to={`/raporlar/haftalik/${report.id}`}
                          className="font-medium text-worktrack-ink hover:text-worktrack-blue-dark hover:underline"
                        >
                          {formatWeekRange(
                            report.week_start_date,
                            report.week_end_date,
                          )}
                        </Link>
                        {report.is_partial_week ? (
                          <Badge
                            tone="warning"
                            className="ml-2 align-middle"
                          >
                            Kısmi
                          </Badge>
                        ) : null}
                      </td>
                      <td className="whitespace-nowrap text-slate-600">
                        v{report.version}
                      </td>
                      <td>
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </td>
                      <td className="text-xs whitespace-nowrap text-slate-500">
                        {report.project_count} proje ·{' '}
                        {report.task_count} görev ·{' '}
                        {report.report_count} rapor
                      </td>
                      <td className="text-xs whitespace-nowrap text-slate-500">
                        {formatDateTime(report.created_at)}
                      </td>
                      <td className="max-w-40 truncate text-xs text-slate-500">
                        {report.model ?? '—'}
                      </td>
                      <td>
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            to={`/raporlar/haftalik/${report.id}`}
                            className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-100 hover:text-worktrack-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-worktrack-blue"
                            aria-label={`${report.version}. sürümü görüntüle`}
                          >
                            <Eye
                              className="h-3.5 w-3.5"
                              aria-hidden="true"
                            />
                            Görüntüle
                          </Link>
                          {report.status === 'failed' ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              leftIcon={
                                <RotateCcw className="h-3.5 w-3.5" />
                              }
                              isLoading={
                                retryMutation.isPending &&
                                retryMutation.variables === report.id
                              }
                              onClick={() =>
                                retryMutation.mutate(report.id)
                              }
                            >
                              Yeniden dene
                            </Button>
                          ) : null}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-red-600 hover:bg-red-50 hover:text-red-700"
                            leftIcon={
                              <Trash2 className="h-3.5 w-3.5" />
                            }
                            disabled={report.status === 'pending'}
                            title={
                              report.status === 'pending'
                                ? 'Hazırlanmakta olan rapor silinemez.'
                                : 'Rapor belgesini sil'
                            }
                            onClick={() => setPendingDelete(report)}
                          >
                            Sil
                          </Button>
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
            disabled={listQuery.isFetching}
          />
        </>
      )}

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Rapor belgesini sil"
        tone="danger"
        confirmLabel="Raporu sil"
        isLoading={deleteMutation.isPending}
        onClose={() => {
          if (!deleteMutation.isPending) {
            setPendingDelete(null)
          }
        }}
        onConfirm={() => {
          if (pendingDelete) {
            deleteMutation.mutate(pendingDelete.id)
          }
        }}
        description={
          pendingDelete ? (
            <>
              <p>
                <span className="font-semibold text-worktrack-ink">
                  {formatWeekRange(
                    pendingDelete.week_start_date,
                    pendingDelete.week_end_date,
                  )}{' '}
                  · v{pendingDelete.version}
                </span>{' '}
                raporu silinecek.
              </p>
              <p>
                Yalnızca bu rapor belgesi silinir. Görevler, çalışanlar,
                haftalık planlar ve çalışan iş raporları korunur. Bu
                işlem geri alınamaz.
              </p>
            </>
          ) : null
        }
      />
    </Card>
  )
}
