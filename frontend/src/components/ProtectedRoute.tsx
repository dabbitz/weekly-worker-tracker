import { Loader2 } from 'lucide-react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../hooks/useAuth'

export function ProtectedRoute() {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-worktrack-canvas">
        <div
          className="flex items-center gap-3 text-sm text-slate-500"
          role="status"
        >
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          Oturum kontrol ediliyor…
        </div>
      </div>
    )
  }

  if (!user) {
    return (
      <Navigate
        to="/giris"
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  }

  return <Outlet />
}
