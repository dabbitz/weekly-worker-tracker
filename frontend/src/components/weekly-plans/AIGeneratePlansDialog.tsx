import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Sparkles, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { tasksApi, weeklyPlansApi } from '../../api/endpoints'
import { getErrorMessage } from '../../lib/utils'
import type { AIPlanGenerateResponse } from '../../types'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Field, Textarea } from '../ui/Form'
import { LoadingState } from '../ui/LoadingState'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'


interface AIGeneratePlansDialogProps {
  open: boolean
  taskIds: number[]
  onClose: () => void
  onGenerated?: (response: AIPlanGenerateResponse) => void
}

function createRequestId(): string {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID()
  }

  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function AIGeneratePlansDialog({
  open,
  taskIds,
  onClose,
  onGenerated,
}: AIGeneratePlansDialogProps) {
  const [instructions, setInstructions] = useState('')
  const [requestId] = useState(createRequestId)
  const [serverError, setServerError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  const sortedIds = [...taskIds].sort((first, second) => first - second)
  const taskIdsKey = sortedIds.join(',')

  const tasksQuery = useQuery({
    queryKey: ['tasks', 'ai-generation', taskIdsKey],
    queryFn: () => Promise.all(sortedIds.map((id) => tasksApi.get(id))),
    enabled: open && sortedIds.length > 0,
  })

  const mutation = useMutation({
    mutationFn: () =>
      weeklyPlansApi.generateAi({
        task_ids: sortedIds,
        extra_instructions: instructions.trim() || null,
        request_id: requestId,
      }),
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['weekly-plans'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      showToast(
        `${response.plan_count} haftalık taslak oluşturuldu. ` +
          'Taslakları inceleyip onaylamanız gerekiyor.',
        'success',
      )
      onGenerated?.(response)
      onClose()
    },
    onError: (error) => {
      setServerError(getErrorMessage(error))
    },
  })

  const tasks = tasksQuery.data ?? []
  const missingDates = tasks.filter(
    (task) => !task.planned_start_date || !task.planned_due_date,
  )
  const missingDescriptions = tasks.filter(
    (task) => !task.description || !task.description.trim(),
  )
  const canGenerate =
    tasks.length > 0 &&
    missingDates.length === 0 &&
    !tasksQuery.isLoading &&
    !mutation.isPending

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="AI ile haftalık plan oluştur"
      description="Seçilen görevler için taslak haftalık hedefler üretilir. Hiçbir plan siz onaylamadan resmî plan sayılmaz."
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
            onClick={() => mutation.mutate()}
            isLoading={mutation.isPending}
            disabled={!canGenerate}
            leftIcon={<Sparkles className="h-4 w-4" />}
          >
            {mutation.isPending
              ? 'AI planı oluşturuyor...'
              : 'Taslakları oluştur'}
          </Button>
        </>
      }
    >
      <div className="space-y-5">
        {serverError ? (
          <Alert tone="error" title="AI planı oluşturulamadı">
            {serverError}
          </Alert>
        ) : null}

        {missingDates.length > 0 ? (
          <Alert tone="warning" title="Görev tarihleri eksik">
            AI planı için planlanan başlangıç ve bitiş tarihleri
            zorunludur. Şu görevlerin tarihlerini tamamlayın:{' '}
            {missingDates.map((task) => task.title).join(', ')}.
          </Alert>
        ) : null}

        {missingDescriptions.length > 0 ? (
          <Alert tone="info" title="Bazı görev açıklamaları eksik">
            {missingDescriptions
              .map((task) => task.title)
              .join(', ')}{' '}
            için açıklama yok. AI daha genel varsayımlar yapabilir; bu
            varsayımlar taslaklarda ayrıca gösterilir.
          </Alert>
        ) : null}

        <div>
          <p className="text-sm font-semibold text-worktrack-ink">
            Seçilen görevler ({sortedIds.length})
          </p>

          {tasksQuery.isLoading ? (
            <div className="mt-3">
              <LoadingState rows={3} />
            </div>
          ) : tasksQuery.isError ? (
            <Alert tone="error" className="mt-3">
              {getErrorMessage(tasksQuery.error)}
            </Alert>
          ) : tasks.length === 0 ? (
            <Alert tone="warning" className="mt-3">
              Plan oluşturmak için en az bir görev seçmelisiniz.
            </Alert>
          ) : (
            <ul className="mt-3 space-y-2">
              {tasks.map((task) => (
                <li
                  key={task.id}
                  className="rounded-lg border border-worktrack-line bg-slate-50/60 px-3 py-2.5"
                >
                  <p className="text-sm font-medium text-worktrack-ink">
                    {task.title}
                  </p>
                  <p className="text-xs text-slate-500">
                    {task.project_name}
                  </p>
                  <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                    <CalendarDays
                      className="h-3.5 w-3.5 text-slate-400"
                      aria-hidden="true"
                    />
                    {task.planned_start_date ?? 'Başlangıç yok'} —{' '}
                    {task.planned_due_date ?? 'Bitiş yok'}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {task.assigned_employees.length > 0
                      ? `Atanan çalışanlar: ${task.assigned_employees
                          .map((employee) => employee.full_name)
                          .join(', ')}`
                      : 'Bu göreve atanmış çalışan yok.'}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>

        <Field
          label="AI için ek talimatlar"
          htmlFor="ai-plan-instructions"
          hint="İsteğe bağlı. Örn. “Önce altyapı işlerini tamamla, testleri son haftaya bırak.”"
        >
          <Textarea
            id="ai-plan-instructions"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            rows={4}
            maxLength={4000}
            placeholder="Planlamada dikkate alınmasını istediğiniz öncelikleri yazın."
            disabled={mutation.isPending}
          />
        </Field>

        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-800">
          <TriangleAlert
            className="mt-0.5 h-4 w-4 shrink-0"
            aria-hidden="true"
          />
          <p>
            Görev bağımlılıkları ve çalışan kapasitesi bu sistemde
            tutulmuyorsa AI bunları bilmez. Taslaklardaki varsayım ve
            uyarıları mutlaka inceleyin. Hedef yüzdeleri haftalık artış
            değil, hafta sonunda beklenen toplam tamamlanmadır.
          </p>
        </div>
      </div>
    </Modal>
  )
}
