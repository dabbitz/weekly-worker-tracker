import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { projectsApi } from '../../api/endpoints'
import { getErrorMessage } from '../../lib/utils'
import { Alert } from '../ui/Alert'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { useToast } from '../ui/Toast'

interface ProjectDeleteDialogProps {
  open: boolean
  projectId: number | null
  projectName: string
  onClose: () => void
  onDeleted?: () => void
}

export function ProjectDeleteDialog({
  open,
  projectId,
  projectName,
  onClose,
  onDeleted,
}: ProjectDeleteDialogProps) {
  const queryClient = useQueryClient()
  const { showToast } = useToast()
  const [typedName, setTypedName] = useState('')

  useEffect(() => {
    if (!open) {
      setTypedName('')
    }
  }, [open])

  const previewQuery = useQuery({
    queryKey: ['projects', 'deletion-preview', projectId],
    queryFn: () => projectsApi.deletionPreview(projectId as number),
    enabled: open && projectId !== null,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => projectsApi.remove(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] })
      void queryClient.invalidateQueries({ queryKey: ['tasks'] })
      void queryClient.invalidateQueries({ queryKey: ['weekly-plans'] })
      void queryClient.invalidateQueries({ queryKey: ['employees'] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      showToast('Proje silindi.', 'success')
      setTypedName('')
      onClose()
      onDeleted?.()
    },
    onError: (error) => {
      showToast(getErrorMessage(error), 'error')
    },
  })

  const preview = previewQuery.data
  const hasReports = (preview?.report_count ?? 0) > 0
  const nameMatches = typedName === projectName
  const confirmDisabled =
    !preview ||
    hasReports ||
    !nameMatches ||
    previewQuery.isLoading ||
    deleteMutation.isPending

  const handleClose = () => {
    if (!deleteMutation.isPending) {
      setTypedName('')
      onClose()
    }
  }

  const handleConfirm = () => {
    if (confirmDisabled || projectId === null) {
      return
    }
    deleteMutation.mutate(projectId)
  }

  return (
    <ConfirmDialog
      open={open}
      title="Projeyi sil"
      description={
        <>
          <p>
            <strong className="text-worktrack-ink">{projectName}</strong>{' '}
            projesi kalıcı olarak silinecek.
          </p>
          <p>
            Bu işlem geri alınamaz. Projeye bağlı görevler, görev
            atamaları ve haftalık planlar da silinir; çalışan kayıtları
            korunur.
          </p>
        </>
      }
      confirmLabel="Projeyi sil"
      tone="danger"
      isLoading={deleteMutation.isPending}
      confirmDisabled={confirmDisabled}
      onConfirm={handleConfirm}
      onClose={handleClose}
    >
      {previewQuery.isLoading ? (
        <p className="text-sm text-slate-500">
          Etkilenecek kayıtlar hesaplanıyor…
        </p>
      ) : previewQuery.isError ? (
        <Alert tone="error" title="Silme önizlemesi alınamadı">
          {getErrorMessage(previewQuery.error)}
        </Alert>
      ) : preview ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2 rounded-lg border border-worktrack-line bg-slate-50 px-3 py-2.5 text-center">
            <div>
              <p className="text-lg font-semibold text-worktrack-ink">
                {preview.task_count}
              </p>
              <p className="text-xs text-slate-500">Görev</p>
            </div>
            <div>
              <p className="text-lg font-semibold text-worktrack-ink">
                {preview.assignment_count}
              </p>
              <p className="text-xs text-slate-500">Atama</p>
            </div>
            <div>
              <p className="text-lg font-semibold text-worktrack-ink">
                {preview.weekly_plan_count}
              </p>
              <p className="text-xs text-slate-500">Haftalık plan</p>
            </div>
          </div>

          {hasReports ? (
            <Alert tone="error" title="Silme engellendi">
              Bu projeye bağlı {preview.report_count} iş raporu var.
              Rapor geçmişinin korunması için önce ilgili raporları
              silmelisiniz.
            </Alert>
          ) : null}

          <div>
            <label
              htmlFor="project-delete-confirmation"
              className="block text-sm font-medium text-slate-700"
            >
              Onaylamak için proje adını yazın:{' '}
              <span className="font-semibold text-worktrack-ink">
                {projectName}
              </span>
            </label>
            <input
              id="project-delete-confirmation"
              type="text"
              value={typedName}
              onChange={(event) => setTypedName(event.target.value)}
              className="field-input mt-1.5"
              autoComplete="off"
              spellCheck={false}
              disabled={hasReports || deleteMutation.isPending}
            />
          </div>
        </div>
      ) : null}
    </ConfirmDialog>
  )
}
