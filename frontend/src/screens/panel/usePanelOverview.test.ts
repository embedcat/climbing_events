import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ApiError } from '../../api/http'
import type { PanelOverview } from '../../api/panel'
import { EVENT_ID, fakePanelApi, makeOverview } from './testing'
import { usePanelOverview } from './usePanelOverview'

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

const network = () => new ApiError(0, 'network', 'Нет связи с сервером.')

function setup(options: { overview?: PanelOverview, api?: ReturnType<typeof fakePanelApi>, isSuperuser?: boolean } = {}) {
  const api = options.api ?? fakePanelApi(options.overview)
  const navigate = vi.fn()
  const copy = vi.fn(async () => {})
  const app = usePanelOverview({ eventId: EVENT_ID, api, isSuperuser: options.isSuperuser, navigate, copy, origin: 'https://rockevents.ru' })
  return { app, api, navigate, copy }
}

describe('загрузка', () => {
  it('грузит обзор и показывает его', async () => {
    const { app, api } = setup()
    expect(app.status).toBe('loading')
    await app.load()
    expect(api.overview).toHaveBeenCalledWith(EVENT_ID)
    expect(app.status).toBe('ready')
    expect(app.overview?.title).toBe('Осенний фестиваль')
  })

  it('ошибка: статус и текст; повтор исправляет', async () => {
    const api = fakePanelApi(makeOverview(), { overview: vi.fn().mockRejectedValueOnce(network()).mockResolvedValue(makeOverview()) })
    const { app } = setup({ api })
    await app.load()
    expect(app.status).toBe('error')
    expect(app.errorMessage).toBe('Нет связи с сервером.')
    await app.load()
    expect(app.status).toBe('ready')
  })

  it('ошибка при обновлении не прячет уже показанный обзор', async () => {
    const api = fakePanelApi(makeOverview(), { overview: vi.fn().mockResolvedValueOnce(makeOverview()).mockRejectedValueOnce(network()) })
    const { app } = setup({ api })
    await app.load()
    await app.load()
    expect(app.status).toBe('ready')
    expect(app.overview).not.toBeNull()
  })

  it('числа и процент: внесли результат от числа участников', async () => {
    const { app } = setup({ overview: makeOverview({ participants_count: 40, entered_count: 10 }) })
    await app.load()
    expect(app.percent).toBe(25)
  })
})

describe('переключатели', () => {
  it('меняются сразу, на сервер уходит только нажатый, ответ обновляет этап', async () => {
    const fresh = makeOverview({ stage: 'live', flags: { is_published: true, is_registration_open: true, is_enter_result_allowed: true, is_results_allowed: true } })
    const api = fakePanelApi(makeOverview(), { setFlags: vi.fn(async () => fresh) })
    const { app } = setup({ api })
    await app.load()
    const done = app.toggle('is_enter_result_allowed')
    expect(app.flags.is_enter_result_allowed).toBe(true)
    expect(app.overview?.flags.is_enter_result_allowed).toBe(false)
    await done
    expect(api.setFlags).toHaveBeenCalledWith(EVENT_ID, { is_enter_result_allowed: true })
    expect(app.overview?.stage).toBe('live')
    expect(app.saving).toBe(0)
  })

  it('ошибка возвращает переключатель назад и пишет причину', async () => {
    const api = fakePanelApi(makeOverview(), { setFlags: vi.fn().mockRejectedValue(network()) })
    const { app } = setup({ api })
    await app.load()
    await app.toggle('is_published')
    expect(app.flags.is_published).toBe(true)
    expect(app.toast).toBe('Нет связи с сервером.')
  })

  it('быстрые нажатия уходят по очереди, второй запрос ждёт первый', async () => {
    const order: string[] = []
    let finishFirst: () => void = () => {}
    const api = fakePanelApi(makeOverview(), {
      setFlags: vi.fn(async (_id, flags) => {
        const name = Object.keys(flags)[0]
        order.push(`start ${name}`)
        if (name === 'is_published') await new Promise<void>((resolve) => { finishFirst = resolve })
        order.push(`end ${name}`)
        return makeOverview()
      }),
    })
    const { app } = setup({ api })
    await app.load()
    const first = app.toggle('is_published')
    const second = app.toggle('is_results_allowed')
    await flushPromises()
    expect(order).toEqual(['start is_published'])
    // оба показаны сразу, хотя на сервере пока ничего не подтверждено
    expect(app.flags.is_published).toBe(false)
    expect(app.flags.is_results_allowed).toBe(false)
    finishFirst()
    await Promise.all([first, second])
    expect(order).toEqual(['start is_published', 'end is_published', 'start is_results_allowed', 'end is_results_allowed'])
  })

  it('двойное нажатие на один переключатель: в итоге прежнее значение', async () => {
    const { app, api } = setup()
    await app.load()
    void app.toggle('is_results_allowed')
    await app.toggle('is_results_allowed')
    expect(api.setFlags).toHaveBeenCalledTimes(2)
    expect(api.setFlags).toHaveBeenNthCalledWith(1, EVENT_ID, { is_results_allowed: false })
    expect(api.setFlags).toHaveBeenNthCalledWith(2, EVENT_ID, { is_results_allowed: true })
    expect(app.flags.is_results_allowed).toBe(true)
  })

  it('до загрузки обзора переключать нечего', async () => {
    const { app, api } = setup()
    await app.toggle('is_published')
    expect(api.setFlags).not.toHaveBeenCalled()
  })
})

describe('служебные действия', () => {
  it('спрашивает подтверждение, отмена ничего не запускает', async () => {
    const { app, api } = setup()
    await app.load()
    app.ask('clear_results')
    expect(app.confirm).toBe('clear_results')
    app.cancel()
    expect(app.confirm).toBeNull()
    await app.run()
    expect(api.runAction).not.toHaveBeenCalled()
  })

  it('подтверждённое действие обновляет обзор и сообщает о результате', async () => {
    const after = makeOverview({ entered_count: 0, participants_count: 42 })
    const api = fakePanelApi(makeOverview(), { runAction: vi.fn(async () => after) })
    const { app } = setup({ api })
    await app.load()
    app.ask('update_score')
    await app.run()
    expect(api.runAction).toHaveBeenCalledWith(EVENT_ID, 'update_score')
    expect(app.confirm).toBeNull()
    expect(app.toast).toBe('Результаты пересчитаны')
  })

  it('удаление события ведёт на адрес из ответа', async () => {
    const api = fakePanelApi(makeOverview(), { runAction: vi.fn(async () => ({ removed: true as const, redirect: '/my_events/' })) })
    const { app, navigate } = setup({ api })
    await app.load()
    app.ask('remove_event')
    await app.run()
    expect(navigate).toHaveBeenCalledWith('/my_events/')
  })

  it('ошибка закрывает окно и пишет причину', async () => {
    const api = fakePanelApi(makeOverview(), {
      runAction: vi.fn().mockRejectedValue(new ApiError(403, 'action_not_allowed', 'Это действие сейчас недоступно.')),
    })
    const { app } = setup({ api })
    await app.load()
    app.ask('clear_event')
    await app.run()
    expect(app.confirm).toBeNull()
    expect(app.toast).toBe('Это действие сейчас недоступно.')
    expect(app.acting).toBe(false)
  })

  it('повторное «Да» во время выполнения не запускает действие дважды', async () => {
    let finish: () => void = () => {}
    const api = fakePanelApi(makeOverview(), {
      runAction: vi.fn(() => new Promise<PanelOverview>((resolve) => { finish = () => resolve(makeOverview()) })),
    })
    const { app } = setup({ api })
    await app.load()
    app.ask('clear_results')
    const first = app.run()
    void app.run()
    app.cancel()
    expect(app.confirm).toBe('clear_results')
    finish()
    await first
    expect(api.runAction).toHaveBeenCalledTimes(1)
  })

  it('тестовые данные только суперпользователю, завершённое событие очищать нельзя', async () => {
    const plain = setup({ overview: makeOverview({ is_expired: true }) })
    await plain.app.load()
    expect(plain.app.actions.map((a) => a.action)).toEqual(['update_score', 'clear_results', 'clear_event', 'remove_event'])
    expect(plain.app.actions.find((a) => a.action === 'clear_event')?.disabled).toBe(true)
    const admin = setup({ isSuperuser: true })
    await admin.app.load()
    expect(admin.app.actions.map((a) => a.action)).toContain('mock_data')
    expect(admin.app.actions.find((a) => a.action === 'clear_event')?.disabled).toBe(false)
  })
})

describe('чек-лист и ссылки', () => {
  it('прогресс считает только обязательное', async () => {
    const { app } = setup({
      overview: makeOverview({ checklist: [{ id: 'description', done: false, poster: false }, { id: 'pay', done: false, optional: true }, { id: 'publish', done: true }] }),
    })
    await app.load()
    expect(app.progress).toEqual({ done: 1, total: 2, open: true })
    expect(app.checklist.map((r) => r.id)).toEqual(['description', 'pay', 'publish'])
  })

  it('ссылки для зала копируются, сбой копирования тоже сообщается', async () => {
    const { app, copy } = setup()
    await app.load()
    expect(app.links.map((l) => l.url)).toEqual([
      'https://rockevents.ru/e/128/results/?autorefresh&m', 'https://rockevents.ru/e/128/results/?autorefresh&f',
    ])
    await app.copyLink(app.links[0].url, 'мужчины')
    expect(copy).toHaveBeenCalledWith('https://rockevents.ru/e/128/results/?autorefresh&m')
    expect(app.toast).toBe('Ссылка скопирована (мужчины)')
    copy.mockRejectedValueOnce(new Error('нет доступа'))
    await app.copyLink('x', 'женщины')
    expect(app.toast).toBe('Не удалось скопировать ссылку')
  })

  it('сообщение исчезает само', async () => {
    const { app } = setup()
    await app.load()
    app.showToast('Готово')
    await vi.advanceTimersByTimeAsync(4100)
    expect(app.toast).toBe('')
  })
})
