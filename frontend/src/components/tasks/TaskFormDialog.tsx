import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { AlertTriangle, Check, Users } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import {
  employeesApi,
  projectsApi,
  tasksApi,
} from '../../api/endpoints'
import { ApiError } from '../../api/client'
import { Alert } from '../ui/Alert'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Checkbox, Field, Input, Select, Textarea } from '../ui/Form'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'
import { cn, getErrorMessage } from '../../lib/utils'
import type { Task, TaskPayload } from '../../types'

interface TaskFormDialogProps {
  open: boolean
  onClose: () => void
  task?: Task | null
  defaultProjectId?: number
}

interface FormState {
  projectId: string
  title: string
  description: string
  plannedStartDate: string
  plannedDueDate: string
}

type FormErrors = Partial<Record<keyof FormState | 'employees', string>>

const emptyForm: FormState = {
  projectId: '',
  title: '',
  description: '',
  plannedStartDate: '',
  plannedDueDate: '',
}

export function TaskFormDialog({
  open,
  onClose,
  task = null,
  defaultProjectId,
}: TaskFormDialogProps) {
  const [form, setForm] = useState<FormState>(emptyForm)
  const [employeeIds, setEmployeeIds] = useState<number[]>([])
  const [errors, setErrors] = useState<FormErrors>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const projectsQuery = useQuery({
    queryKey: ['projects', 'options'],
    queryFn: projectsApi.options,
    enabled: open,
  })

  const employeesQuery = useQuery({
    queryKey: ['employees', 'list', 'all-for-assignment'],
    queryFn: () =>
      employeesApi.list({ page: 1, page_size: 100, search: undefined }),
    enabled: open,
  })

  const currentAssignedIds = useMemo(
    () => task?.assigned_employees.map((employee) => employee.id) ?? [],
    [task],
  )

  useEffect(() => {
    if (!open) {
      return
    }

    setErrors({})
    setServerError(null)

    if (task) {
      setForm({
        projectId: String(task.project_id),
        title: task.title,
        description: task.description ?? '',
        plannedStartDate: task.planned_start_date ?? '',
        plannedDueDate: task.planned_due_date ?? '',
      })
      setEmployeeIds(currentAssignedIds)
    } else {
      setForm({
        ...emptyForm,
        projectId: defaultProjectId ? String(defaultProjectId) : '',
      })
      setEmployeeIds([])
    }
  }, [open, task, defaultProjectId, currentAssignedIds])

  const mutation = useMutation({
    mutationFn: async (payload: TaskPayload) => {
      if (task) {
        await tasksApi.update(task.id, payload)
        return tasksApi.setAssignments(task.id, employeeIds)
      }

      return tasksApi.create({
        ...payload,
        employee_ids: employeeIds,
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['employees'] })
      void queryClient.invalidateQueries({
        queryKey: ['weekly-plans'],
      })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      showToast(
        task ? 'Görev güncellendi.' : 'Görev oluşturuldu.',
        'success',
      )
      onClose()
    },
    onError: (error) => {
      setServerError(getErrorMessage(error))
      if (error instanceof ApiError) {
        setErrors((current) => ({
          ...current,
          ...mapServerErrors(error.fieldErrors),
        }))
      }
    },
  })

  const updateField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  const toggleEmployee = (employeeId: number) => {
    setEmployeeIds((current) =>
      current.includes(employeeId)
        ? current.filter((id) => id !== employeeId)
        : [...current, employeeId],
    )
    setErrors((current) => ({ ...current, employees: undefined }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setServerError(null)

    const nextErrors: FormErrors = {}
    const projectId = Number(form.projectId)
    const title = form.title.trim()

    if (!projectId) {
      nextErrors.projectId = 'Bir proje seçmelisiniz.'
    }

    if (!title) {
      nextErrors.title = 'Görev başlığı zorunludur.'
    } else if (title.length > 250) {
      nextErrors.title = 'Başlık en fazla 250 karakter olabilir.'
    }

    if (form.description.length > 8000) {
      nextErrors.description =
        'Açıklama en fazla 8000 karakter olabilir.'
    }

    if (
      form.plannedStartDate &&
      form.plannedDueDate &&
      form.plannedStartDate > form.plannedDueDate
    ) {
      nextErrors.plannedStartDate =
        'Başlangıç tarihi bitiş tarihinden sonra olamaz.'
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    mutation.mutate({
      project_id: projectId,
      title,
      description: form.description.trim() || null,
      planned_start_date: form.plannedStartDate || null,
      planned_due_date: form.plannedDueDate || null,
    })
  }

  const employees = employeesQuery.data?.items ?? []
  const projects = projectsQuery.data ?? []
  const activeCount = employees.filter(
    (employee) => employee.is_active,
  ).length

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={task ? 'Görevi Düzenle' : 'Yeni Görev'}
      description={
        task
          ? 'Görev bilgilerini ve çalışan atamalarını güncelleyin.'
          : 'Görevi bir projeye bağlayın, planlanan tarihleri girin ve çalışan atayın.'
      }
      size="lg"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Vazgeç
          </Button>
          <Button
            type="submit"
            form="task-form"
            isLoading={mutation.isPending}
            disabled={projectsQuery.isLoading}
          >
            {task ? 'Değişiklikleri kaydet' : 'Görevi oluştur'}
          </Button>
        </>
      }
    >
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      {!projectsQuery.isLoading && projects.length === 0 ? (
        <Alert tone="warning" title="Önce bir proje gerekli" className="mb-4">
          Görev oluşturmak için önce bir proje oluşturun.{' '}
          <Link
            to="/projeler?yeni=1"
            className="font-semibold underline underline-offset-2"
            onClick={onClose}
          >
            Proje oluştur
          </Link>
        </Alert>
      ) : null}

      <form
        id="task-form"
        onSubmit={handleSubmit}
        noValidate
        className="space-y-4"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Proje"
            htmlFor="task-project"
            required
            error={errors.projectId}
          >
            <Select
              id="task-project"
              value={form.projectId}
              onChange={(event) =>
                updateField('projectId', event.target.value)
              }
              invalid={Boolean(errors.projectId)}
              disabled={projectsQuery.isLoading}
            >
              <option value="">Proje seçin</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </Select>
          </Field>

          <Field
            label="Görev başlığı"
            htmlFor="task-title"
            required
            error={errors.title}
          >
            <Input
              id="task-title"
              value={form.title}
              onChange={(event) =>
                updateField('title', event.target.value)
              }
              placeholder="Örn. Elektrik tesisatı"
              maxLength={250}
              invalid={Boolean(errors.title)}
              autoFocus
            />
          </Field>
        </div>

        <Field
          label="Açıklama"
          htmlFor="task-description"
          error={errors.description}
          hint="İsteğe bağlı."
        >
          <Textarea
            id="task-description"
            value={form.description}
            onChange={(event) =>
              updateField('description', event.target.value)
            }
            placeholder="Görevin kapsamı ve notlar"
            maxLength={8000}
            rows={3}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Planlanan başlangıç"
            htmlFor="task-start"
            error={errors.plannedStartDate}
            hint="Haftanın günü veritabanında otomatik hesaplanır."
          >
            <Input
              id="task-start"
              type="date"
              value={form.plannedStartDate}
              onChange={(event) =>
                updateField('plannedStartDate', event.target.value)
              }
            />
          </Field>

          <Field
            label="Planlanan bitiş"
            htmlFor="task-due"
            error={errors.plannedDueDate}
            hint="Haftanın günü veritabanında otomatik hesaplanır."
          >
            <Input
              id="task-due"
              type="date"
              value={form.plannedDueDate}
              onChange={(event) =>
                updateField('plannedDueDate', event.target.value)
              }
            />
          </Field>
        </div>

        {task ? (
          <div className="flex flex-wrap gap-2 text-xs text-slate-500">
            {task.planned_start_weekday ? (
              <Badge tone="info">
                Başlangıç günü: {task.planned_start_weekday}
              </Badge>
            ) : null}
            {task.planned_due_weekday ? (
              <Badge tone="info">
                Bitiş günü: {task.planned_due_weekday}
              </Badge>
            ) : null}
          </div>
        ) : null}

        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-700">
                Çalışan atamaları
              </p>
              <p className="text-xs text-slate-500">
                Bir göreve birden fazla çalışan atanabilir. Pasif
                çalışanlar yeni atanamaz.
              </p>
            </div>
            <span className="inline-flex items-center gap-1 text-xs text-slate-500">
              <Users className="h-3.5 w-3.5" aria-hidden="true" />
              {employeeIds.length} seçili
            </span>
          </div>

          {employeesQuery.isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="h-12 animate-pulse rounded-lg bg-slate-100"
                />
              ))}
            </div>
          ) : employees.length === 0 ? (
            <Alert tone="info">
              Henüz çalışan kaydı yok. Çalışanlar Telegram onayıyla
              eklendikten sonra burada görünür.
            </Alert>
          ) : (
            <div className="grid max-h-56 gap-2 overflow-y-auto rounded-lg border border-slate-200 p-2 sm:grid-cols-2">
              {employees.map((employee) => {
                const isAssigned = currentAssignedIds.includes(
                  employee.id,
                )
                const disabled = !employee.is_active && !isAssigned

                return (
                  <Checkbox
                    key={employee.id}
                    id={`task-employee-${employee.id}`}
                    label={employee.full_name}
                    description={
                      disabled
                        ? 'Pasif · yeni atanamaz'
                        : employee.role ??
                          (employee.is_active ? 'Aktif' : 'Pasif')
                    }
                    checked={employeeIds.includes(employee.id)}
                    disabled={disabled}
                    onChange={() => toggleEmployee(employee.id)}
                    className={cn(
                      employeeIds.includes(employee.id) &&
                        'border-worktrack-blue/40 bg-worktrack-blue/5',
                    )}
                  />
                )
              })}
            </div>
          )}

          <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1">
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
              {activeCount} aktif çalışan
            </span>
            {errors.employees ? (
              <span className="text-red-600">{errors.employees}</span>
            ) : null}
          </div>
        </div>

        {task && employeeIds.some((employeeId) => {
          const employee = employees.find(
            (item) => item.id === employeeId,
          )
          return employee && !employee.is_active
        }) ? (
          <p className="flex items-start gap-1.5 text-xs text-amber-700">
            <AlertTriangle
              className="mt-0.5 h-3.5 w-3.5 shrink-0"
              aria-hidden="true"
            />
            Mevcut pasif atamalar korunuyor. Kaldırmak için ilgili
            çalışanın işaretini kaldırın.
          </p>
        ) : null}
      </form>
    </Modal>
  )
}

function mapServerErrors(
  fieldErrors: Record<string, string>,
): FormErrors {
  const result: FormErrors = {}

  if (fieldErrors.title) result.title = fieldErrors.title
  if (fieldErrors.description) {
    result.description = fieldErrors.description
  }
  if (fieldErrors.project_id) {
    result.projectId = fieldErrors.project_id
  }
  if (fieldErrors.planned_start_date) {
    result.plannedStartDate = fieldErrors.planned_start_date
  }
  if (fieldErrors.planned_due_date) {
    result.plannedDueDate = fieldErrors.planned_due_date
  }
  if (fieldErrors.employee_ids) {
    result.employees = fieldErrors.employee_ids
  }

  return result
}
