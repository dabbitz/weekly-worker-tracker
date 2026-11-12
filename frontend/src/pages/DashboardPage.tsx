import {
  ArrowRight,
  CheckCircle2,
  Circle,
  ClipboardCheck,
  FolderKanban,
  ListChecks,
  Plus,
  Users,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'

import { dashboardApi } from '../api/endpoints'
import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Card, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { StatCard } from '../components/ui/StatCard'
import {
  formatDate,
  getErrorMessage,
  pluralize,
} from '../lib/utils'

interface StepProps {
  done: boolean
  title: string
  description: string
  to: string
  actionLabel: string
}

function StartStep({
  done,
  title,
  description,
  to,
  actionLabel,
}: StepProps) {
  return (
    <div className="flex gap-3 px-5 py-3.5">
      <div className="mt-0.5">
        {done ? (
          <CheckCircle2
            className="h-5 w-5 text-emerald-500"
            aria-label="Tamamlandı"
          />
        ) : (
          <Circle
            className="h-5 w-5 text-slate-300"
            aria-label="Bekliyor"
          />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-worktrack-ink">{title}</p>
        <p className="mt-0.5 text-xs text-slate-500">{description}</p>
      </div>
      {!done ? (
        <Link
          to={to}
          className="shrink-0 self-center text-xs font-semibold text-worktrack-blue hover:underline"
        >
          {actionLabel}
        </Link>
      ) : null}
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const summaryQuery = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: dashboardApi.summary,
  })

  const summary = summaryQuery.data
  const isLoading = summaryQuery.isLoading

  return (
    <div className="space-y-6">
      <PageHeader
        title="Genel Bakış"
        description="Haftalık iş takibinin güncel durumu. Tüm sayılar veritabanındaki gerçek kayıtlardan gelir."
        actions={
          <Button
            leftIcon={<Plus className="h-4 w-4" />}
            onClick={() => navigate('/projeler?yeni=1')}
          >
            Yeni proje
          </Button>
        }
      />

      {summaryQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(summaryQuery.error)}
            onRetry={() => void summaryQuery.refetch()}
            compact
          />
        </Card>
      ) : null}

      {summary?.pending_registration_count ? (
        <Alert tone="warning" title="Bekleyen kayıt talebi var">
          <p>
            {pluralize(
              summary.pending_registration_count,
              'Telegram kayıt talebi',
              'Telegram kayıt talebi',
            )}{' '}
            yönetici kararını bekliyor.{' '}
            <Link
              to="/kayit-talepleri"
              className="font-semibold underline underline-offset-2"
            >
              Talepleri incele
            </Link>
          </p>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Aktif Projeler"
          value={summary?.project_count ?? 0}
          hint="Tüm projeler aktif kabul edilir"
          icon={FolderKanban}
          tone="blue"
          isLoading={isLoading}
        />
        <StatCard
          label="Aktif Çalışanlar"
          value={summary?.active_employee_count ?? 0}
          hint="Telegram onayıyla aktifleşen çalışanlar"
          icon={Users}
          tone="green"
          isLoading={isLoading}
        />
        <StatCard
          label="Görevler"
          value={summary?.task_count ?? 0}
          hint="Projelere bağlı toplam görev"
          icon={ListChecks}
          tone="navy"
          isLoading={isLoading}
        />
        <StatCard
          label="Bekleyen Kayıt Talepleri"
          value={summary?.pending_registration_count ?? 0}
          hint="Telegram üzerinden gelen başvurular"
          icon={ClipboardCheck}
          tone="amber"
          isLoading={isLoading}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card>
          <CardHeader
            title="Son Projeler"
            description="En son oluşturulan projeler ve ekip büyüklükleri."
            action={
              <Link
                to="/projeler"
                className="inline-flex items-center gap-1 text-sm font-semibold text-worktrack-blue hover:underline"
              >
                Tümü
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            }
          />

          {isLoading ? (
            <LoadingState variant="table" rows={4} />
          ) : summary && summary.recent_projects.length > 0 ? (
            <div className="table-shell rounded-none border-0">
              <table className="data-table">
                <thead>
                  <tr>
                    <th scope="col">Proje</th>
                    <th scope="col">Konum</th>
                    <th scope="col">Görev</th>
                    <th scope="col">Ekip</th>
                    <th scope="col">Beklenen Tamamlanma</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recent_projects.map((project) => (
                    <tr key={project.id}>
                      <td>
                        <Link
                          to={`/projeler/${project.id}`}
                          className="font-medium text-worktrack-ink hover:text-worktrack-blue hover:underline"
                        >
                          {project.name}
                        </Link>
                      </td>
                      <td className="text-slate-500">
                        {project.location ?? '—'}
                      </td>
                      <td>{project.task_count}</td>
                      <td>{project.employee_count}</td>
                      <td className="text-slate-500">
                        {formatDate(project.expected_completion_date)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : summary ? (
            <EmptyState
              icon={FolderKanban}
              title="Henüz proje yok"
              description="İlk projeyi oluşturarak görevleri, çalışan atamalarını ve haftalık planları buradan yönetmeye başlayın."
              action={
                <Button
                  onClick={() => navigate('/projeler?yeni=1')}
                  leftIcon={<Plus className="h-4 w-4" />}
                >
                  İlk Projeyi Oluştur
                </Button>
              }
              compact
            />
          ) : null}
        </Card>

        <Card>
          <CardHeader
            title="Başlangıç Adımları"
            description="Kurulum ilerlemesi mevcut kayıtlara göre hesaplanır."
          />
          <div className="divide-y divide-worktrack-line">
            <StartStep
              done={(summary?.project_count ?? 0) > 0}
              title="Proje oluştur"
              description="Takip edilecek ilk projeyi tanımlayın."
              to="/projeler?yeni=1"
              actionLabel="Oluştur"
            />
            <StartStep
              done={(summary?.active_employee_count ?? 0) > 0}
              title="Çalışanları kontrol et"
              description="Çalışanlar Telegram onayıyla sisteme katılır."
              to="/calisanlar"
              actionLabel="Görüntüle"
            />
            <StartStep
              done={(summary?.task_count ?? 0) > 0}
              title="Görev ekle"
              description="Görevleri projelere bağlayın ve çalışan atayın."
              to={
                (summary?.project_count ?? 0) > 0
                  ? '/gorevler?yeni=1'
                  : '/projeler?yeni=1'
              }
              actionLabel={
                (summary?.project_count ?? 0) > 0
                  ? 'Görev ekle'
                  : 'Önce proje'
              }
            />
          </div>
          <div className="border-t border-worktrack-line bg-slate-50/60 px-5 py-3">
            <p className="text-xs leading-5 text-slate-500">
              Çalışanlar projelere doğrudan bağlanmaz; proje ekibi,
              görev atamalarından türetilir.
            </p>
          </div>
        </Card>
      </div>
    </div>
  )
}
