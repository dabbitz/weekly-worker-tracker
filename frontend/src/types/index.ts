export interface Page<T> {
  items: T[]
  page: number
  page_size: number
  total: number
  pages: number
}

export interface Admin {
  username: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_at: string
  admin: Admin
}

export interface Project {
  id: number
  name: string
  description: string | null
  location: string | null
  expected_completion_date: string | null
  created_at: string
  task_count: number
  employee_count: number
}

export interface ProjectOption {
  id: number
  name: string
}

export interface EmployeeSummary {
  id: number
  full_name: string
  role: string | null
  is_active: boolean
}

export interface Employee extends EmployeeSummary {
  telegram_user_id: number | null
  created_at: string
  task_count: number
  project_count: number
}

export interface EmployeeDetail extends Employee {
  assigned_tasks: Task[]
  projects: ProjectOption[]
}

export interface Task {
  id: number
  project_id: number
  project_name: string
  title: string
  description: string | null
  planned_start_date: string | null
  planned_start_weekday: string | null
  planned_due_date: string | null
  planned_due_weekday: string | null
  created_at: string
  assigned_employees: EmployeeSummary[]
  weekly_plan_count: number
}

export interface ProjectDetail extends Project {
  tasks: Task[]
  employees: EmployeeSummary[]
}

export interface WeeklyPlan {
  id: number
  task_id: number
  task_title: string
  project_id: number
  project_name: string
  week_start_date: string
  week_end_date: string
  target_description: string
  target_completion_percentage: number | null
  created_at: string
  updated_at: string
}

export type RegistrationStatus = 'pending' | 'approved' | 'rejected'

export interface RegistrationRequest {
  id: number
  telegram_user_id: number
  requested_full_name: string
  employee_id: number | null
  employee_full_name: string | null
  status: RegistrationStatus
  created_at: string
  notification_sent_at: string | null
  reviewed_at: string | null
  reviewed_by_telegram_user_id: number | null
}

export interface DashboardSummary {
  project_count: number
  active_employee_count: number
  task_count: number
  pending_registration_count: number
  recent_projects: Project[]
}

export interface ProjectPayload {
  name: string
  description: string | null
  location: string | null
  expected_completion_date: string | null
}

export interface TaskPayload {
  project_id: number
  title: string
  description: string | null
  planned_start_date: string | null
  planned_due_date: string | null
}

export interface TaskCreatePayload extends TaskPayload {
  employee_ids: number[]
}

export interface WeeklyPlanPayload {
  task_id: number
  week_start_date: string
  week_end_date: string
  target_description: string
  target_completion_percentage: number | null
}
