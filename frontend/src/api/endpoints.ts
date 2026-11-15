import {
  buildQuery,
  request,
  tokenStorage,
} from './client'
import type {
  Admin,
  AIPlanGeneratePayload,
  AIPlanGenerateResponse,
  DashboardSummary,
  Employee,
  EmployeeDetail,
  EmployeeUpdatePayload,
  LoginResponse,
  Page,
  Project,
  ProjectDeletionPreview,
  ProjectDetail,
  ProjectOption,
  ProjectPayload,
  RegistrationRequest,
  RegistrationStatus,
  ReportDetail,
  ReportListResponse,
  Task,
  TaskCreatePayload,
  TaskPayload,
  WeeklyPlan,
  WeeklyPlanPayload,
  WeeklyPlanSource,
  WeeklyPlanStatus,
  WeeklyReportCreatePayload,
  WeeklyReportDetail,
  WeeklyReportListResponse,
  WeeklyReportPeriodsResponse,
  WeeklyReportPreview,
  WeeklyReportStatus,
  WorkStatus,
} from '../types'

interface ListParams {
  page?: number
  page_size?: number
  search?: string
}

export const authApi = {
  async login(username: string, password: string): Promise<LoginResponse> {
    const result = await request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: { username, password },
      auth: false,
    })
    tokenStorage.set(result.access_token)
    return result
  },

  me(): Promise<Admin> {
    return request<Admin>('/auth/me')
  },

  async logout(): Promise<void> {
    try {
      await request<void>('/auth/logout', { method: 'POST' })
    } finally {
      tokenStorage.clear()
    }
  },
}

export const dashboardApi = {
  summary(): Promise<DashboardSummary> {
    return request<DashboardSummary>('/dashboard/summary')
  },
}

export const projectsApi = {
  list(params: ListParams = {}): Promise<Page<Project>> {
    return request<Page<Project>>(`/projects${buildQuery(params)}`)
  },

  options(): Promise<ProjectOption[]> {
    return request<ProjectOption[]>('/projects/options')
  },

  get(id: number): Promise<ProjectDetail> {
    return request<ProjectDetail>(`/projects/${id}`)
  },

  create(payload: ProjectPayload): Promise<Project> {
    return request<Project>('/projects', {
      method: 'POST',
      body: payload,
    })
  },

  update(id: number, payload: ProjectPayload): Promise<Project> {
    return request<Project>(`/projects/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  },

  deletionPreview(id: number): Promise<ProjectDeletionPreview> {
    return request<ProjectDeletionPreview>(
      `/projects/${id}/deletion-preview`,
    )
  },

  remove(id: number): Promise<void> {
    return request<void>(`/projects/${id}`, {
      method: 'DELETE',
    })
  },
}

export const employeesApi = {
  list(
    params: ListParams & { is_active?: boolean },
  ): Promise<Page<Employee>> {
    return request<Page<Employee>>(`/employees${buildQuery(params)}`)
  },

  get(id: number): Promise<EmployeeDetail> {
    return request<EmployeeDetail>(`/employees/${id}`)
  },

  update(
    id: number,
    payload: EmployeeUpdatePayload,
  ): Promise<Employee> {
    return request<Employee>(`/employees/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  },

  remove(id: number): Promise<void> {
    return request<void>(`/employees/${id}`, {
      method: 'DELETE',
    })
  },
}

export const tasksApi = {
  list(
    params: ListParams & {
      project_id?: number
      employee_id?: number
    } = {},
  ): Promise<Page<Task>> {
    return request<Page<Task>>(`/tasks${buildQuery(params)}`)
  },

  get(id: number): Promise<Task> {
    return request<Task>(`/tasks/${id}`)
  },

  create(payload: TaskCreatePayload): Promise<Task> {
    return request<Task>('/tasks', {
      method: 'POST',
      body: payload,
    })
  },

  update(id: number, payload: TaskPayload): Promise<Task> {
    return request<Task>(`/tasks/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  },

  setAssignments(id: number, employeeIds: number[]): Promise<Task> {
    return request<Task>(`/tasks/${id}/assignments`, {
      method: 'PUT',
      body: { employee_ids: employeeIds },
    })
  },

  remove(id: number): Promise<void> {
    return request<void>(`/tasks/${id}`, {
      method: 'DELETE',
    })
  },
}

export const weeklyPlansApi = {
  list(
    params: ListParams & {
      project_id?: number
      task_id?: number
      week_start_date?: string
      status?: WeeklyPlanStatus
      source?: WeeklyPlanSource
      generation_id?: number
    } = {},
  ): Promise<Page<WeeklyPlan>> {
    return request<Page<WeeklyPlan>>(
      `/weekly-plans${buildQuery(params)}`,
    )
  },

  get(id: number): Promise<WeeklyPlan> {
    return request<WeeklyPlan>(`/weekly-plans/${id}`)
  },

  create(payload: WeeklyPlanPayload): Promise<WeeklyPlan> {
    return request<WeeklyPlan>('/weekly-plans', {
      method: 'POST',
      body: payload,
    })
  },

  update(
    id: number,
    payload: WeeklyPlanPayload,
  ): Promise<WeeklyPlan> {
    return request<WeeklyPlan>(`/weekly-plans/${id}`, {
      method: 'PATCH',
      body: payload,
    })
  },

  approve(
    id: number,
    replaceExisting = false,
  ): Promise<WeeklyPlan> {
    return request<WeeklyPlan>(`/weekly-plans/${id}/approve`, {
      method: 'POST',
      body: { replace_existing: replaceExisting },
    })
  },

  reject(id: number): Promise<WeeklyPlan> {
    return request<WeeklyPlan>(`/weekly-plans/${id}/reject`, {
      method: 'POST',
    })
  },

  remove(id: number): Promise<void> {
    return request<void>(`/weekly-plans/${id}`, {
      method: 'DELETE',
    })
  },

  generateAi(
    payload: AIPlanGeneratePayload,
  ): Promise<AIPlanGenerateResponse> {
    return request<AIPlanGenerateResponse>(
      '/weekly-plans/ai/generate',
      {
        method: 'POST',
        body: payload,
      },
    )
  },
}

export const registrationRequestsApi = {
  list(
    params: ListParams & { status?: RegistrationStatus },
  ): Promise<Page<RegistrationRequest>> {
    return request<Page<RegistrationRequest>>(
      `/registration-requests${buildQuery(params)}`,
    )
  },

  remove(id: number): Promise<void> {
    return request<void>(`/registration-requests/${id}`, {
      method: 'DELETE',
    })
  },
}

export interface ReportListParams {
  page?: number
  page_size?: number
  date_from?: string
  date_to?: string
  project_id?: number
  employee_id?: number
  task_id?: number
  status?: WorkStatus
  has_blocker?: boolean
  has_delay?: boolean
}

export const reportsApi = {
  list(params: ReportListParams = {}): Promise<ReportListResponse> {
    return request<ReportListResponse>(
      `/reports${buildQuery(params)}`,
    )
  },

  get(id: number): Promise<ReportDetail> {
    return request<ReportDetail>(`/reports/${id}`)
  },

  remove(id: number): Promise<void> {
    return request<void>(`/reports/${id}`, {
      method: 'DELETE',
    })
  },
}

export interface WeeklyReportListParams {
  page?: number
  page_size?: number
  week_start_date?: string
  status?: WeeklyReportStatus
}

export const weeklyReportsApi = {
  periods(weeks = 12): Promise<WeeklyReportPeriodsResponse> {
    return request<WeeklyReportPeriodsResponse>(
      `/weekly-reports/periods${buildQuery({ weeks })}`,
    )
  },

  preview(weekStartDate: string): Promise<WeeklyReportPreview> {
    return request<WeeklyReportPreview>(
      `/weekly-reports/preview${buildQuery({
        week_start_date: weekStartDate,
      })}`,
    )
  },

  create(payload: WeeklyReportCreatePayload): Promise<WeeklyReportDetail> {
    return request<WeeklyReportDetail>('/weekly-reports', {
      method: 'POST',
      body: payload,
    })
  },

  list(
    params: WeeklyReportListParams = {},
  ): Promise<WeeklyReportListResponse> {
    return request<WeeklyReportListResponse>(
      `/weekly-reports${buildQuery(params)}`,
    )
  },

  get(id: number): Promise<WeeklyReportDetail> {
    return request<WeeklyReportDetail>(`/weekly-reports/${id}`)
  },

  retry(id: number): Promise<WeeklyReportDetail> {
    return request<WeeklyReportDetail>(
      `/weekly-reports/${id}/retry`,
      { method: 'POST' },
    )
  },

  remove(id: number): Promise<void> {
    return request<void>(`/weekly-reports/${id}`, {
      method: 'DELETE',
    })
  },
}
