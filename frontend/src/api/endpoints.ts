import {
  buildQuery,
  request,
  tokenStorage,
} from './client'
import type {
  Admin,
  DashboardSummary,
  Employee,
  EmployeeDetail,
  LoginResponse,
  Page,
  Project,
  ProjectDetail,
  ProjectOption,
  ProjectPayload,
  RegistrationRequest,
  RegistrationStatus,
  Task,
  TaskCreatePayload,
  TaskPayload,
  WeeklyPlan,
  WeeklyPlanPayload,
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
}

export const weeklyPlansApi = {
  list(
    params: ListParams & {
      project_id?: number
      task_id?: number
      week_start_date?: string
    } = {},
  ): Promise<Page<WeeklyPlan>> {
    return request<Page<WeeklyPlan>>(
      `/weekly-plans${buildQuery(params)}`,
    )
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
}

export const registrationRequestsApi = {
  list(
    params: ListParams & { status?: RegistrationStatus },
  ): Promise<Page<RegistrationRequest>> {
    return request<Page<RegistrationRequest>>(
      `/registration-requests${buildQuery(params)}`,
    )
  },
}
