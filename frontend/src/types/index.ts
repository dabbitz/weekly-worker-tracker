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

export interface ProjectDeletionPreview {
  id: number
  name: string
  task_count: number
  assignment_count: number
  weekly_plan_count: number
  report_count: number
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

export type WeeklyPlanStatus =
  | 'draft'
  | 'approved'
  | 'rejected'
  | 'superseded'

export type WeeklyPlanSource = 'manual' | 'ai'

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
  status: WeeklyPlanStatus
  source: WeeklyPlanSource
  generation_id: number | null
  generation_request_id: string | null
  ai_rationale: string | null
  ai_assumptions: string | null
  ai_warnings: string | null
  approved_at: string | null
  created_at: string
  updated_at: string
}

export interface AIPlanGeneratePayload {
  task_ids: number[]
  extra_instructions: string | null
  request_id: string
}

export interface AIPlanGenerateResponse {
  generation_id: number
  request_id: string
  plan_count: number
  tasks: number[]
  plans: WeeklyPlan[]
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

export type WorkStatus =
  | 'completed'
  | 'in_progress'
  | 'blocked'
  | 'not_started'
  | 'unknown'

export type ReportReviewStatus = 'pending' | 'approved' | 'rejected'

export interface ReportListItem {
  id: number
  received_at: string
  employee_id: number | null
  employee_name: string | null
  project_id: number | null
  project_name: string | null
  task_id: number | null
  task_title: string | null
  completion_percentage: number | null
  status: WorkStatus
  has_blocker: boolean
  has_delay: boolean
  review_status: ReportReviewStatus
  weekly_plan_id: number | null
  has_weekly_plan: boolean
}

export interface ReportStats {
  total: number
  blocked_count: number
  with_blocker_count: number
  with_delay_count: number
  completed_count: number
}

export interface ReportListResponse extends Page<ReportListItem> {
  stats: ReportStats
}

export interface ReportWeeklyPlan {
  id: number
  target_description: string
  target_completion_percentage: number | null
  week_start_date: string
  week_end_date: string
  status: WeeklyPlanStatus
}

export interface ReportDetail extends ReportListItem {
  task_description: string | null
  original_message: string
  task_reference_text: string | null
  blocker: string | null
  delay_reason: string | null
  next_step: string | null
  reported_eta_text: string | null
  reported_eta_date: string | null
  reported_eta_weekday: string | null
  summary: string | null
  ai_model: string | null
  reviewed_at: string | null
  reviewed_by_employee_id: number | null
  reviewed_by_employee_name: string | null
  weekly_plan: ReportWeeklyPlan | null
}

/* ------------------------------------------------------------------ */
/* Weekly manager reports                                              */
/* ------------------------------------------------------------------ */

export type WeeklyReportStatus = 'pending' | 'completed' | 'failed'

export interface WeekPeriod {
  week_start_date: string
  week_end_date: string
  label: string
  is_current_week: boolean
  is_partial_week: boolean
  is_completed: boolean
  is_future: boolean
  is_default: boolean
}

export interface WeeklyReportPeriodsResponse {
  periods: WeekPeriod[]
  default_week_start_date: string
  current_week_start_date: string
  timezone: string
}

export interface WeeklyPreviewWarning {
  code: string
  message: string
}

export interface WeeklyPreviewProject {
  project_token: string
  name: string
  task_count: number
  report_count: number
}

export interface WeeklyReportPreview {
  week_start_date: string
  week_end_date: string
  label: string
  is_partial_week: boolean
  is_current_week: boolean
  project_count: number
  task_count: number
  plan_count: number
  report_count: number
  pending_review_report_count: number
  completed_task_count: number
  in_progress_task_count: number
  blocked_task_count: number
  not_started_task_count: number
  no_report_task_count: number
  unassigned_task_count: number
  plan_conflict_count: number
  missing_target_percentage_count: number
  intervention_candidate_count: number
  has_data: boolean
  projects: WeeklyPreviewProject[]
  warnings: WeeklyPreviewWarning[]
}

export interface WeeklyReportCreatePayload {
  week_start_date: string
  request_id: string
  extra_instructions?: string
}

export interface WeeklyReportListItem {
  id: number
  week_start_date: string
  week_end_date: string
  version: number
  status: WeeklyReportStatus
  model: string | null
  is_partial_week: boolean
  created_at: string
  completed_at: string | null
  error_message: string | null
  has_narrative: boolean
  project_count: number
  task_count: number
  report_count: number
  intervention_count: number
}

export interface WeeklyReportListResponse
  extends Page<WeeklyReportListItem> {}

export interface NarrativeSegment {
  type: 'text' | 'reference'
  text: string | null
  token: string | null
  kind: string | null
  ref_id: number | null
  label: string | null
  href: string | null
}

export interface NarrativeBlock {
  segments: NarrativeSegment[]
  sources: NarrativeSegment[]
}

export interface NarrativeProjectView {
  project: NarrativeSegment
  summary: NarrativeSegment[]
  highlights: NarrativeBlock[]
  risks: NarrativeBlock[]
}

export interface NarrativeEmployeeView {
  employee: NarrativeSegment
  summary: NarrativeSegment[]
  observations: NarrativeBlock[]
}

export interface NarrativeTaskView {
  task: NarrativeSegment
  assessment: NarrativeSegment[]
  classification: string
  classification_label: string
  sources: NarrativeSegment[]
}

export type InterventionPriority = 'high' | 'medium' | 'low'

export interface NarrativeInterventionView {
  title: NarrativeSegment[]
  problem: NarrativeSegment[]
  recommended_action: NarrativeSegment[]
  priority: InterventionPriority
  affected_projects: NarrativeSegment[]
  affected_tasks: NarrativeSegment[]
  sources: NarrativeSegment[]
}

export interface NarrativeView {
  source: 'ai' | 'deterministic_empty'
  general_summary: NarrativeSegment[]
  general_highlights: NarrativeBlock[]
  general_issues: NarrativeBlock[]
  project_analyses: NarrativeProjectView[]
  employee_analyses: NarrativeEmployeeView[]
  task_assessments: NarrativeTaskView[]
  unmet_work_analysis: NarrativeBlock[]
  history_comparison: NarrativeBlock[]
  recommendations: NarrativeBlock[]
  data_quality_notes: NarrativeBlock[]
  manager_interventions: NarrativeInterventionView[]
  partial_week_note: NarrativeSegment[] | null
}

export interface WeeklyMetricsSummary {
  project_count: number
  task_count: number
  plan_count: number
  plan_approved_after_week_count: number
  report_count: number
  pending_review_report_count: number
  rejected_report_count: number
  unlinked_report_count: number
  completed_task_count: number
  in_progress_task_count: number
  blocked_task_count: number
  not_started_task_count: number
  unknown_task_count: number
  no_report_task_count: number
  unassigned_task_count: number
  overdue_not_completed_count: number
  plan_conflict_count: number
  missing_target_percentage_count: number
  conflicting_report_count: number
  delay_reason_missing_count: number
  employee_count: number
  missing_dates_task_count: number
}

export interface WeeklyLatestReportSnapshot {
  report_token: string
  employee_token: string | null
  status: WorkStatus
  completion_percentage: number | null
  received_at: string
  summary: string | null
  blocker: string | null
  delay_reason: string | null
  next_step: string | null
  reported_eta_text: string | null
  reported_eta_date: string | null
}

export interface WeeklyPlanSnapshot {
  plan_token: string
  week_start_date: string
  week_end_date: string
  target_description: string
  target_completion_percentage: number | null
  approved_at: string | null
}

export interface WeeklyTaskSnapshot {
  task_token: string
  id: number
  project_token: string
  title: string
  description: string | null
  planned_start_date: string | null
  planned_due_date: string | null
  has_dates: boolean
  created_at: string | null
  assigned_employee_tokens: string[]
  approved_report_tokens: string[]
  latest_report: WeeklyLatestReportSnapshot | null
  plan: WeeklyPlanSnapshot | null
  plan_tokens: string[]
  plan_conflict: boolean
  plan_approved_after_week: boolean
  classification: string
  classification_label: string
  target_completion_percentage: number | null
  reported_completion_percentage: number | null
  reported_status: WorkStatus | null
  completed_reported: boolean
  overdue: boolean
  unassigned: boolean
  eta_slipped: boolean
  repeated_blocker: boolean
  conflicting_reports: boolean
  pending_review_report_count: number
}

export interface WeeklyEmployeeProgress {
  task_token: string | null
  completion_percentage: number | null
  status: WorkStatus
  report_token: string
}

export interface WeeklyEmployeeSnapshot {
  employee_token: string
  id: number
  full_name: string
  role: string | null
  is_active: boolean
  assigned_task_tokens: string[]
  reported_task_tokens: string[]
  report_tokens: string[]
  report_count: number
  pending_report_count: number
  completed_task_tokens: string[]
  blocked_task_tokens: string[]
  blocker_count: number
  delay_count: number
  task_progress: WeeklyEmployeeProgress[]
  prior_week_report_count: number
  report_trend: 'up' | 'down' | 'same' | null
}

export interface WeeklyProjectSnapshot {
  project_token: string
  id: number
  name: string
  description: string | null
  location: string | null
  expected_completion_date: string | null
  task_tokens: string[]
  employee_tokens: string[]
  task_count: number
  report_count: number
  completed_task_count: number
  blocked_task_count: number
  plan_count: number
  risk_codes: string[]
}

export interface WeeklyComparison {
  available: boolean
  prior_week_start_date: string
  prior_week_end_date: string
  current_report_count: number
  prior_report_count: number
  report_count_change: number
  employee_trends: Array<{
    employee_token: string
    prior_report_count: number
    current_report_count: number
    trend: 'up' | 'down' | 'same' | null
  }>
  project_trends: Array<{
    project_token: string
    prior_report_count: number
    current_report_count: number
    trend: 'up' | 'down' | 'same' | null
  }>
  task_progress_changes: Array<{
    task_token: string | null
    prior_completion_percentage: number
    current_completion_percentage: number
    delta: number
  }>
  repeated_blocker_texts: string[]
}

export interface WeeklyDataQualityItem {
  code: string
  message: string
  task_tokens: string[]
  project_tokens: string[]
  report_tokens: string[]
  plan_tokens: string[]
  task_labels?: string[]
  count?: number | null
}

export interface WeeklyInterventionCandidate {
  code: string
  priority: InterventionPriority
  priority_source: string
  title: string
  description: string
  task_tokens: string[]
  project_tokens: string[]
  report_tokens: string[]
  plan_tokens: string[]
  evidence_count: number
}

export interface WeeklyMetricsSnapshot {
  week: {
    week_start_date: string
    week_end_date: string
    timezone: string
    is_partial_week: boolean
    is_current_week: boolean
    evaluated_at: string
  }
  summary: WeeklyMetricsSummary
  projects: WeeklyProjectSnapshot[]
  tasks: WeeklyTaskSnapshot[]
  employees: WeeklyEmployeeSnapshot[]
  plans: WeeklyPlanSnapshot[]
  reports: Array<Record<string, unknown>>
  pending_reports: Array<Record<string, unknown>>
  repeated_blockers: Array<Record<string, unknown>>
  comparison: WeeklyComparison
  data_quality: WeeklyDataQualityItem[]
  intervention_candidates: WeeklyInterventionCandidate[]
  methodology: Record<string, string>
}

export interface WeeklyReferenceEntry {
  id?: number
  label?: string
  href?: string
  project_token?: string
  received_at?: string
  week_start_date?: string
  week_end_date?: string
}

export type WeeklyReferences = Record<
  'projects' | 'tasks' | 'employees' | 'reports' | 'plans' | 'weeks',
  Record<string, WeeklyReferenceEntry>
>

export interface WeeklyReportDetail extends WeeklyReportListItem {
  request_id: string
  extra_instructions: string | null
  metrics_snapshot: WeeklyMetricsSnapshot
  data_quality: WeeklyDataQualityItem[]
  narrative: Record<string, unknown> | null
  narrative_view: NarrativeView | null
  references: WeeklyReferences
  intervention_candidates: WeeklyInterventionCandidate[]
}
