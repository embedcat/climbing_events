// Тонкая обёртка над fetch для `/api/`. Сайт и API на одном домене, поэтому сессия и CSRF работают как в Django.

export type ApiErrorCode = string

/** Ошибка запроса. status 0 — сервер не ответил (нет связи, таймаут). */
export class ApiError extends Error {
  readonly status: number
  readonly code: ApiErrorCode
  readonly body: Record<string, unknown>

  constructor(status: number, code: ApiErrorCode, message: string, body: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.body = body
  }

  get isNetwork(): boolean {
    return this.status === 0
  }
}

const UNKNOWN_MESSAGE = 'Что-то пошло не так. Попробуйте ещё раз.'

/** Любую пойманную ошибку приводит к ApiError: неожиданные (баги) показываем как общий сбой, а не как «нет связи». */
export function asApiError(error: unknown): ApiError {
  return error instanceof ApiError ? error : new ApiError(-1, 'unknown', UNKNOWN_MESSAGE)
}

export interface HttpOptions {
  csrfToken?: string
  timeoutMs?: number
  fetchImpl?: typeof fetch
}

export interface Http {
  get<T>(url: string): Promise<T>
  post<T>(url: string, body: unknown): Promise<T>
}

const NETWORK_MESSAGE = 'Нет связи с сервером.'

export function createHttp(options: HttpOptions = {}): Http {
  const { csrfToken = '', timeoutMs = 20000, fetchImpl } = options

  async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
    const doFetch = fetchImpl ?? fetch
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    let response: Response
    try {
      response = await doFetch(url, {
        method,
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
          ...(csrfToken ? { 'X-CSRFToken': csrfToken } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })
    } catch {
      throw new ApiError(0, 'network', NETWORK_MESSAGE)
    } finally {
      clearTimeout(timer)
    }

    let data: Record<string, unknown> = {}
    try {
      data = await response.json()
    } catch {
      /* ответ не JSON: страница ошибки прокси и т. п. */
    }
    if (!response.ok) {
      const code = typeof data.code === 'string' ? data.code : response.status >= 500 ? 'server' : 'error'
      const message = typeof data.error === 'string' ? data.error
        : response.status >= 500 ? 'Сервер временно недоступен. Попробуйте ещё раз.' : 'Запрос не выполнен.'
      throw new ApiError(response.status, code, message, data)
    }
    return data as T
  }

  return {
    get: (url) => request('GET', url),
    post: (url, body) => request('POST', url, body),
  }
}
