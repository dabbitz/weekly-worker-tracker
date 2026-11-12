import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { authApi } from '../api/endpoints'
import { onUnauthorized, tokenStorage } from '../api/client'
import type { Admin } from '../types'

interface AuthContextValue {
  user: Admin | null
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Admin | null>(null)
  const [isLoading, setIsLoading] = useState(
    () => tokenStorage.get() !== null,
  )

  useEffect(() => {
    let cancelled = false

    const token = tokenStorage.get()

    if (!token) {
      setIsLoading(false)
      return
    }

    authApi
      .me()
      .then((admin) => {
        if (!cancelled) {
          setUser(admin)
        }
      })
      .catch(() => {
        if (!cancelled) {
          tokenStorage.clear()
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(
    () =>
      onUnauthorized(() => {
        tokenStorage.clear()
        setUser(null)
      }),
    [],
  )

  const login = useCallback(
    async (username: string, password: string) => {
      const response = await authApi.login(username, password)
      setUser(response.admin)
    },
    [],
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } finally {
      tokenStorage.clear()
      setUser(null)
    }
  }, [])

  const value = useMemo(
    () => ({ user, isLoading, login, logout }),
    [user, isLoading, login, logout],
  )

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)

  if (context === null) {
    throw new Error('useAuth, AuthProvider içinde kullanılmalıdır.')
  }

  return context
}
