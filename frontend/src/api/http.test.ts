import { describe, expect, it, vi } from 'vitest'
import { createEntryApi } from './entry'
import { ApiError, createHttp } from './http'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('http', () => {
  it('шлёт JSON с CSRF-токеном и разбирает ответ', async () => {
    const fetchImpl = vi.fn(async () => json({ ok: true }))
    const http = createHttp({ csrfToken: 'tok', fetchImpl })
    await expect(http.post('/api/x/', { a: 1 })).resolves.toEqual({ ok: true })
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/x/')
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('same-origin')
    expect(init.body).toBe('{"a":1}')
    expect(init.headers).toMatchObject({ 'Content-Type': 'application/json', 'X-CSRFToken': 'tok' })
  })

  it('GET идёт без тела и без Content-Type', async () => {
    const fetchImpl = vi.fn(async () => json({}))
    await createHttp({ fetchImpl }).get('/api/x/')
    const init = (fetchImpl.mock.calls[0] as unknown as [string, RequestInit])[1]
    expect(init.body).toBeUndefined()
    expect(init.headers).not.toHaveProperty('Content-Type')
    expect(init.headers).not.toHaveProperty('X-CSRFToken')
  })

  it('ошибка API несёт код и сообщение сервера', async () => {
    const http = createHttp({ fetchImpl: async () => json({ error: 'PIN не найден', code: 'pin_not_found' }, 404) })
    const error = await http.post('/x', {}).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, code: 'pin_not_found', message: 'PIN не найден', isNetwork: false })
  })

  it('обрыв связи превращается в сетевую ошибку', async () => {
    const http = createHttp({ fetchImpl: async () => { throw new TypeError('Failed to fetch') } })
    const error = await http.get('/x').catch((e) => e)
    expect(error).toMatchObject({ status: 0, code: 'network', isNetwork: true })
  })

  it('зависший запрос обрывается по таймауту', async () => {
    const fetchImpl = vi.fn((_url: string, init: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init.signal!.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    const http = createHttp({ fetchImpl: fetchImpl as unknown as typeof fetch, timeoutMs: 10 })
    await expect(http.get('/x')).rejects.toMatchObject({ isNetwork: true })
  })

  it('страница ошибки прокси не ломает разбор', async () => {
    const http = createHttp({ fetchImpl: async () => new Response('<html>502</html>', { status: 502 }) })
    const error = await http.get('/x').catch((e) => e)
    expect(error).toMatchObject({ status: 502, code: 'server' })
    expect((error as ApiError).message).toMatch(/Сервер временно недоступен/)
  })
})

describe('entry api', () => {
  it('обращается к эндпоинтам события', async () => {
    const calls: Array<[string, unknown]> = []
    const http = {
      get: vi.fn(async (url: string) => { calls.push([url, undefined]); return {} }),
      post: vi.fn(async (url: string, body: unknown) => { calls.push([url, body]); return {} }),
    }
    const api = createEntryApi(http as never)
    await api.getConfig(7)
    await api.identify(7, '1234')
    await api.submit(7, '1234', [{ top: 2, zone: 0 }], false)
    await api.submitWithoutRegistration(7, { last_name: 'Зайцева' }, [{ top: 1, zone: 1 }], true)
    expect(calls).toEqual([
      ['/api/events/7/entry/config/', undefined],
      ['/api/events/7/entry/identify/', { pin: '1234' }],
      ['/api/events/7/entry/submit/', { pin: '1234', results: [{ top: 2 }] }],
      ['/api/events/7/entry/submit-without-registration/',
        { last_name: 'Зайцева', results: [{ top: 1, zone: 1 }] }],
    ])
  })
})
