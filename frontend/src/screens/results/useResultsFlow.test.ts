import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ResultsPayload } from '../../api/results'
import { rememberKey, rememberParticipant } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import { apiError, networkError } from '../entry/testing'
import {
  HIGHLIGHT_MS, LIVE_INTERVAL_MS, MONITOR_INTERVAL_MS, useResultsFlow, type ResultsFlowDeps,
} from './useResultsFlow'
import { fakeResultsApi, makeRow, res, standardPayload } from './testing'

const EVENT_ID = 7

function setup(payload: ResultsPayload = standardPayload(), deps: Partial<ResultsFlowDeps> = {}) {
  const { api, state } = fakeResultsApi(payload)
  const store = deps.store ?? memoryStore()
  const flow = useResultsFlow({ eventId: EVENT_ID, api, store, isHidden: () => false, ...deps })
  return { flow, api, state, store }
}

/** Участник, которого телефон запомнил, например после ввода результатов. */
const remember = (store: ReturnType<typeof memoryStore>, last: string, first: string, gender: string, group = 0) =>
  rememberParticipant(store, EVENT_ID, { first_name: first, last_name: last, gender, group_index: group })

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

describe('загрузка', () => {
  it('показывает первую непустую таблицу', async () => {
    const { flow, api } = setup()
    expect(flow.status).toBe('loading')
    await flow.init()
    flow.dispose()
    expect(api.getResults).toHaveBeenCalledWith(EVENT_ID)
    expect(flow.status).toBe('ready')
    expect([flow.gender, flow.groupIndex]).toEqual(['MALE', 0])
    expect(flow.table?.ranked).toHaveLength(2)
  })

  it('если мужская таблица пуста, открывает женскую', async () => {
    const payload = standardPayload()
    payload.tables[0].ranked = []
    payload.tables[0].waiting = []
    payload.tables[1].ranked = []
    const { flow } = setup(payload)
    await flow.init()
    flow.dispose()
    expect(flow.gender).toBe('FEMALE')
  })

  it('открывает группу запомненного участника', async () => {
    const store = memoryStore()
    remember(store, 'Зайцева', 'Юлия', 'FEMALE')
    const { flow } = setup(standardPayload(), { store })
    await flow.init()
    flow.dispose()
    expect([flow.gender, flow.groupIndex]).toEqual(['FEMALE', 0])
    expect(flow.me?.row.last_name).toBe('Зайцева')
  })

  it('ссылка монитора выбирает пол и важнее запомненного участника', async () => {
    const store = memoryStore()
    remember(store, 'Андреев', 'Иван', 'MALE')
    const { flow } = setup(standardPayload(), { store, search: '?autorefresh&f' })
    await flow.init()
    flow.dispose()
    expect(flow.gender).toBe('FEMALE')
    expect(flow.monitor).toBe(true)
  })

  it('просмотр закрыт организатором', async () => {
    const { flow, api } = setup()
    api.getResults.mockRejectedValueOnce(apiError('results_closed', 403))
    await flow.init()
    flow.dispose()
    expect(flow.status).toBe('closed')
  })

  it('нет связи при первой загрузке: можно повторить', async () => {
    const { flow, api } = setup()
    api.getResults.mockRejectedValueOnce(networkError())
    await flow.init()
    expect(flow.status).toBe('fatal')
    expect(flow.fatalMessage).toMatch(/Нет связи/)
    await flow.init()
    flow.dispose()
    expect(flow.status).toBe('ready')
  })

  it('событие не найдено', async () => {
    const { flow, api } = setup()
    api.getResults.mockRejectedValueOnce(apiError('error', 404))
    await flow.init()
    flow.dispose()
    expect(flow.fatalMessage).toMatch(/не найдено/)
  })

  it('число групп уменьшили в настройках: выбранная группа не пропадает', async () => {
    const { flow, state } = setup()
    await flow.init()
    flow.selectGroup(1)
    state.current = { ...standardPayload(), groups: [], tables: standardPayload().tables.filter((t) => t.group_index === 0) }
    await flow.refresh()
    flow.dispose()
    expect(flow.groupIndex).toBe(0)
  })
})

describe('выбор таблицы', () => {
  it('переключает пол и группу, счётчики на чипах по выбранному полу', async () => {
    const { flow } = setup()
    await flow.init()
    flow.dispose()
    expect(flow.hasGroups).toBe(true)
    expect(flow.groupCounts).toEqual([3, 1])
    flow.selectGender('FEMALE')
    expect(flow.groupCounts).toEqual([3, 0])
    flow.selectGroup(1)
    expect(flow.table?.group).toBe('Спорт')
  })

  it('у события с одной группой чипов нет', async () => {
    const payload = standardPayload({ groups: [] })
    const { flow } = setup(payload)
    await flow.init()
    flow.dispose()
    expect(flow.hasGroups).toBe(false)
  })
})

describe('автообновление', () => {
  it('пока событие идёт, обновляется раз в 30 секунд', async () => {
    const { flow, api } = setup()
    await flow.init()
    expect(api.getResults).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(LIVE_INTERVAL_MS - 1000)
    expect(api.getResults).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(6000)
    expect(api.getResults).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(LIVE_INTERVAL_MS + 5000)
    expect(api.getResults).toHaveBeenCalledTimes(3)
    flow.dispose()
  })

  it('завершённое событие не обновляется само', async () => {
    const { flow, api } = setup(standardPayload({ is_live: false, is_expired: true }))
    await flow.init()
    await vi.advanceTimersByTimeAsync(LIVE_INTERVAL_MS * 3)
    expect(api.getResults).toHaveBeenCalledTimes(1)
    flow.dispose()
  })

  it('монитор для зала обновляется каждые 10 секунд, даже если событие не идёт', async () => {
    const { flow, api } = setup(standardPayload({ is_live: false }), { search: '?autorefresh&m' })
    await flow.init()
    await vi.advanceTimersByTimeAsync(MONITOR_INTERVAL_MS + 5000)
    expect(api.getResults).toHaveBeenCalledTimes(2)
    flow.dispose()
  })

  it('на скрытой вкладке не обновляется, а когда вкладка вернулась, обновляет сразу', async () => {
    let hidden = true
    const { flow, api } = setup(standardPayload(), { isHidden: () => hidden })
    await flow.init()
    await vi.advanceTimersByTimeAsync(LIVE_INTERVAL_MS * 2)
    expect(api.getResults).toHaveBeenCalledTimes(1)
    hidden = false
    flow.wake()
    await vi.advanceTimersByTimeAsync(0)
    expect(api.getResults).toHaveBeenCalledTimes(2)
    flow.dispose()
  })

  it('пока открыта карточка участника, таблица под ней не меняется', async () => {
    const { flow, api } = setup()
    await flow.init()
    flow.openPerson(flow.table!.ranked[0].id)
    await vi.advanceTimersByTimeAsync(LIVE_INTERVAL_MS * 2)
    expect(api.getResults).toHaveBeenCalledTimes(1)
    flow.closeSheet()
    await vi.advanceTimersByTimeAsync(0)
    expect(api.getResults).toHaveBeenCalledTimes(2)
    flow.dispose()
  })

  it('обрыв связи при обновлении не стирает таблицу, следующее обновление всё чинит', async () => {
    const { flow, api } = setup()
    await flow.init()
    api.getResults.mockRejectedValueOnce(networkError())
    await flow.refresh()
    expect(flow.status).toBe('ready')
    expect(flow.refreshFailed).toBe(true)
    expect(flow.table?.ranked).toHaveLength(2)
    await flow.refresh()
    expect(flow.refreshFailed).toBe(false)
    flow.dispose()
  })

  it('организатор закрыл просмотр во время события', async () => {
    const { flow, api } = setup()
    await flow.init()
    api.getResults.mockRejectedValueOnce(apiError('results_closed', 403))
    await flow.refresh()
    expect(flow.status).toBe('closed')
    flow.dispose()
  })

  it('запрос не дублируется, пока предыдущий не закончился', async () => {
    const { flow, api } = setup()
    await flow.init()
    await Promise.all([flow.refresh(), flow.refresh()])
    expect(api.getResults).toHaveBeenCalledTimes(2)
    flow.dispose()
  })

  it('текст «обновлено …» растёт со временем и обнуляется после обновления', async () => {
    const { flow } = setup()
    await flow.init()
    expect(flow.agoText).toBe('обновлено только что')
    await vi.advanceTimersByTimeAsync(20_000)
    expect(flow.agoText).toBe('обновлено 20 с назад')
    await flow.refresh()
    expect(flow.agoText).toBe('обновлено только что')
    flow.dispose()
  })
})

describe('подсветка сдвигов', () => {
  it('показывает стрелки и сообщение, а через 12 секунд убирает стрелки', async () => {
    const { flow, state } = setup()
    await flow.init()
    const next = JSON.parse(JSON.stringify(state.current)) as ResultsPayload
    const men = next.tables[0]
    const late = men.waiting.shift()!
    Object.assign(late, { place: 1, score: 300, score_view: '300', results: res(2, 2, 2, 2, 2), counted: [true, true, true, true, true] })
    men.ranked.unshift(late)
    men.ranked[1].place = 2
    men.ranked[2].place = 3
    state.current = next
    await flow.refresh()

    expect(flow.toast).toBe('Власов Глеб ввёл результат')
    expect(flow.deltas.get(men.ranked[1].id)).toBe(-1)
    expect(flow.changed.has(late.id)).toBe(true)
    expect(flow.table?.ranked[0].last_name).toBe('Власов')

    await vi.advanceTimersByTimeAsync(HIGHLIGHT_MS + 100)
    expect(flow.deltas.size).toBe(0)
    expect(flow.changed.size).toBe(0)
    expect(flow.toast).toBe('')
    flow.dispose()
  })

  it('кто-то ввёл в другой таблице: в сообщении группа и пол', async () => {
    const { flow, state } = setup()
    await flow.init()
    const next = JSON.parse(JSON.stringify(state.current)) as ResultsPayload
    const women = next.tables[2]
    const late = women.waiting.shift()!
    Object.assign(late, { place: 2, results: res(2, 0, 0, 0, 0) })
    women.ranked.push(late)
    state.current = next
    await flow.refresh()
    expect(flow.toast).toBe('Титова Полина ввела результат (Новички, Ж)')
    flow.dispose()
  })

  it('данные не изменились: ни сообщения, ни стрелок', async () => {
    const { flow } = setup()
    await flow.init()
    await flow.refresh()
    expect(flow.toast).toBe('')
    expect(flow.deltas.size).toBe(0)
    flow.dispose()
  })
})

describe('«это я»', () => {
  it('запоминает участника из карточки и сразу находит его строку', async () => {
    const { flow, store } = setup()
    await flow.init()
    const row = flow.table!.ranked[1]
    flow.openPerson(row.id)
    expect(flow.sheet?.row.last_name).toBe('Борисов')
    flow.rememberPerson(row)
    expect(flow.sheetId).toBeNull()
    expect(flow.meId).toBe(row.id)
    expect(flow.toast).toMatch(/Запомнили/)
    expect(JSON.parse(store.get(rememberKey(EVENT_ID))!)).toEqual(
      { id: row.id, first_name: 'Пётр', last_name: 'Борисов', gender: 'MALE', group_index: 0, set_index: 0 })
    flow.dispose()
  })

  it('«Вы» в другой таблице: переход открывает её и просит прокрутить к строке', async () => {
    const store = memoryStore()
    remember(store, 'Зайцева', 'Юлия', 'FEMALE')
    const { flow } = setup(standardPayload(), { store })
    await flow.init()
    flow.selectGender('MALE')
    flow.selectGroup(1)
    expect(flow.meInCurrentTable).toBe(false)
    flow.goToMe()
    expect([flow.gender, flow.groupIndex]).toEqual(['FEMALE', 0])
    expect(flow.meInCurrentTable).toBe(true)
    expect(flow.focusRow?.id).toBe(flow.meId)
    const first = flow.focusRow!.seq
    flow.goToMe()
    expect(flow.focusRow!.seq).toBe(first + 1)
    flow.dispose()
  })

  it('свою группу помечает на чипе', async () => {
    const store = memoryStore()
    remember(store, 'Гаврилов', 'Олег', 'MALE', 1)
    const { flow } = setup(standardPayload(), { store })
    await flow.init()
    expect(flow.myGroupIndex).toBe(1)
    flow.selectGender('FEMALE')
    expect(flow.myGroupIndex).toBe(-1)
    flow.dispose()
  })

  it('без запомненного участника «Вы» нет', async () => {
    const { flow } = setup()
    await flow.init()
    expect(flow.me).toBeNull()
    flow.goToMe()
    expect(flow.focusRow).toBeNull()
    flow.dispose()
  })

  it('участник из другого события не подхватывается', async () => {
    const store = memoryStore()
    rememberParticipant(store, 999, { first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 0 })
    const { flow } = setup(standardPayload(), { store })
    await flow.init()
    flow.dispose()
    expect(flow.me).toBeNull()
  })

  it('заготовка строки без результата не попадает в места', () => {
    expect(makeRow('Иванов', 'Иван', null).place).toBeNull()
  })
})
