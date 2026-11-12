import {
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { ApiError } from './api/client'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ToastProvider } from './components/ui/Toast'
import { AuthProvider } from './hooks/useAuth'
import { AppLayout } from './layouts/AppLayout'
import { DashboardPage } from './pages/DashboardPage'
import { EmployeeDetailPage } from './pages/EmployeeDetailPage'
import { EmployeesPage } from './pages/EmployeesPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProjectDetailPage } from './pages/ProjectDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { RegistrationRequestsPage } from './pages/RegistrationRequestsPage'
import { ReportsPage } from './pages/ReportsPage'
import { TasksPage } from './pages/TasksPage'
import { WeeklyPlansPage } from './pages/WeeklyPlansPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if (error.status >= 400 && error.status < 500) {
            return false
          }
        }
        return failureCount < 2
      },
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/giris" element={<LoginPage />} />

              <Route element={<ProtectedRoute />}>
                <Route element={<AppLayout />}>
                  <Route index element={<DashboardPage />} />
                  <Route path="projeler" element={<ProjectsPage />} />
                  <Route
                    path="projeler/:projectId"
                    element={<ProjectDetailPage />}
                  />
                  <Route path="calisanlar" element={<EmployeesPage />} />
                  <Route
                    path="calisanlar/:employeeId"
                    element={<EmployeeDetailPage />}
                  />
                  <Route path="gorevler" element={<TasksPage />} />
                  <Route
                    path="haftalik-planlar"
                    element={<WeeklyPlansPage />}
                  />
                  <Route
                    path="kayit-talepleri"
                    element={<RegistrationRequestsPage />}
                  />
                  <Route path="raporlar" element={<ReportsPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
