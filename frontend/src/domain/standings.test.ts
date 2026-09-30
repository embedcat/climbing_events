import { describe, expect, it } from 'vitest'
import { fr, makePayload, makeRow, makeTable, res, standardPayload } from '../screens/results/testing'
import {
  cellView, changeMessage, diffResults, findRemembered, findRow, findTable, flashRedpointTotals, formatAgo,
  formatPoints, formatScore, frenchTotals, shortName, tableKey,
} from './standings'

describe('поиск', () => {
  const payload = standardPayload()

  it('таблица по полу и группе', () => {
    expect(findTable(payload, 'FEMALE', 0)?.ranked[0].last_name).toBe('Зайцева')
    expect(findTable(payload, 'FEMALE', 5)).toBeNull()
    expect(tableKey(payload.tables[1])).toBe('MALE:1')
  })

  it('строка по id вместе с таблицей', () => {
    const waiting = payload.tables[0].waiting[0]
    expect(findRow(payload, waiting.id)?.table.group).toBe('Новички')
    expect(findRow(payload, 99999)).toBeNull()
  })

  it('запомненного участника находит по имени без учёта регистра и пробелов', () => {
    const me = { first_name: ' юлия ', last_name: 'ЗАЙЦЕВА', gender: 'FEMALE', group_index: 9 }
    expect(findRemembered(payload, me)).toBe(payload.tables[2].ranked[0].id)
  })

  it('однофамилец другого пола и неизвестный участник не находятся', () => {
    expect(findRemembered(payload, { first_name: 'Юлия', last_name: 'Зайцева', gender: 'MALE', group_index: 0 })).toBeNull()
    expect(findRemembered(payload, { first_name: 'Кто-то', last_name: 'Другой', gender: 'MALE', group_index: 0 })).toBeNull()
    expect(findRemembered(payload, null)).toBeNull()
  })

  it('участник без результата тоже находится', () => {
    const me = { first_name: 'Полина', last_name: 'Титова', gender: 'FEMALE', group_index: 0 }
    expect(findRemembered(payload, me)).toBe(payload.tables[2].waiting[0].id)
  })
})

describe('подписи', () => {
  it('счёт очками форматируется по-русски, остальные системы показывают готовую строку', () => {
    const row = makeRow('Иванов', 'Иван', 1, [], { score: 1247.5, score_view: '1247.5' })
    expect(formatScore(row, 'PROP')).toBe('1247,5')
    expect(formatScore({ ...row, score: 180 }, 'SUM')).toBe('180')
    expect(formatScore({ ...row, score: 99.123 }, 'TBL')).toBe('99,12')
    expect(formatScore({ ...row, score_view: '3T7 4z9' }, 'FR')).toBe('3T7 4z9')
    expect(formatScore({ ...row, score_view: '5/2' }, 'NUM')).toBe('5/2')
  })

  it('очки за трассу — с одним знаком', () => {
    expect(formatPoints(11.4285)).toBe('11,4')
    expect(formatPoints(80)).toBe('80')
  })

  it('короткое имя', () => {
    expect(shortName({ last_name: 'Зайцева', first_name: 'Юлия' })).toBe('Зайцева Ю.')
  })

  it('«обновлено …»', () => {
    expect(formatAgo(3)).toBe('обновлено только что')
    expect(formatAgo(42)).toBe('обновлено 42 с назад')
    expect(formatAgo(130)).toBe('обновлено 2 мин назад')
  })
})

describe('ячейки', () => {
  it('flash и redpoint', () => {
    expect(cellView({ top: 1, zone: 0 }, false, true)).toEqual({ text: 'FL', kind: 'fl', dim: false })
    expect(cellView({ top: 2, zone: 0 }, false, true)).toEqual({ text: 'RP', kind: 'rp', dim: false })
    expect(cellView({ top: 0, zone: 0 }, false, true)).toEqual({ text: '', kind: '', dim: false })
    expect(cellView(undefined, false, true)).toEqual({ text: '', kind: '', dim: false })
  })

  it('трасса вне зачёта бледнеет только если на ней есть пролаз', () => {
    expect(cellView({ top: 2, zone: 0 }, false, false).dim).toBe(true)
    expect(cellView({ top: 0, zone: 0 }, false, false).dim).toBe(false)
  })

  it('французская система: попытки топа и зоны', () => {
    expect(cellView({ top: 3, zone: 2 }, true, true)).toEqual({ text: '3/2', kind: 'top', dim: false })
    expect(cellView({ top: 0, zone: 4 }, true, true)).toEqual({ text: '–/4', kind: 'zone', dim: false })
    expect(cellView({ top: 0, zone: 0 }, true, true).text).toBe('')
  })

  it('итоги по трассам', () => {
    expect(flashRedpointTotals(res(1, 2, 2, 0, 1))).toEqual({ flash: 2, redpoint: 2 })
    expect(frenchTotals(fr([3, 2], [0, 4], [1, 1], [0, 0]))).toEqual({ tops: 2, topAttempts: 4, zones: 3, zoneAttempts: 7 })
  })
})

describe('что изменилось между обновлениями', () => {
  const before = standardPayload()
  const clone = () => JSON.parse(JSON.stringify(before)) as typeof before

  it('без изменений ничего нет', () => {
    const diff = diffResults(before, clone())
    expect(diff.events).toEqual([])
    expect(diff.changed.size).toBe(0)
    expect(diff.deltas.size).toBe(0)
  })

  it('участник ввёл результат: событие, место новичка и сдвиг тех, кого он обогнал', () => {
    const next = clone()
    const men = next.tables[0]
    const late = men.waiting.shift()!
    late.place = 1
    late.results = res(2, 2, 2, 2, 2)
    men.ranked.unshift(late)
    men.ranked[1].place = 2
    men.ranked[2].place = 3

    const diff = diffResults(before, next)
    expect(diff.events).toEqual([
      { id: late.id, name: 'Власов Глеб', gender: 'MALE', group: 'Новички', groupIndex: 0, kind: 'entered' },
    ])
    expect([...diff.deltas.values()].sort()).toEqual([-1, -1])
    expect(diff.changed.has(late.id)).toBe(true)
    expect(diff.changed.size).toBe(3)
  })

  it('исправленный результат', () => {
    const next = clone()
    next.tables[0].ranked[1].results = res(2, 2, 0, 2, 0)
    const diff = diffResults(before, next)
    expect(diff.events.map((e) => e.kind)).toEqual(['corrected'])
    expect(diff.events[0].name).toBe('Борисов Пётр')
  })

  it('только сдвиг места без нового ввода: стрелки есть, сообщения нет', () => {
    const next = clone()
    const [a, b] = next.tables[0].ranked
    a.place = 2
    b.place = 1
    const diff = diffResults(before, next)
    expect(diff.events).toEqual([])
    expect(diff.deltas.get(a.id)).toBe(-1)
    expect(diff.deltas.get(b.id)).toBe(1)
  })

  it('новый участник сразу с результатом тоже считается вводом', () => {
    const next = clone()
    next.tables[1].ranked.push(makeRow('Дроздов', 'Аркадий', 2, res(1)))
    expect(diffResults(before, next).events.map((e) => e.name)).toEqual(['Дроздов Аркадий'])
  })

  it('участник без результата не даёт событий', () => {
    const next = clone()
    next.tables[0].waiting.push(makeRow('Ёлкин', 'Игорь', null))
    expect(diffResults(before, next).events).toEqual([])
  })
})

describe('сообщение о вводе', () => {
  const event = (overrides = {}) => ({
    id: 1, name: 'Титова Полина', gender: 'FEMALE' as const, group: 'Спорт', groupIndex: 1, kind: 'entered' as const,
    ...overrides,
  })

  it('форма глагола зависит от пола и вида изменения', () => {
    expect(changeMessage([event()], () => true)).toBe('Титова Полина ввела результат')
    expect(changeMessage([event({ gender: 'MALE', name: 'Титов Павел' })], () => true)).toBe('Титов Павел ввёл результат')
    expect(changeMessage([event({ kind: 'corrected' })], () => true)).toBe('Титова Полина исправила результат')
    expect(changeMessage([event({ gender: 'MALE', kind: 'corrected', name: 'Титов Павел' })], () => true))
      .toBe('Титов Павел исправил результат')
  })

  it('если участник в другой таблице, добавляет группу и пол', () => {
    expect(changeMessage([event()], () => false)).toBe('Титова Полина ввела результат (Спорт, Ж)')
    expect(changeMessage([event({ group: '', gender: 'MALE' })], () => false)).toBe('Титова Полина ввёл результат (М)')
  })

  it('несколько изменений — одно общее сообщение, ни одного — пусто', () => {
    expect(changeMessage([event(), event({ id: 2 }), event({ id: 3 })], () => true)).toBe('Обновились результаты: 3')
    expect(changeMessage([], () => true)).toBe('')
  })
})

describe('заготовки тестов', () => {
  it('makePayload по умолчанию даёт пять трасс', () => {
    expect(makePayload([makeTable('MALE', 0, '', [])]).routes).toHaveLength(5)
  })
})
