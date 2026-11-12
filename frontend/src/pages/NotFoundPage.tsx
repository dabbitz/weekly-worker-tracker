import { ArrowLeft, Compass, LayoutDashboard } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'

export function NotFoundPage() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div className="flex min-h-[60vh] items-center justify-center py-8">
      <Card className="w-full max-w-xl p-8 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-worktrack-navy/5 text-worktrack-navy">
          <Compass className="h-7 w-7" aria-hidden="true" />
        </div>
        <p className="mt-5 text-xs font-semibold tracking-widest text-worktrack-blue uppercase">
          404
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-worktrack-ink">
          Sayfa bulunamadı
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
            {location.pathname}
          </code>{' '}
          adresi bu panelde tanımlı değil. Adresi kontrol edin veya
          aşağıdaki bağlantılardan devam edin.
        </p>

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <Button
            onClick={() => navigate('/')}
            leftIcon={<LayoutDashboard className="h-4 w-4" />}
          >
            Genel Bakış'a git
          </Button>
          <Button
            variant="secondary"
            onClick={() => navigate(-1)}
            leftIcon={<ArrowLeft className="h-4 w-4" />}
          >
            Önceki sayfaya dön
          </Button>
        </div>
      </Card>
    </div>
  )
}
