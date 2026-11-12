import {
  ArrowRight,
  CalendarDays,
  Eye,
  EyeOff,
  FolderKanban,
  ListChecks,
  LockKeyhole,
  ShieldCheck,
  UserRound,
} from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Alert } from '../components/ui/Alert'
import { Button } from '../components/ui/Button'
import { Field, Input } from '../components/ui/Form'
import { useAuth } from '../hooks/useAuth'
import { getErrorMessage } from '../lib/utils'

interface LocationState {
  from?: string
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [errors, setErrors] = useState<{
    username?: string
    password?: string
  }>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const destination =
    (location.state as LocationState | null)?.from ?? '/'

  useEffect(() => {
    if (user) {
      navigate(destination, { replace: true })
    }
  }, [user, destination, navigate])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setServerError(null)

    const nextErrors: { username?: string; password?: string } = {}

    if (!username.trim()) {
      nextErrors.username = 'Kullanıcı adı zorunludur.'
    }
    if (!password) {
      nextErrors.password = 'Parola zorunludur.'
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setIsSubmitting(true)

    try {
      await login(username.trim(), password)
      navigate(destination, { replace: true })
    } catch (error) {
      setServerError(getErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-worktrack-navy px-12 py-12 lg:flex lg:flex-col lg:justify-between">
        <div
          className="pointer-events-none absolute -top-32 -right-24 h-96 w-96 rounded-full bg-worktrack-blue/20 blur-3xl"
          aria-hidden="true"
        />
        <div
          className="pointer-events-none absolute -bottom-40 -left-24 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl"
          aria-hidden="true"
        />

        <div className="relative">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white text-xl font-bold text-worktrack-navy">
              W
            </div>
            <div>
              <p className="text-lg font-semibold text-white">WorkTrack</p>
              <p className="text-sm text-slate-300">Yönetim Paneli</p>
            </div>
          </div>

          <h1 className="mt-16 max-w-lg text-3xl leading-tight font-semibold text-white">
            Haftalık iş takibini tek bir yönetim noktasından planlayın.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-6 text-slate-300">
            Projeleri, çalışanları, görev atamalarını ve haftalık
            hedefleri gerçek verilerle yönetin. Saha ve ofis ekipleri
            aynı haftalık resmi görsün.
          </p>

          <ul className="mt-10 space-y-4">
            <li className="flex items-center gap-3 text-sm text-slate-200">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
                <FolderKanban className="h-4 w-4" aria-hidden="true" />
              </span>
              Proje ve görev takibi
            </li>
            <li className="flex items-center gap-3 text-sm text-slate-200">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
                <ListChecks className="h-4 w-4" aria-hidden="true" />
              </span>
              Görev bazlı çoklu çalışan ataması
            </li>
            <li className="flex items-center gap-3 text-sm text-slate-200">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
                <CalendarDays className="h-4 w-4" aria-hidden="true" />
              </span>
              Haftalık hedef ve tamamlanma planları
            </li>
          </ul>
        </div>

        <p className="relative text-xs text-slate-400">
          Telegram kayıt akışıyla entegre · Yalnızca yönetici erişimi
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-worktrack-navy text-lg font-bold text-white">
              W
            </div>
            <div>
              <p className="font-semibold text-worktrack-ink">WorkTrack</p>
              <p className="text-xs text-slate-500">Yönetim Paneli</p>
            </div>
          </div>

          <div className="mb-8">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-worktrack-navy/5 px-3 py-1 text-xs font-medium text-worktrack-navy">
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
              Güvenli yönetici girişi
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-worktrack-ink">
              Yönetim paneline giriş
            </h2>
            <p className="mt-1.5 text-sm text-slate-500">
              Devam etmek için yönetici bilgilerinizi girin.
            </p>
          </div>

          {serverError ? (
            <Alert tone="error" className="mb-5">
              {serverError}
            </Alert>
          ) : null}

          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            <Field
              label="Kullanıcı adı"
              htmlFor="username"
              required
              error={errors.username}
            >
              <div className="relative">
                <UserRound
                  className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
                <Input
                  id="username"
                  name="username"
                  autoComplete="username"
                  value={username}
                  onChange={(event) => {
                    setUsername(event.target.value)
                    setErrors((current) => ({
                      ...current,
                      username: undefined,
                    }))
                  }}
                  placeholder="Yönetici kullanıcı adı"
                  className="pl-9"
                  invalid={Boolean(errors.username)}
                  aria-describedby={
                    errors.username ? 'username-error' : undefined
                  }
                />
              </div>
            </Field>

            <Field
              label="Parola"
              htmlFor="password"
              required
              error={errors.password}
            >
              <div className="relative">
                <LockKeyhole
                  className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400"
                  aria-hidden="true"
                />
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value)
                    setErrors((current) => ({
                      ...current,
                      password: undefined,
                    }))
                  }}
                  placeholder="Parolanız"
                  className="pr-10 pl-9"
                  invalid={Boolean(errors.password)}
                  aria-describedby={
                    errors.password ? 'password-error' : undefined
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((current) => !current)}
                  className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
                  aria-label={
                    showPassword ? 'Parolayı gizle' : 'Parolayı göster'
                  }
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" aria-hidden="true" />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </Field>

            <Button
              type="submit"
              size="lg"
              fullWidth
              isLoading={isSubmitting}
            >
              Giriş yap
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </form>

          <p className="mt-8 text-center text-xs text-slate-400">
            Bu panel yalnızca yetkili yönetici içindir. Hesap oluşturma
            kapalıdır.
          </p>
        </div>
      </section>
    </div>
  )
}
