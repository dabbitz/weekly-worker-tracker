import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type FormEvent } from 'react'

import { projectsApi } from '../../api/endpoints'
import { ApiError } from '../../api/client'
import { Alert } from '../ui/Alert'
import { Button } from '../ui/Button'
import { Field, Input, Textarea } from '../ui/Form'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'
import { getErrorMessage } from '../../lib/utils'
import type { Project, ProjectPayload } from '../../types'

interface ProjectFormDialogProps {
  open: boolean
  onClose: () => void
  project?: Project | null
}

interface FormState {
  name: string
  description: string
  location: string
  expectedCompletionDate: string
}

type FormErrors = Partial<Record<keyof FormState, string>>

const emptyForm: FormState = {
  name: '',
  description: '',
  location: '',
  expectedCompletionDate: '',
}

export function ProjectFormDialog({
  open,
  onClose,
  project = null,
}: ProjectFormDialogProps) {
  const [form, setForm] = useState<FormState>(emptyForm)
  const [errors, setErrors] = useState<FormErrors>({})
  const [serverError, setServerError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { showToast } = useToast()

  useEffect(() => {
    if (!open) {
      return
    }

    setErrors({})
    setServerError(null)

    if (project) {
      setForm({
        name: project.name,
        description: project.description ?? '',
        location: project.location ?? '',
        expectedCompletionDate:
          project.expected_completion_date ?? '',
      })
    } else {
      setForm(emptyForm)
    }
  }, [open, project])

  const mutation = useMutation({
    mutationFn: (payload: ProjectPayload) =>
      project
        ? projectsApi.update(project.id, payload)
        : projectsApi.create(payload),
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      showToast(
        project ? 'Proje güncellendi.' : 'Proje oluşturuldu.',
        'success',
      )
      onClose()
      return saved
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

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setServerError(null)

    const nextErrors: FormErrors = {}
    const name = form.name.trim()

    if (!name) {
      nextErrors.name = 'Proje adı zorunludur.'
    } else if (name.length > 200) {
      nextErrors.name = 'Proje adı en fazla 200 karakter olabilir.'
    }

    if (form.location.trim().length > 200) {
      nextErrors.location = 'Konum en fazla 200 karakter olabilir.'
    }

    if (form.description.length > 4000) {
      nextErrors.description =
        'Açıklama en fazla 4000 karakter olabilir.'
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    mutation.mutate({
      name,
      description: form.description.trim() || null,
      location: form.location.trim() || null,
      expected_completion_date:
        form.expectedCompletionDate || null,
    })
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={project ? 'Projeyi Düzenle' : 'Yeni Proje'}
      description={
        project
          ? 'Proje bilgilerini güncelleyin.'
          : 'Projeyi görevler ve çalışan atamaları eklemeden önce oluşturabilirsiniz.'
      }
      size="md"
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
            form="project-form"
            isLoading={mutation.isPending}
          >
            {project ? 'Değişiklikleri kaydet' : 'Projeyi oluştur'}
          </Button>
        </>
      }
    >
      {serverError ? (
        <Alert tone="error" className="mb-4">
          {serverError}
        </Alert>
      ) : null}

      <form
        id="project-form"
        onSubmit={handleSubmit}
        noValidate
        className="space-y-4"
      >
        <Field
          label="Proje adı"
          htmlFor="project-name"
          required
          error={errors.name}
        >
          <Input
            id="project-name"
            value={form.name}
            onChange={(event) => updateField('name', event.target.value)}
            placeholder="Örn. Merkez Ofis Yenileme"
            maxLength={200}
            invalid={Boolean(errors.name)}
            autoFocus
          />
        </Field>

        <Field
          label="Açıklama"
          htmlFor="project-description"
          error={errors.description}
          hint="İsteğe bağlı. Projenin kapsamını kısaca açıklayın."
        >
          <Textarea
            id="project-description"
            value={form.description}
            onChange={(event) =>
              updateField('description', event.target.value)
            }
            placeholder="Proje kapsamı ve notlar"
            rows={4}
            maxLength={4000}
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Konum"
            htmlFor="project-location"
            error={errors.location}
          >
            <Input
              id="project-location"
              value={form.location}
              onChange={(event) =>
                updateField('location', event.target.value)
              }
              placeholder="Örn. İstanbul"
              maxLength={200}
            />
          </Field>

          <Field
            label="Beklenen tamamlanma tarihi"
            htmlFor="project-date"
            hint="İsteğe bağlı."
          >
            <Input
              id="project-date"
              type="date"
              value={form.expectedCompletionDate}
              onChange={(event) =>
                updateField('expectedCompletionDate', event.target.value)
              }
            />
          </Field>
        </div>
      </form>
    </Modal>
  )
}

function mapServerErrors(
  fieldErrors: Record<string, string>,
): FormErrors {
  const result: FormErrors = {}

  if (fieldErrors.name) result.name = fieldErrors.name
  if (fieldErrors.description) {
    result.description = fieldErrors.description
  }
  if (fieldErrors.location) result.location = fieldErrors.location

  return result
}
