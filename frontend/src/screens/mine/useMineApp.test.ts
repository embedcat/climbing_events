import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { fakeSiteApi, makeMyCard, makeMyEvents, networkError } from '../home/testing'
import { useMineApp } from './useMineApp'

const cards = () => [
  makeMyCard({ id: 1, stage: 'live' }),
  makeMyCard({ id: 2, stage: 'reg' }),
  makeMyCard({ id: 3, stage: 'draft' }),
  makeMyCard({ id: 4, stage: 'done' }),
]

describe('кабинет организатора', () => {
  it('готовый список из HTML показывается сразу, без запроса', async () => {
    const api = fakeSiteApi()
    const app = useMineApp({ api, initial: makeMyEvents({ results: cards() }) })
    await app.init()
    expect(api.myEvents).not.toHaveBeenCalled()
    expect(app.status).toBe('ready')
    expect(app.visible).toHaveLength(4)
  })

  it('без готового списка запрашивает его сам', async () => {
    const api = fakeSiteApi({ myEvents: vi.fn(async () => makeMyEvents({ results: cards() })) })
    const app = useMineApp({ api })
    expect(app.status).toBe('loading')
    await app.init()
    expect(api.myEvents).toHaveBeenCalledWith('mine')
    expect(app.cards).toHaveLength(4)
  })

  it('фильтры считают события по этапам', () => {
    const app = useMineApp({ api: fakeSiteApi(), initial: makeMyEvents({ results: cards() }) })
    expect(app.counts).toEqual({ all: 4, live: 1, soon: 2, done: 1 })
    app.setFilter('soon')
    expect(app.visible.map((c) => c.id)).toEqual([2, 3])
    app.setFilter('done')
    expect(app.visible.map((c) => c.id)).toEqual([4])
  })

  it('суперпользователь переключает «Мои» и «Все события сайта»', async () => {
    const api = fakeSiteApi({
      myEvents: vi.fn(async (scope) => makeMyEvents({ scope, is_superuser: true, results: scope === 'all' ? cards() : [makeMyCard()] })),
    })
    const app = useMineApp({ api, initial: makeMyEvents({ is_superuser: true }) })
    expect(app.isSuperuser).toBe(true)
    app.setScope('mine')
    expect(api.myEvents).not.toHaveBeenCalled()
    app.setScope('all')
    await flushPromises()
    expect(api.myEvents).toHaveBeenCalledWith('all')
    expect(app.scope).toBe('all')
    expect(app.cards).toHaveLength(4)
  })

  it('ошибка загрузки: статус и повтор', async () => {
    const api = fakeSiteApi({ myEvents: vi.fn().mockRejectedValueOnce(networkError()).mockResolvedValue(makeMyEvents()) })
    const app = useMineApp({ api })
    await app.init()
    expect(app.status).toBe('error')
    expect(app.errorMessage).toBe('Нет связи с сервером.')
    await app.load()
    expect(app.status).toBe('ready')
    expect(app.errorMessage).toBe('')
  })

  it('поздний ответ на прежний режим не затирает свежий', async () => {
    let finishMine: (value: ReturnType<typeof makeMyEvents>) => void = () => {}
    const api = fakeSiteApi({
      myEvents: vi.fn()
        .mockReturnValueOnce(new Promise((resolve) => { finishMine = resolve }))
        .mockResolvedValueOnce(makeMyEvents({ scope: 'all', is_superuser: true, results: cards() })),
    })
    const app = useMineApp({ api, initial: makeMyEvents({ is_superuser: true }) })
    void app.load()
    app.setScope('all')
    await flushPromises()
    finishMine(makeMyEvents({ results: [] }))
    await flushPromises()
    expect(app.cards).toHaveLength(4)
  })
})
