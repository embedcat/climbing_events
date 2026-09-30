import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MatrixPayload } from '../../api/matrix'
import { cellKey } from '../../domain/matrix'
import type { KeyAction } from '../../domain/matrixKeys'
import { memoryStore } from '../../domain/storage'
import { apiError, networkError } from '../entry/testing'
import { fakeMatrixApi, person, standardMatrix } from './testing'
import { useMatrixFlow, type MatrixFlow } from './useMatrixFlow'

const EVENT_ID = 7
const STORE_KEY = `rockevents-matrix-draft:v1:${EVENT_ID}`

async function setup(payload: MatrixPayload = standardMatrix(), options: { store?: ReturnType<typeof memoryStore>; hash?: string } = {}) {
  const { api, state } = fakeMatrixApi(payload)
  const store = options.store ?? memoryStore()
  const flow = useMatrixFlow({ eventId: EVENT_ID, api, store, hash: options.hash })
  await flow.init()
  return { flow, api, state, store }
}

const digit = (d: number): KeyAction => ({ type: 'digit', digit: d })
const press = (flow: MatrixFlow, ...actions: KeyAction[]) => actions.forEach((a) => flow.applyKey(a))
const by = (flow: MatrixFlow, last: string) => flow.participants.find((p) => p.last_name === last)!
const cursorAt = (flow: MatrixFlow) => flow.cursor && { name: flow.current!.last_name, r: flow.cursor.r, sub: flow.cursor.sub }

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

describe('загрузка', () => {
  it('открывает сет, где больше всего участников без результата, курсор в начале первой строки', async () => {
    const { flow, api } = await setup()
    expect(api.getMatrix).toHaveBeenCalledWith(EVENT_ID)
    expect(flow.status).toBe('ready')
    // в сете 1 без результата один, в сете 2 двое
    expect(flow.filters.set).toBe(1)
    expect(flow.rows.map((p) => p.last_name)).toEqual(['Гаврилов', 'Зайцева', 'Титова'])
    expect(flow.missingCount).toBe(2)
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 0, sub: 0 })
  })

  it('у события с одним сетом фильтр по сету не нужен', async () => {
    const { flow } = await setup(standardMatrix({ sets: [] }))
    expect(flow.filters.set).toBe(-1)
    expect(flow.hasSets).toBe(false)
  })

  it('все внесены: показывает всех', async () => {
    const payload = standardMatrix()
    payload.participants.forEach((p) => { p.is_entered_result = true })
    const { flow } = await setup(payload)
    expect(flow.filters.set).toBe(-1)
  })

  it('нет прав: сообщение, а не ошибка загрузки', async () => {
    const { api } = fakeMatrixApi(standardMatrix())
    api.getMatrix.mockRejectedValueOnce(apiError('error', 403))
    const flow = useMatrixFlow({ eventId: EVENT_ID, api, store: memoryStore() })
    await flow.init()
    expect(flow.status).toBe('forbidden')
  })

  it('нет связи: можно повторить', async () => {
    const { api } = fakeMatrixApi(standardMatrix())
    api.getMatrix.mockRejectedValueOnce(networkError())
    const flow = useMatrixFlow({ eventId: EVENT_ID, api, store: memoryStore() })
    await flow.init()
    expect(flow.status).toBe('fatal')
    expect(flow.fatalMessage).toMatch(/Нет связи/)
    await flow.init()
    expect(flow.status).toBe('ready')
  })

  it('ссылка #p=id открывает участника, даже если он в другом сете', async () => {
    const payload = standardMatrix()
    const { flow } = await setup(payload, { hash: `#p=${payload.participants[0].id}` })
    expect(flow.filters.set).toBe(0)
    expect(cursorAt(flow)).toEqual({ name: 'Андреев', r: 0, sub: 0 })
    expect(flow.phone.pid).toBe(payload.participants[0].id)
  })

  it('ссылка на неизвестного участника ничего не ломает', async () => {
    const { flow } = await setup(standardMatrix(), { hash: '#p=99999' })
    expect(flow.status).toBe('ready')
    expect(flow.phone.pid).toBeNull()
  })
})

describe('ввод с клавиатуры (PROP)', () => {
  it('0, 1 и 2 пишут значение и двигают курсор вправо', async () => {
    const { flow } = await setup()
    press(flow, digit(2), digit(1), digit(0))
    const gavrilov = by(flow, 'Гаврилов')
    expect([0, 1, 2].map((r) => flow.valueAt(gavrilov, r).top)).toEqual([2, 1, 0])
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 3, sub: 0 })
    expect(flow.stats).toEqual({ cells: 3, participants: 1 })
  })

  it('в конце строки курсор идёт к следующему участнику и подсвечивает его', async () => {
    const { flow } = await setup()
    flow.moveTo({ pid: by(flow, 'Гаврилов').id, r: 5, sub: 0 })
    press(flow, digit(1))
    expect(cursorAt(flow)).toEqual({ name: 'Зайцева', r: 0, sub: 0 })
    expect(flow.flash?.pid).toBe(by(flow, 'Зайцева').id)
    expect(flow.hint).toBe('Следующий участник: Зайцева Юлия')
    vi.advanceTimersByTime(5000)
    expect(flow.hint).toBe('')
  })

  it('направление «вниз» переносит протокол трассы: вниз по столбцу, в конце к следующей трассе', async () => {
    const { flow } = await setup()
    flow.setDirection('down')
    press(flow, digit(2), digit(2), digit(2))
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 1, sub: 0 })
    expect(flow.hint).toBe('Следующая трасса: 2')
    expect(['Гаврилов', 'Зайцева', 'Титова'].map((n) => flow.valueAt(by(flow, n), 0).top)).toEqual([2, 2, 2])
  })

  it('направление запоминается в браузере', async () => {
    const first = await setup()
    first.flow.setDirection('down')
    const second = await setup(standardMatrix(), { store: first.store })
    expect(second.flow.direction).toBe('down')
  })

  it('пробел переключает по кругу и курсор не двигает, Backspace ставит «нет»', async () => {
    const { flow } = await setup()
    press(flow, { type: 'space' }, { type: 'space' })
    const p = by(flow, 'Гаврилов')
    expect(flow.valueAt(p, 0).top).toBe(2)
    expect(cursorAt(flow)?.r).toBe(0)
    press(flow, { type: 'backspace' })
    expect(flow.valueAt(p, 0).top).toBe(0)
  })

  it('Enter идёт на строку вниз, цифры 3–9 подсказывают про flash и redpoint', async () => {
    const { flow } = await setup()
    press(flow, { type: 'enter' })
    expect(cursorAt(flow)).toEqual({ name: 'Зайцева', r: 0, sub: 0 })
    press(flow, digit(5))
    expect(flow.hint).toMatch(/1 — flash, 2 — redpoint/)
    expect(flow.stats.cells).toBe(0)
  })

  it('стрелки и Home/End', async () => {
    const { flow } = await setup()
    press(flow, { type: 'move', dRow: 1, dCol: 2 })
    expect(cursorAt(flow)).toEqual({ name: 'Зайцева', r: 2, sub: 0 })
    press(flow, { type: 'end' })
    expect(cursorAt(flow)?.r).toBe(5)
    press(flow, { type: 'home' })
    expect(cursorAt(flow)?.r).toBe(0)
  })

  it('клик по выбранной ячейке переключает, по другой только переводит курсор', async () => {
    const { flow } = await setup()
    const p = by(flow, 'Гаврилов')
    flow.clickCell(p.id, 2, 0)
    expect(cursorAt(flow)?.r).toBe(2)
    expect(flow.valueAt(p, 2).top).toBe(0)
    flow.clickCell(p.id, 2, 0)
    expect(flow.valueAt(p, 2).top).toBe(1)
    flow.clickCell(p.id, 2, 0)
    expect(flow.valueAt(p, 2).top).toBe(2)
  })

  it('возврат к сохранённому значению снимает изменение', async () => {
    const { flow } = await setup()
    const zaitseva = by(flow, 'Зайцева')
    flow.moveTo({ pid: zaitseva.id, r: 0, sub: 0 })
    press(flow, { type: 'space' })
    expect(flow.stats.cells).toBe(1)
    press(flow, { type: 'space' }, { type: 'space' })
    expect(flow.valueAt(zaitseva, 0).top).toBe(1)
    expect(flow.stats.cells).toBe(0)
  })
})

describe('ввод с клавиатуры (французская система)', () => {
  const french = () => standardMatrix({ score_type: 'FR' })

  it('цифры набираются в ячейке, Enter записывает и идёт к зоне, потом к следующей трассе', async () => {
    const { flow } = await setup(french())
    const p = by(flow, 'Гаврилов')
    press(flow, digit(3))
    expect(flow.edit).toBe('3')
    expect(flow.stats.cells).toBe(0)
    press(flow, { type: 'enter' })
    // топ без зоны: зона на той же попытке
    expect(flow.valueAt(p, 0)).toEqual({ top: 3, zone: 3 })
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 0, sub: 1 })
    press(flow, digit(2), { type: 'enter' })
    expect(flow.valueAt(p, 0)).toEqual({ top: 3, zone: 2 })
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 1, sub: 0 })
  })

  it('двузначное число, ведущие нули отбрасываются, больше двух цифр не набрать', async () => {
    const { flow } = await setup(french())
    press(flow, digit(0), digit(0), digit(7), digit(2), digit(9))
    expect(flow.edit).toBe('72')
  })

  it('попытка выше предела обрезается до предела', async () => {
    const { flow } = await setup(french())
    press(flow, digit(9), digit(9), { type: 'enter' })
    expect(flow.valueAt(by(flow, 'Гаврилов'), 0).top).toBe(20)
  })

  it('Backspace стирает набранное, а без набора обнуляет ячейку; Delete обнуляет сразу; Esc отменяет набор', async () => {
    const { flow } = await setup(french())
    const p = by(flow, 'Гаврилов')
    press(flow, digit(4), digit(5), { type: 'backspace' })
    expect(flow.edit).toBe('4')
    press(flow, { type: 'escape' })
    expect(flow.edit).toBeNull()
    expect(flow.stats.cells).toBe(0)
    flow.setAttempt(p, 0, 0, 4)
    press(flow, { type: 'backspace' })
    expect(flow.valueAt(p, 0)).toEqual({ top: 0, zone: 4 })
    press(flow, digit(2), { type: 'delete' })
    expect(flow.edit).toBeNull()
    expect(flow.valueAt(p, 0)).toEqual({ top: 0, zone: 4 })
  })

  it('набор записывается, когда уходишь стрелкой', async () => {
    const { flow } = await setup(french())
    press(flow, digit(2), { type: 'move', dRow: 1, dCol: 0 })
    expect(flow.valueAt(by(flow, 'Гаврилов'), 0).top).toBe(2)
    expect(flow.edit).toBeNull()
  })

  it('зона позже топа блокирует сохранение и подсвечивается, а после правки всё снова можно сохранить', async () => {
    const { flow, api } = await setup(french())
    const p = by(flow, 'Гаврилов')
    flow.setAttempt(p, 2, 0, 1)
    flow.setAttempt(p, 2, 1, 4)
    expect(flow.invalid).toEqual([{ pid: p.id, r: 2 }])
    expect(flow.canSave).toBe(false)
    await flow.save()
    expect(api.save).not.toHaveBeenCalled()
    expect(flow.hint).toMatch(/зона позже топа/)
    flow.goToProblem()
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 2, sub: 1 })
    flow.setAttempt(p, 2, 1, 1)
    expect(flow.invalid).toEqual([])
    expect(flow.canSave).toBe(true)
  })

  it('на французской системе шаги на телефоне работают так же', async () => {
    const { flow } = await setup(french())
    const p = by(flow, 'Гаврилов')
    flow.stepCell(p, 1, 'top', 1)
    expect(flow.valueAt(p, 1)).toEqual({ top: 1, zone: 1 })
    flow.stepCell(p, 1, 'zone', 1)
    expect(flow.invalid).toHaveLength(1)
  })
})

describe('фильтры и поиск', () => {
  it('смена фильтра оставляет курсор на участнике, если он виден', async () => {
    const { flow } = await setup()
    flow.moveTo({ pid: by(flow, 'Зайцева').id, r: 3, sub: 0 })
    flow.setFilter('gender', 'FEMALE')
    expect(flow.rows.map((p) => p.last_name)).toEqual(['Зайцева', 'Титова'])
    expect(cursorAt(flow)).toEqual({ name: 'Зайцева', r: 3, sub: 0 })
    flow.setFilter('gender', 'MALE')
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 3, sub: 0 })
  })

  it('«без результата» оставляет только таких', async () => {
    const { flow } = await setup()
    flow.setFilter('missing', true)
    expect(flow.rows.map((p) => p.last_name)).toEqual(['Гаврилов', 'Титова'])
  })

  it('поиск по PIN и по фамилии, выбор переводит курсор и подсвечивает строку', async () => {
    const { flow } = await setup()
    flow.setSearch('1111')
    expect(flow.searchResults.map((p) => p.last_name)).toEqual(['Андреев'])
    flow.pickSearch()
    expect(flow.filters.set).toBe(0)
    expect(cursorAt(flow)).toEqual({ name: 'Андреев', r: 0, sub: 0 })
    expect(flow.flash?.pid).toBe(by(flow, 'Андреев').id)
    expect(flow.searchQuery).toBe('')
  })

  it('поиск: стрелки по списку, видимые в таблице первыми', async () => {
    const { flow } = await setup()
    flow.setSearch('а')
    expect(flow.searchResults[0].set_index).toBe(1)
    flow.moveSearch(1)
    expect(flow.searchActive).toBe(1)
    flow.moveSearch(-5)
    expect(flow.searchActive).toBe(0)
  })

  it('«/» просит перевести фокус в поиск и отменяет набор', async () => {
    const { flow } = await setup(standardMatrix({ score_type: 'FR' }))
    press(flow, digit(3))
    const before = flow.searchFocus
    press(flow, { type: 'search' })
    expect(flow.searchFocus).toBe(before + 1)
    expect(flow.edit).toBeNull()
  })

  it('число пролазов по трассам считается по показанным строкам и с учётом черновика', async () => {
    const { flow } = await setup()
    expect(flow.routeCounts).toEqual([1, 1, 1, 0, 0, 0])
    flow.setTop(by(flow, 'Гаврилов'), 3, 2)
    expect(flow.routeCounts[3]).toBe(1)
  })
})

describe('черновик в браузере', () => {
  it('сохраняется при каждом изменении и возвращается после перезагрузки страницы', async () => {
    const first = await setup()
    press(first.flow, digit(2), digit(1))
    expect(JSON.parse(first.store.get(STORE_KEY)!)).toHaveLength(2)

    const second = await setup(standardMatrix(), { store: first.store })
    expect(second.flow.stats.cells).toBe(2)
    expect(second.flow.restoredCount).toBe(2)
    expect(cursorAt(second.flow)).toEqual({ name: 'Гаврилов', r: 2, sub: 0 })
    expect(second.flow.valueAt(by(second.flow, 'Гаврилов'), 0).top).toBe(2)
  })

  it('открывает сет, где остался черновик', async () => {
    const first = await setup()
    first.flow.setFilter('set', 0)
    first.flow.moveTo({ pid: by(first.flow, 'Власов').id, r: 0, sub: 0 })
    press(first.flow, digit(1))
    const second = await setup(standardMatrix(), { store: first.store })
    expect(second.flow.filters.set).toBe(0)
  })

  it('мусор в хранилище и чужие участники не мешают', async () => {
    const store = memoryStore({ [STORE_KEY]: '{oops' })
    const { flow } = await setup(standardMatrix(), { store })
    expect(flow.status).toBe('ready')
    expect(flow.stats.cells).toBe(0)
    const stale = memoryStore({ [STORE_KEY]: JSON.stringify([[cellKey(9999, 0), { top: 1, zone: 1 }]]) })
    const second = await setup(standardMatrix(), { store: stale })
    expect(second.flow.stats.cells).toBe(0)
    expect(JSON.parse(stale.get(STORE_KEY)!)).toEqual([])
  })

  it('браузер не даёт сохранить: сообщаем, но работаем', async () => {
    const store = memoryStore()
    store.set = () => false
    const { flow } = await setup(standardMatrix(), { store })
    press(flow, digit(1))
    expect(flow.storageOk).toBe(false)
    expect(flow.stats.cells).toBe(1)
  })

  it('«Отменить изменения» очищает и черновик в браузере', async () => {
    const { flow, store } = await setup()
    press(flow, digit(1), digit(1))
    flow.discard()
    expect(flow.stats.cells).toBe(0)
    expect(JSON.parse(store.get(STORE_KEY)!)).toEqual([])
    expect(flow.restoredCount).toBe(0)
  })
})

describe('сохранение', () => {
  it('отправляет только изменённые ячейки по участникам, потом подтягивает пересчитанные данные', async () => {
    const { flow, api } = await setup()
    press(flow, digit(2), digit(1))
    flow.moveTo({ pid: by(flow, 'Титова').id, r: 4, sub: 0 })
    press(flow, digit(0))
    await flow.save()

    const changes = api.save.mock.calls[0][1]
    expect(changes).toEqual([
      { participant: by(flow, 'Гаврилов').id, results: { 0: { top: 2 }, 1: { top: 1 } } },
      { participant: by(flow, 'Титова').id, results: { 4: { top: 0 } } },
    ])
    expect(flow.stats.cells).toBe(0)
    expect(flow.saving).toBe(false)
    expect(flow.savedMessage).toBe('Сохранено 3 результата у 2 участников. Баллы и места пересчитаны.')
    // у Титовой был «нет результата»: теперь она внесла результат, хоть и все «нет»
    expect(by(flow, 'Титова').is_entered_result).toBe(true)
    expect(flow.missingCount).toBe(0)
  })

  it('сообщение в единственном числе', async () => {
    const { flow } = await setup()
    press(flow, digit(2))
    await flow.save()
    expect(flow.savedMessage).toBe('Сохранено 1 результат у 1 участника. Баллы и места пересчитаны.')
  })

  it('сдвиг мест показывается стрелками и через 8 секунд гаснет', async () => {
    const { flow, api, state } = await setup()
    const zaitseva = by(flow, 'Зайцева')
    flow.setTop(by(flow, 'Гаврилов'), 0, 2)
    // сервер пересчитал места: Зайцева была первой, стала второй
    api.save.mockImplementationOnce(async () => {
      const next = JSON.parse(JSON.stringify(state.current)) as MatrixPayload
      next.participants.find((p) => p.id === zaitseva.id)!.place = 2
      return { ...next, saved: { cells: 1, participants: 1 } }
    })
    await flow.save()
    expect(flow.deltas.get(zaitseva.id)).toBe(-1)
    vi.advanceTimersByTime(8100)
    expect(flow.deltas.size).toBe(0)
  })

  it('пока идёт запрос, правка той же ячейки остаётся в черновике', async () => {
    const { flow, api } = await setup()
    const p = by(flow, 'Гаврилов')
    flow.setTop(p, 0, 1)
    let release: () => void = () => {}
    const original = api.save.getMockImplementation()!
    api.save.mockImplementationOnce(async (id, changes) => {
      await new Promise<void>((resolve) => { release = resolve })
      return original(id, changes)
    })
    const pending = flow.save()
    expect(flow.saving).toBe(true)
    flow.setTop(p, 0, 2)
    flow.setTop(p, 1, 2)
    release()
    await pending
    expect([...flow.draft.keys()].sort()).toEqual([cellKey(p.id, 0), cellKey(p.id, 1)])
    expect(flow.valueAt(p, 0).top).toBe(2)
  })

  it('двойное нажатие не отправляет запрос дважды', async () => {
    const { flow, api } = await setup()
    press(flow, digit(1))
    await Promise.all([flow.save(), flow.save()])
    expect(api.save).toHaveBeenCalledTimes(1)
  })

  it('нечего сохранять — запроса нет', async () => {
    const { flow, api } = await setup()
    await flow.save()
    expect(api.save).not.toHaveBeenCalled()
  })

  it('нет связи: черновик цел, ошибка сетевая, повтор проходит', async () => {
    const { flow, api } = await setup()
    press(flow, digit(1))
    api.save.mockRejectedValueOnce(networkError())
    await flow.save()
    expect(flow.saveError?.isNetwork).toBe(true)
    expect(flow.stats.cells).toBe(1)
    expect(flow.saving).toBe(false)
    await flow.save()
    expect(flow.saveError).toBeNull()
    expect(flow.stats.cells).toBe(0)
  })

  it('сервер отклонил результаты участника: ошибка и переход к его трассе', async () => {
    const { flow, api } = await setup(standardMatrix({ score_type: 'FR' }))
    const p = by(flow, 'Гаврилов')
    flow.setAttempt(p, 3, 0, 1)
    api.save.mockRejectedValueOnce(apiError('invalid_results', 400, 'Зона позже топа: Гаврилов Олег, трасса 4.', { routes: [4], participant: p.id }))
    await flow.save()
    expect(flow.saveError?.message).toBe('Зона позже топа: Гаврилов Олег, трасса 4.')
    expect(flow.errorTarget).toEqual({ pid: p.id, r: 3 })
    flow.moveTo({ pid: by(flow, 'Титова').id, r: 0, sub: 0 })
    flow.goToProblem()
    expect(cursorAt(flow)).toEqual({ name: 'Гаврилов', r: 3, sub: 1 })
    expect(flow.stats.cells).toBe(1)
  })

  it('«Обновить данные» подтягивает ввод участников, а черновик и курсор остаются', async () => {
    const { flow, state } = await setup()
    press(flow, digit(2))
    const cursor = { ...flow.cursor! }
    state.current.participants.forEach((p) => { if (p.last_name === 'Титова') { p.is_entered_result = true; p.place = 2 } })
    await flow.refresh()
    expect(by(flow, 'Титова').is_entered_result).toBe(true)
    expect(flow.missingCount).toBe(1)
    expect(flow.stats.cells).toBe(1)
    expect(flow.cursor).toEqual(cursor)
    expect(flow.hint).toBe('Данные обновлены.')
  })

  it('обновление: черновик про участника, которого уже нет, отбрасывается', async () => {
    const { flow, state } = await setup()
    press(flow, digit(2))
    state.current.participants = state.current.participants.filter((p) => p.last_name !== 'Гаврилов')
    await flow.refresh()
    expect(flow.stats.cells).toBe(0)
  })

  it('обновление при обрыве связи даёт ошибку, но ничего не стирает', async () => {
    const { flow, api } = await setup()
    press(flow, digit(2))
    api.getMatrix.mockRejectedValueOnce(networkError())
    await flow.refresh()
    expect(flow.saveError?.isNetwork).toBe(true)
    expect(flow.stats.cells).toBe(1)
    expect(flow.participants).toHaveLength(6)
  })
})

describe('шаги на телефоне', () => {
  it('открывает участника, идёт к следующему по списку и возвращается к списку на последнем', async () => {
    const { flow } = await setup()
    const [first, second, third] = flow.rows
    flow.phoneOpen(first.id)
    expect(flow.phoneParticipant?.last_name).toBe('Гаврилов')
    flow.phoneNext()
    expect(flow.phone.pid).toBe(second.id)
    flow.phoneNext()
    expect(flow.phone.pid).toBe(third.id)
    flow.phoneNext()
    expect(flow.phone.pid).toBeNull()
    flow.phoneOpen(first.id)
    flow.phoneClose()
    expect(flow.phone.pid).toBeNull()
  })

  it('трасса выбирается в пределах события', async () => {
    const { flow } = await setup()
    flow.setPhoneRoute(3)
    expect(flow.phone.route).toBe(3)
    flow.setPhoneRoute(99)
    expect(flow.phone.route).toBe(5)
    flow.setPhoneRoute(-4)
    expect(flow.phone.route).toBe(0)
  })

  it('по трассе: явное значение для каждого участника и то же сохранение', async () => {
    const { flow, api } = await setup()
    flow.setPhoneRoute(2)
    for (const [name, top] of [['Гаврилов', 2], ['Зайцева', 0], ['Титова', 1]] as const) flow.setTop(by(flow, name), 2, top)
    await flow.save()
    expect(api.save.mock.calls[0][1].map((c) => c.results)).toEqual([{ 2: { top: 2 } }, { 2: { top: 0 } }, { 2: { top: 1 } }])
  })

  it('плитка переключает нет → flash → redpoint → нет', async () => {
    const { flow } = await setup()
    const p = by(flow, 'Гаврилов')
    const seen = []
    for (let i = 0; i < 3; i++) {
      flow.cycleCell(p, 1)
      seen.push(flow.valueAt(p, 1).top)
    }
    expect(seen).toEqual([1, 2, 0])
    // участник без результата: возврат к «нет» остаётся изменением
    expect(flow.isDirty(p.id, 1)).toBe(true)
  })

  it('заготовка участника', () => {
    expect(person('А', 'Б', 2).results).toHaveLength(2)
  })
})
