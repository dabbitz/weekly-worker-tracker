export class ApiError extends Error {
  readonly status: number
  readonly fieldErrors: Record<string, string>

  constructor(
    message: string,
    status: number,
    fieldErrors: Record<string, string> = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

interface ValidationErrorItem {
  field?: string | null
  message?: string
}

interface ErrorBody {
  detail?: string | unknown
  errors?: ValidationErrorItem[]
}

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api'
).replace(/\/+$/, '')

const TOKEN_KEY = 'worktrack_admin_token'

export const tokenStorage = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string): void {
    sessionStorage.setItem(TOKEN_KEY, token)
  },
  clear(): void {
    sessionStorage.removeItem(TOKEN_KEY)
  },
}

const UNAUTHORIZED_EVENT = 'worktrack:unauthorized'

export function notifyUnauthorized(): void {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
}

export function onUnauthorized(handler: () => void): () => void {
  window.addEventListener(UNAUTHORIZED_EVENT, handler)
  return () => window.removeEventListener(UNAUTHORIZED_EVENT, handler)
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  auth?: boolean
  signal?: AbortSignal
}

function extractFieldErrors(body: ErrorBody): Record<string, string> {
  const result: Record<string, string> = {}

  for (const item of body.errors ?? []) {
    if (item.field && item.message) {
      result[item.field] = item.message
    }
  }

  return result
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    method = 'GET',
    body,
    auth = true,
    signal,
  } = options

  const headers: Record<string, string> = {
    Accept: 'application/json',
  }

  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  if (auth) {
    const token = tokenStorage.get()
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }
  }

  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw error
    }
    throw new ApiError(
      'Sunucuya ulaşılamadı. Backend çalışıyor mu?',
      0,
    )
  }

  if (response.status === 204) {
    return undefined as T
  }

  const contentType = response.headers.get('content-type') ?? ''
  const parsed: unknown = contentType.includes('application/json')
    ? await response.json().catch(() => null)
    : null

  if (!response.ok) {
    if (response.status === 401 && auth) {
      notifyUnauthorized()
    }

    const errorBody = (parsed ?? {}) as ErrorBody
    const detail =
      typeof errorBody.detail === 'string'
        ? errorBody.detail
        : 'İşlem tamamlanamadı. Lütfen tekrar deneyin.'

    throw new ApiError(
      detail,
      response.status,
      extractFieldErrors(errorBody),
    )
  }

  return parsed as T
}

export function buildQuery(params: object): string {
  const search = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (
      typeof value !== 'string' &&
      typeof value !== 'number' &&
      typeof value !== 'boolean'
    ) {
      continue
    }
    if (value === '') {
      continue
    }
    search.set(key, String(value))
  }

  const query = search.toString()
  return query ? `?${query}` : ''
}

export { API_BASE_URL, request }
