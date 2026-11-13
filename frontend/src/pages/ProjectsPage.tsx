import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  FolderKanban,
  MapPin,
  Pencil,
  Plus,
} from 'lucide-react'
import { useDeferredValue, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { projectsApi } from '../api/endpoints'
import { ProjectDeleteDialog } from '../components/projects/ProjectDeleteDialog'
import { ProjectFormDialog } from '../components/projects/ProjectFormDialog'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { DeleteButton } from '../components/ui/DeleteButton'
import { EmptyState } from '../components/ui/EmptyState'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingState } from '../components/ui/LoadingState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { SearchInput } from '../components/ui/SearchInput'
import { formatDate, getErrorMessage } from '../lib/utils'
import type { Project } from '../types'

const PAGE_SIZE = 10

export function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [page, setPage] = useState(1)
  const [formOpen, setFormOpen] = useState(false)
  const [editingProject, setEditingProject] =
    useState<Project | null>(null)
  const [deletingProject, setDeletingProject] =
    useState<Project | null>(null)

  const projectsQuery = useQuery({
    queryKey: ['projects', 'list', page, deferredSearch],
    queryFn: () =>
      projectsApi.list({
        page,
        page_size: PAGE_SIZE,
        search: deferredSearch.trim() || undefined,
      }),
  })

  useEffect(() => {
    if (searchParams.get('yeni') === '1') {
      setEditingProject(null)
      setFormOpen(true)
    }
  }, [searchParams])

  const closeForm = () => {
    setFormOpen(false)
    setEditingProject(null)
    if (searchParams.has('yeni')) {
      const next = new URLSearchParams(searchParams)
      next.delete('yeni')
      setSearchParams(next, { replace: true })
    }
  }

  const openCreate = () => {
    setEditingProject(null)
    setFormOpen(true)
  }

  const openEdit = (project: Project) => {
    setEditingProject(project)
    setFormOpen(true)
  }

  const data = projectsQuery.data
  const hasSearch = deferredSearch.trim().length > 0

  return (
    <div className="space-y-5">
      <PageHeader
        title="Projeler"
        description="Projeleri oluşturun, arayın ve ekiplerini görev atamaları üzerinden görüntüleyin."
        actions={
          <Button
            onClick={openCreate}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Yeni proje
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <SearchInput
          value={search}
          onChange={(value) => {
            setSearch(value)
            setPage(1)
          }}
          placeholder="Proje adı, konum veya açıklama ara"
        />
        {data ? (
          <p className="text-sm text-slate-500">
            {data.total} proje
          </p>
        ) : null}
      </div>

      {projectsQuery.isLoading ? (
        <LoadingState rows={5} />
      ) : projectsQuery.isError ? (
        <Card>
          <ErrorState
            message={getErrorMessage(projectsQuery.error)}
            onRetry={() => void projectsQuery.refetch()}
          />
        </Card>
      ) : data && data.items.length === 0 ? (
        <Card>
          {hasSearch ? (
            <EmptyState
              icon={FolderKanban}
              title="Arama sonucu bulunamadı"
              description="Farklı bir proje adı, konum veya açıklama ile tekrar arayın."
              action={
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch('')
                    setPage(1)
                  }}
                >
                  Aramayı temizle
                </Button>
              }
            />
          ) : (
            <EmptyState
              icon={FolderKanban}
              title="Henüz proje oluşturulmadı"
              description="İlk projeyi oluşturarak görevleri, çalışan atamalarını ve haftalık planları planlamaya başlayın. Proje, görev eklenmeden de var olabilir."
              action={
                <Button
                  onClick={openCreate}
                  leftIcon={<Plus className="h-4 w-4" />}
                >
                  İlk Projeyi Oluştur
                </Button>
              }
            />
          )}
        </Card>
      ) : data ? (
        <>
          <div className="table-shell">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col">Proje</th>
                  <th scope="col">Konum</th>
                  <th scope="col">Beklenen Tamamlanma</th>
                  <th scope="col">Görev</th>
                  <th scope="col">Ekip</th>
                  <th scope="col">Oluşturma</th>
                  <th scope="col" className="text-right">
                    İşlem
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <div className="min-w-0">
                        <Link
                          to={`/projeler/${project.id}`}
                          className="font-medium text-worktrack-ink hover:text-worktrack-blue hover:underline"
                        >
                          {project.name}
                        </Link>
                        {project.description ? (
                          <p className="mt-0.5 line-clamp-1 max-w-xs text-xs text-slate-500">
                            {project.description}
                          </p>
                        ) : null}
                      </div>
                    </td>
                    <td>
                      {project.location ? (
                        <span className="inline-flex items-center gap-1 text-slate-600">
                          <MapPin
                            className="h-3.5 w-3.5 text-slate-400"
                            aria-hidden="true"
                          />
                          {project.location}
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                    <td className="text-slate-600">
                      {formatDate(project.expected_completion_date)}
                    </td>
                    <td>{project.task_count}</td>
                    <td>{project.employee_count}</td>
                    <td className="text-slate-500">
                      {formatDate(project.created_at)}
                    </td>
                    <td>
                      <div className="flex items-center justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(project)}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                          aria-label={`${project.name} projesini düzenle`}
                          title="Düzenle"
                        >
                          <Pencil
                            className="h-4 w-4"
                            aria-hidden="true"
                          />
                        </button>
                        <Link
                          to={`/projeler/${project.id}`}
                          className="rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-worktrack-blue"
                          aria-label={`${project.name} proje detayını aç`}
                          title="Detay"
                        >
                          <ArrowRight
                            className="h-4 w-4"
                            aria-hidden="true"
                          />
                        </Link>
                        <DeleteButton
                          label={`${project.name} projesini sil`}
                          onClick={() => setDeletingProject(project)}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <Pagination
            page={data.page}
            pages={data.pages}
            total={data.total}
            onPageChange={setPage}
          />
        </>
      ) : null}

      <ProjectFormDialog
        open={formOpen}
        onClose={closeForm}
        project={editingProject}
      />

      <ProjectDeleteDialog
        open={deletingProject !== null}
        projectId={deletingProject?.id ?? null}
        projectName={deletingProject?.name ?? ''}
        onClose={() => setDeletingProject(null)}
      />
    </div>
  )
}
