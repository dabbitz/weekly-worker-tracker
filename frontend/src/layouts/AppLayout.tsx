import {
  BarChart3,
  CalendarDays,
  ChevronRight,
  ClipboardCheck,
  FolderKanban,
  LayoutDashboard,
  ListChecks,
  LogOut,
  Menu,
  Users,
  X,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'
import { cn, getInitials } from '../lib/utils'

const navigation = [
  { to: '/', label: 'Genel Bakış', icon: LayoutDashboard, end: true },
  { to: '/projeler', label: 'Projeler', icon: FolderKanban },
  { to: '/calisanlar', label: 'Çalışanlar', icon: Users },
  { to: '/gorevler', label: 'Görevler', icon: ListChecks },
  { to: '/haftalik-planlar', label: 'Haftalık Planlar', icon: CalendarDays },
  { to: '/kayit-talepleri', label: 'Kayıt Talepleri', icon: ClipboardCheck },
  { to: '/raporlar', label: 'Raporlar', icon: BarChart3 },
]

function resolveTitle(pathname: string): string {
  if (pathname === '/') return 'Genel Bakış'
  if (pathname.startsWith('/projeler/')) return 'Proje Detayı'
  if (pathname === '/projeler') return 'Projeler'
  if (pathname.startsWith('/calisanlar/')) return 'Çalışan Detayı'
  if (pathname === '/calisanlar') return 'Çalışanlar'
  if (pathname === '/gorevler') return 'Görevler'
  if (pathname === '/haftalik-planlar') return 'Haftalık Planlar'
  if (pathname === '/kayit-talepleri') return 'Kayıt Talepleri'
  if (pathname.startsWith('/raporlar/haftalik/')) {
    return 'Haftalık Yönetici Raporu'
  }
  if (pathname === '/raporlar') return 'Raporlar'
  return 'WorkTrack'
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/giris', { replace: true })
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-5 pt-6 pb-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-lg font-bold text-worktrack-navy shadow-sm">
          W
        </div>
        <div>
          <p className="text-base font-semibold tracking-tight text-white">
            WorkTrack
          </p>
          <p className="text-xs text-slate-300">Yönetim Paneli</p>
        </div>
      </div>

      <nav
        aria-label="Ana menü"
        className="flex-1 space-y-1 overflow-y-auto px-3 py-3"
      >
        {navigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition',
                isActive
                  ? 'bg-white/12 text-white shadow-[inset_3px_0_0_#6ea0ff]'
                  : 'text-slate-300 hover:bg-white/6 hover:text-white',
              )
            }
          >
            <item.icon className="h-4.5 w-4.5 shrink-0" aria-hidden="true" />
            <span className="flex-1">{item.label}</span>
            <ChevronRight
              className="h-3.5 w-3.5 opacity-0 transition group-hover:opacity-60"
              aria-hidden="true"
            />
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="flex items-center gap-3 rounded-lg bg-white/5 p-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs font-semibold text-white">
            {user ? getInitials(user.username) : 'YT'}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white">
              {user?.username ?? 'Yönetici'}
            </p>
            <p className="text-[11px] tracking-wide text-slate-400 uppercase">
              Yönetici
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleLogout()}
            className="rounded-md p-1.5 text-slate-300 transition hover:bg-white/10 hover:text-white"
            aria-label="Oturumu kapat"
            title="Oturumu kapat"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
        <p className="mt-3 text-center text-[11px] text-slate-500">
          WorkTrack · Haftalık iş takibi
        </p>
      </div>
    </div>
  )
}

export function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const { user } = useAuth()

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-worktrack-canvas print:min-h-0">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[110] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:shadow-lg"
      >
        İçeriğe geç
      </a>

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 bg-worktrack-navy lg:block">
        <SidebarContent />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            className="absolute inset-0 bg-slate-950/50"
            onClick={() => setMobileOpen(false)}
            aria-label="Menüyü kapat"
          />
          <aside className="relative h-full w-72 max-w-[85vw] bg-worktrack-navy shadow-2xl">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute top-4 right-3 rounded-md p-1.5 text-slate-300 hover:bg-white/10 hover:text-white"
              aria-label="Menüyü kapat"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64 print:pl-0">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-worktrack-line bg-white/90 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-2 text-slate-600 transition hover:bg-slate-100 lg:hidden"
              aria-label="Menüyü aç"
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-worktrack-ink">
                {resolveTitle(location.pathname)}
              </p>
              <p className="hidden text-xs text-slate-400 sm:block">
                WorkTrack Yönetim Paneli
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden text-xs text-slate-500 sm:block">
              {user?.username}
            </span>
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-worktrack-navy/10 text-[11px] font-semibold text-worktrack-navy">
              {user ? getInitials(user.username) : 'YT'}
            </span>
          </div>
        </header>

        <main
          id="main-content"
          className="mx-auto w-full max-w-[1440px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8"
        >
          <Outlet />
        </main>
      </div>
    </div>
  )
}
