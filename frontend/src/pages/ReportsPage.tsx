import {
  ArrowRight,
  BarChart3,
  CalendarDays,
  ClipboardList,
  Clock3,
  FolderKanban,
  ListChecks,
  Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { Alert } from '../components/ui/Alert'
import { Badge } from '../components/ui/Badge'
import { Card, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'

const plannedReports = [
  'Görev bazlı haftalık hedef ve gerçekleşme karşılaştırması',
  'Çalışan bazlı tamamlanan iş güncellemeleri',
  'Proje bazlı haftalık ilerleme özeti',
  'Onaylanan ve reddedilen iş güncellemelerinin dökümü',
]

const dataSources = [
  {
    to: '/projeler',
    label: 'Projeler',
    description: 'Proje kayıtları, görev ve ekip sayıları',
    icon: FolderKanban,
  },
  {
    to: '/gorevler',
    label: 'Görevler',
    description: 'Planlanan tarihler ve çalışan atamaları',
    icon: ListChecks,
  },
  {
    to: '/haftalik-planlar',
    label: 'Haftalık Planlar',
    description: 'Haftalık hedefler ve hedef tamamlanma yüzdeleri',
    icon: CalendarDays,
  },
  {
    to: '/calisanlar',
    label: 'Çalışanlar',
    description: 'Aktif/pasif durum ve görev dağılımı',
    icon: Users,
  },
]

export function ReportsPage() {
  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Sonraki Aşama"
        title="Raporlar"
        description="Haftalık performans raporları, gerçek iş güncellemeleri toplanmaya başladıktan sonra burada üretilecek."
        actions={<Badge tone="warning">Planlanıyor</Badge>}
      />

      <Alert tone="info" title="Bu sayfada örnek veri gösterilmez">
        WorkTrack, doğrulanmamış veya tahmini metrikler üretmez.
        Raporlar yalnızca veritabanındaki gerçek görev, atama, haftalık
        plan ve iş güncellemesi kayıtlarına dayanacaktır.
      </Alert>

      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader
            title="Hazırlanan Raporlar"
            description="Çalışan iş güncellemesi akışı etkinleştirildiğinde aşağıdaki raporlar gerçek kayıtlarla oluşturulacak."
          />
          <ul className="divide-y divide-worktrack-line">
            {plannedReports.map((report) => (
              <li
                key={report}
                className="flex items-start gap-3 px-5 py-3.5"
              >
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                  <BarChart3
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-worktrack-ink">
                    {report}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500">
                    Henüz kullanılamıyor · sonraki aşama
                  </p>
                </div>
                <Badge tone="neutral">Beklemede</Badge>
              </li>
            ))}
          </ul>
          <div className="flex items-start gap-2 border-t border-worktrack-line bg-slate-50/60 px-5 py-3">
            <Clock3
              className="mt-0.5 h-4 w-4 shrink-0 text-slate-400"
              aria-hidden="true"
            />
            <p className="text-xs leading-5 text-slate-500">
              Raporların ön koşulu, çalışanların Telegram üzerinden
              ilettiği iş güncellemelerinin onaylanmış kayıtlara
              dönüşmesidir. Bu akış şu anda bu panelin kapsamı dışında
              tutulmaktadır.
            </p>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Mevcut Gerçek Veriler"
            description="Raporlar hazır olana kadar güncel kayıtları ilgili sayfalardan inceleyebilirsiniz."
          />
          <ul className="divide-y divide-worktrack-line">
            {dataSources.map((source) => (
              <li key={source.to}>
                <Link
                  to={source.to}
                  className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-slate-50/70"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-worktrack-navy/5 text-worktrack-navy">
                    <source.icon
                      className="h-4 w-4"
                      aria-hidden="true"
                    />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-worktrack-ink">
                      {source.label}
                    </span>
                    <span className="block text-xs text-slate-500">
                      {source.description}
                    </span>
                  </span>
                  <ArrowRight
                    className="h-4 w-4 text-slate-300"
                    aria-hidden="true"
                  />
                </Link>
              </li>
            ))}
          </ul>
          <div className="border-t border-worktrack-line bg-slate-50/60 px-5 py-3">
            <Link
              to="/"
              className="inline-flex items-center gap-1 text-xs font-semibold text-worktrack-blue hover:underline"
            >
              <ClipboardList className="h-3.5 w-3.5" aria-hidden="true" />
              Genel Bakış'ta güncel sayıları görün
            </Link>
          </div>
        </Card>
      </div>
    </div>
  )
}
