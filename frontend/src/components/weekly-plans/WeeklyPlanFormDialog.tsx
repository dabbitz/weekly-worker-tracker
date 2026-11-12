import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { CalendarRange, Sparkles, Target } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { tasksApi, weeklyPlansApi } from '../../api/endpoints'
import { ApiError } from '../../api/client'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Field, Input, Select, Textarea } from '../ui/Form'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'
import {
  addDaysIso,
  getErrorMessage,
  todayIso,
} from '../../lib/utils'
import type { WeeklyPlan, WeeklyPlanPayload } from '../../types'

interface WeeklyPlanFormDialogProps {
  open: boolean
  onClose: () => void
  plan?: WeeklyPlan | null
  defaultTaskId?: number
}

interface FormState {
  taskId: string
  weekStart: string
  weekEnd: string
  targetDescription: string
  percentage: string
}

type FormErrors = Partial<Record<keyof FormState, string>>

function currentWeekStart(): string {
  const today = new Date(`${todayIso()}T00:00:00`)
  const offset = (today.getDay() + 6) % 7
  return addDaysIso(todayIso(), -offset)
}

function emptyForm(defaultTaskId?: number): FormState {
  const weekStart = currentWeekStart()

  return {
    taskId: defaultTaskId ? String(defaultTaskId) : '',
    weekStart,
    weekEnd: addDaysIso(weekStart, 6),
    targetDescription: '',
    percentage: '',
  }
}

export function WeeklyPlanFormDialog({
  open,
  onClose,
  plan = null,
  defaultTaskId,
}: WeeklyPlanFormDialogProps) {
  const [form, setForm] = useState<FormState>(emptyForm(defaultTaskId))
  const [errors, setErrors] = useState<FormErrors>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const tasksQuery = useQuery({
    queryKey: ['tasks', 'list', 'plan-options'],
    queryFn: () => tasksApi.list({ page: 1, page_size: 100 }),
    enabled: open,
  })

  useEffect(() => {
    if (!open) {
      return
    }

    setErrors({})
    setServerError(null)

    if (plan) {
      setForm({
        taskId: String(plan.task_id),
        weekStart: plan.week_start_date,
        weekEnd: plan.week_end_date,
        targetDescription: plan.target_description,
        percentage:
          plan.target_completion_percentage === null
            ? ''
            : String(plan.target_completion_percentage),
      })
    } else {
      setForm(emptyForm(defaultTaskId))
    }
  }, [open, plan, defaultTaskId])

  const mutation = useMutation({
    mutationFn: (payload: WeeklyPlanPayload) =>
      plan
        ? weeklyPlansApi.update(plan.id, payload)
        : weeklyPlansApi.create(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['weekly-plans'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['employees'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      showToast(
        plan ? 'Haftalık plan güncellendi.' : 'Haftalık plan oluşturuldu.',
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

  const tasks = useMemo(() => {
    const items = tasksQuery.data?.items ?? []

    if (plan && !items.some((task) => task.id === plan.task_id)) {
      return [
        {
          id: plan.task_id,
          title: plan.task_title,
          project_name: plan.project_name,
          project_id: plan.project_id,
        },
        ...items,
      ]
    }

    return items
  }, [tasksQuery.data, plan])

  const updateField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  const updateWeekStart = (value: string) => {
    setForm((current) => {
      const next = { ...current, weekStart: value }

      if (value) {
        const suggestedEnd = current.weekStart
          ? addDaysIso(current.weekStart, 6)
          : ''
        const shouldFollow =
          !current.weekEnd || current.weekEnd === suggestedEnd

        if (shouldFollow) {
          next.weekEnd = addDaysIso(value, 6)
        }
      }

      return next
    })
    setErrors((current) => ({
      ...current,
      weekStart: undefined,
      weekEnd: undefined,
    }))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setServerError(null)

    const nextErrors: FormErrors = {}
    const taskId = Number(form.taskId)
    const description = form.targetDescription.trim()
    const percentageValue = form.percentage.trim()

    if (!taskId) {
      nextErrors.taskId = 'Bir görev seçmelisiniz.'
    }

    if (!form.weekStart) {
      nextErrors.weekStart = 'Hafta başlangıç tarihi zorunludur.'
    }

    if (!form.weekEnd) {
      nextErrors.weekEnd = 'Hafta bitiş tarihi zorunludur.'
    }

    if (
      form.weekStart &&
      form.weekEnd &&
      form.weekEnd < form.weekStart
    ) {
      nextErrors.weekEnd =
        'Hafta bitiş tarihi, başlangıç tarihinden önce olamaz.'
    }

    if (!description) {
      nextErrors.targetDescription =
        'Haftalık hedef açıklaması zorunludur.'
    } else if (description.length > 4000) {
      nextErrors.targetDescription =
        'Hedef açıklaması en fazla 4000 karakter olabilir.'
    }

    let percentage: number | null = null

    if (percentageValue) {
      const parsed = Number(percentageValue)

      if (
        !Number.isInteger(parsed) ||
        parsed < 0 ||
        parsed > 100
      ) {
        nextErrors.percentage =
          'Tamamlanma yüzdesi 0 ile 100 arasında bir tam sayı olmalıdır.'
      } else {
        percentage = parsed
      }
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    mutation.mutate({
      task_id: taskId,
      week_start_date: form.weekStart,
      week_end_date: form.weekEnd,
      target_description: description,
      target_completion_percentage: percentage,
    })
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={plan ? 'Haftalık Planı Düzenle' : 'Yeni Haftalık Plan'}
      description={
        plan
          ? 'Haftalık hedefi ve tamamlanma yüzdesini güncelleyin.'
          : 'Bir görev için taslak haftalık hedef tanımlayın. Plan, onaylandığında resmî hedef olur.'
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
            form="weekly-plan-form"
            isLoading={mutation.isPending}
            disabled={tasksQuery.isLoading}
          >
            {plan ? 'Değişiklikleri kaydet' : 'Planı oluştur'}
          </Button>
        </>
      }
    >
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      {plan?.source === 'ai' &&
      (plan.ai_rationale || plan.ai_assumptions || plan.ai_warnings) ? (
        <div className="mb-4 space-y-2">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-worktrack-ink">
            <Sparkles
              className="h-4 w-4 text-worktrack-blue"
              aria-hidden="true"
            />
            AI plan notları
          </p>
          {plan.ai_rationale ? (
            <Alert tone="info" title="Gerekçe">
              <p className="whitespace-pre-line">{plan.ai_rationale}</p>
            </Alert>
          ) : null}
          {plan.ai_assumptions ? (
            <Alert tone="warning" title="Varsayımlar">
              <p className="whitespace-pre-line">
                {plan.ai_assumptions}
              </p>
            </Alert>
          ) : null}
          {plan.ai_warnings ? (
            <Alert tone="error" title="Uyarılar">
              <p className="whitespace-pre-line">
                {plan.ai_warnings}
              </p>
            </Alert>
          ) : null}
        </div>
      ) : null}

      {!tasksQuery.isLoading && tasks.length === 0 ? (
        <Alert
          tone="warning"
          title="Önce bir görev gerekli"
          className="mb-4"
        >
          Haftalık plan bir göreve bağlıdır. Önce bir proje ve görev
          oluşturun.{' '}
          <Link
            to="/gorevler?yeni=1"
            className="font-semibold underline underline-offset-2"
            onClick={onClose}
          >
            Görev oluştur
          </Link>
        </Alert>
      ) : null}

      <form
        id="weekly-plan-form"
        onSubmit={handleSubmit}
        noValidate
        className="space-y-4"
      >
        <Field
          label="Görev"
          htmlFor="plan-task"
          required
          error={errors.taskId}
        >
          <Select
            id="plan-task"
            value={form.taskId}
            onChange={(event) =>
              updateField('taskId', event.target.value)
            }
            invalid={Boolean(errors.taskId)}
            disabled={tasksQuery.isLoading}
          >
            <option value="">Görev seçin</option>
            {tasks.map((task) => (
              <option key={task.id} value={task.id}>
                {task.title} — {task.project_name}
              </option>
            ))}
          </Select>
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Hafta başlangıcı"
            htmlFor="plan-week-start"
            required
            error={errors.weekStart}
            hint="Bitiş tarihi boşsa başlangıçtan 6 gün sonrası önerilir."
          >
            <Input
              id="plan-week-start"
              type="date"
              value={form.weekStart}
              onChange={(event) => updateWeekStart(event.target.value)}
              invalid={Boolean(errors.weekStart)}
            />
          </Field>

          <Field
            label="Hafta bitişi"
            htmlFor="plan-week-end"
            required
            error={errors.weekEnd}
          >
            <Input
              id="plan-week-end"
              type="date"
              value={form.weekEnd}
              min={form.weekStart || undefined}
              onChange={(event) =>
                updateField('weekEnd', event.target.value)
              }
              invalid={Boolean(errors.weekEnd)}
            />
          </Field>
        </div>

        <Field
          label="Haftalık hedef açıklaması"
          htmlFor="plan-description"
          required
          error={errors.targetDescription}
          hint="Bu hafta tamamlanması beklenen işi tanımlayın."
        >
          <Textarea
            id="plan-description"
            value={form.targetDescription}
            onChange={(event) =>
              updateField('targetDescription', event.target.value)
            }
            placeholder="Örn. Zemin kat elektrik kablolama işinin %70'i tamamlanacak."
            maxLength={4000}
            rows={4}
            invalid={Boolean(errors.targetDescription)}
          />
        </Field>

        <Field
          label="Hedef tamamlanma yüzdesi"
          htmlFor="plan-percentage"
          error={errors.percentage}
          hint="İsteğe bağlı. 0 ile 100 arasında tam sayı girin."
        >
          <div className="relative sm:max-w-40">
            <Target
              className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <Input
              id="plan-percentage"
              type="number"
              inputMode="numeric"
              min={0}
              max={100}
              step={1}
              value={form.percentage}
              onChange={(event) =>
                updateField('percentage', event.target.value)
              }
              placeholder="0 - 100"
              className="pr-8 pl-9"
              invalid={Boolean(errors.percentage)}
            />
            <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-sm text-slate-400">
              %
            </span>
          </div>
        </Field>

        <p className="flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs leading-5 text-slate-500">
          <CalendarRange
            className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400"
            aria-hidden="true"
          />
          Manuel plan taslak olarak oluşturulur; onayladığınızda resmî
          haftalık hedef olur. Aynı görev ve hafta için tek manuel aktif
          plan bulunabilir. AI taslakları birden fazla sürüm olarak
          saklanabilir. Haftalık plan hedefleri, görevin planlanan
          başlangıç ve bitiş tarihlerinden ayrı tutulur.
        </p>
      </form>
    </Modal>
  )
}

function mapServerErrors(
  fieldErrors: Record<string, string>,
): FormErrors {
  const result: FormErrors = {}

  if (fieldErrors.task_id) result.taskId = fieldErrors.task_id
  if (fieldErrors.week_start_date) {
    result.weekStart = fieldErrors.week_start_date
  }
  if (fieldErrors.week_end_date) {
    result.weekEnd = fieldErrors.week_end_date
  }
  if (fieldErrors.target_description) {
    result.targetDescription = fieldErrors.target_description
  }
  if (fieldErrors.target_completion_percentage) {
    result.percentage = fieldErrors.target_completion_percentage
  }

  return result
}
