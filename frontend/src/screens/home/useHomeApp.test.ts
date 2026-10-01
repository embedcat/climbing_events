import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { rememberParticipant } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import { fakeSiteApi, makeCard, makeCatalog, makeParticipation, networkError } from './testing'
import { useHomeApp } from './useHomeApp'

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

const person = { id: 7, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 }

describe('каталог на главной', () => {
  it('первая страница из HTML показывается сразу, без запроса', async () => {
    const api = fakeSiteApi()
    const app = useHomeApp({ api, store: memoryStore(), initial: makeCatalog({ counts: { upcoming: 3, past: 9 } }) })
    expect(app.status).toBe('ready')
    expect(app.counts).toEqual({ upcoming: 3, past: 9 })
    await app.init()
    expect(api.events).not.toHaveBeenCalled()
  })

  it('без готовых данных запрашивает первую страницу сам', async () => {
    const api = fakeSiteApi()
    const app = useHomeApp({ api, store: memoryStore() })
    expect(app.status).toBe('loading')
    await app.init()
    expect(api.events).toHaveBeenCalledWith({ query: '', when: 'upcoming', offset: 0 })
    expect(app.status).toBe('ready')
    expect(app.cards).toHaveLength(1)
  })

  it('ошибка загрузки: статус «ошибка» с текстом, повтор приводит в порядок', async () => {
    const api = fakeSiteApi({ events: vi.fn().mockRejectedValueOnce(networkError()).mockResolvedValue(makeCatalog()) })
    const app = useHomeApp({ api, store: memoryStore() })
    await app.init()
    expect(app.status).toBe('error')
    expect(app.errorMessage).toBe('Нет связи с сервером.')
    await app.load()
    expect(app.status).toBe('ready')
    expect(app.errorMessage).toBe('')
  })

  it('«Прошедшие» запрашивает другой период, тот же выбор повторно не грузит', async () => {
    const api = fakeSiteApi()
    const app = useHomeApp({ api, store: memoryStore(), initial: makeCatalog() })
    app.setWhen('upcoming')
    expect(api.events).not.toHaveBeenCalled()
    app.setWhen('past')
    await flushPromises()
    expect(api.events).toHaveBeenCalledWith({ query: '', when: 'past', offset: 0 })
  })

  it('поиск ждёт паузу в наборе и ищет по последнему тексту', async () => {
    const api = fakeSiteApi()
    const app = useHomeApp({ api, store: memoryStore(), initial: makeCatalog() })
    app.setQuery('о')
    app.setQuery('осен')
    app.setQuery('осенний')
    expect(api.events).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(250)
    expect(api.events).toHaveBeenCalledTimes(1)
    expect(api.events).toHaveBeenCalledWith({ query: 'осенний', when: 'upcoming', offset: 0 })
  })

  it('поздний ответ на старый запрос не затирает свежий', async () => {
    let finishFirst: (value: ReturnType<typeof makeCatalog>) => void = () => {}
    const api = fakeSiteApi({
      events: vi.fn()
        .mockReturnValueOnce(new Promise((resolve) => { finishFirst = resolve }))
        .mockResolvedValueOnce(makeCatalog({ results: [makeCard({ id: 2, title: 'Свежий' })] })),
    })
    const app = useHomeApp({ api, store: memoryStore(), initial: makeCatalog() })
    app.setQuery('а')
    await vi.advanceTimersByTimeAsync(250)
    app.setQuery('аб')
    await vi.advanceTimersByTimeAsync(250)
    expect(app.cards.map((c) => c.title)).toEqual(['Свежий'])
    finishFirst(makeCatalog({ results: [makeCard({ id: 1, title: 'Старый' })] }))
    await flushPromises()
    expect(app.cards.map((c) => c.title)).toEqual(['Свежий'])
    expect(app.busy).toBe(false)
  })

  it('«Показать ещё» дописывает карточки со смещением по числу уже показанных', async () => {
    const api = fakeSiteApi({
      events: vi.fn().mockResolvedValue(makeCatalog({ results: [makeCard({ id: 3, title: 'Третье' })], has_more: false })),
    })
    const app = useHomeApp({
      api, store: memoryStore(),
      initial: makeCatalog({ results: [makeCard({ id: 1 }), makeCard({ id: 2 })], has_more: true }),
    })
    await app.loadMore()
    expect(api.events).toHaveBeenCalledWith({ query: '', when: 'upcoming', offset: 2 })
    expect(app.cards.map((c) => c.id)).toEqual([1, 2, 3])
    expect(app.hasMore).toBe(false)
    await app.loadMore()
    expect(api.events).toHaveBeenCalledTimes(1)
  })

  it('«Показать ещё» при ошибке оставляет список и пишет причину', async () => {
    const api = fakeSiteApi({ events: vi.fn().mockRejectedValue(networkError()) })
    const app = useHomeApp({ api, store: memoryStore(), initial: makeCatalog({ has_more: true }) })
    await app.loadMore()
    expect(app.cards).toHaveLength(1)
    expect(app.status).toBe('ready')
    expect(app.errorMessage).toBe('Нет связи с сервером.')
    expect(app.loadingMore).toBe(false)
  })

  it('выключенный экран не доводит отложенный поиск до запроса', async () => {
    const api = fakeSiteApi()
    const app = useHomeApp({ api, store: memoryStore(), initial: makeCatalog() })
    app.setQuery('осенний')
    app.dispose()
    await vi.advanceTimersByTimeAsync(1000)
    expect(api.events).not.toHaveBeenCalled()
  })
})

describe('«Вы участвуете»', () => {
  it('браузер никого не помнит: запроса нет', async () => {
    const api = fakeSiteApi()
    await useHomeApp({ api, store: memoryStore(), initial: makeCatalog() }).init()
    expect(api.participations).not.toHaveBeenCalled()
  })

  it('отправляет записи браузера и собирает строки', async () => {
    const store = memoryStore()
    rememberParticipant(store, 128, person)
    rememberParticipant(store, 105, { ...person, id: undefined })
    const api = fakeSiteApi({
      participations: vi.fn(async () => [makeParticipation(), makeParticipation({ event: makeCard({ id: 105, title: 'Камень' }), me: null })]),
    })
    const app = useHomeApp({ api, store, initial: makeCatalog() })
    await app.init()
    expect(api.participations).toHaveBeenCalledWith([{ eventId: 128, participantId: 7 }, { eventId: 105, participantId: undefined }])
    expect(app.rows.map((r) => [r.id, r.note])).toEqual([
      [128, 'Зайцева Юлия · Сет 3, 16:00 · взнос не оплачен'],
      [105, 'Зайцева Юлия'],
    ])
  })

  it('сбой запроса прячет блок, а не ломает главную', async () => {
    const store = memoryStore()
    rememberParticipant(store, 128, person)
    const api = fakeSiteApi({ participations: vi.fn().mockRejectedValue(networkError()) })
    const app = useHomeApp({ api, store, initial: makeCatalog() })
    await app.init()
    expect(app.rows).toEqual([])
    expect(app.status).toBe('ready')
  })
})
