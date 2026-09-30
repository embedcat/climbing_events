import { describe, expect, it } from 'vitest'
import { person, standardMatrix, tops } from '../screens/matrix/testing'
import {
  advanceCursor, byName, cellKey, cellValue, defaultFilters, draftStats, draftToChanges, filtersShowing, fixCursor,
  invalidCells, isVisible, parseCellKey, restoreDraft, rowHasDraft, searchParticipants, setDraftValue, stepCursor,
  visibleRows, type Cursor, type Draft,
} from './matrix'
import { interpretKey, isSaveShortcut, isSlash, type KeyLike } from './matrixKeys'

const matrix = () => standardMatrix()
const key = (overrides: Partial<KeyLike>): KeyLike => ({
  key: '', code: '', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, ...overrides,
})

describe('строки под фильтром', () => {
  const { participants } = matrix()

  it('без фильтров все, по фамилии, и счётчик без результата', () => {
    const { rows, missingCount } = visibleRows(participants, defaultFilters())
    expect(rows.map((p) => p.last_name)).toEqual(['Андреев', 'Борисов', 'Власов', 'Гаврилов', 'Зайцева', 'Титова'])
    expect(missingCount).toBe(3)
  })

  it('сет, группа и пол сужают строки и счётчик', () => {
    expect(visibleRows(participants, { ...defaultFilters(), set: 1 }).rows.map((p) => p.last_name))
      .toEqual(['Гаврилов', 'Зайцева', 'Титова'])
    expect(visibleRows(participants, { ...defaultFilters(), group: 1 }).rows.map((p) => p.last_name)).toEqual(['Гаврилов'])
    const women = visibleRows(participants, { ...defaultFilters(), gender: 'FEMALE' })
    expect(women.rows.map((p) => p.last_name)).toEqual(['Зайцева', 'Титова'])
    expect(women.missingCount).toBe(1)
  })

  it('«только без результата» убирает строки, но счётчик остаётся по всем выбранным', () => {
    const { rows, missingCount } = visibleRows(participants, { ...defaultFilters(), set: 1, missing: true })
    expect(rows.map((p) => p.last_name)).toEqual(['Гаврилов', 'Титова'])
    expect(missingCount).toBe(2)
  })

  it('видимость участника и фильтры, при которых он виден', () => {
    const gavrilov = participants[3]
    expect(isVisible(gavrilov, { ...defaultFilters(), set: 0 })).toBe(false)
    expect(isVisible(gavrilov, { ...defaultFilters(), set: 1 })).toBe(true)
    expect(isVisible(participants[0], { ...defaultFilters(), missing: true })).toBe(false)
    expect(filtersShowing(gavrilov, true)).toEqual({ set: 1, group: -1, gender: 'all', missing: false })
    expect(filtersShowing(gavrilov, false).set).toBe(-1)
  })

  it('сортировка по-русски, ё как е', () => {
    const a = person('Ёлкин', 'Ян', 3)
    const b = person('Егоров', 'Яков', 3)
    const c = person('Жуков', 'Иван', 3)
    expect([c, a, b].sort(byName).map((p) => p.last_name)).toEqual(['Егоров', 'Ёлкин', 'Жуков'])
  })
})

describe('черновик', () => {
  const [entered, waiting] = [
    person('Андреев', 'Иван', 4, {}, tops(2, 1, 0, 0)),
    person('Власов', 'Глеб', 4),
  ]
  const fresh = (): Draft => new Map()

  it('значение, совпавшее с сохранённым, снимает изменение', () => {
    const draft = fresh()
    setDraftValue(draft, entered, 0, { top: 1, zone: 0 }, false)
    expect(draft.has(cellKey(entered.id, 0))).toBe(true)
    setDraftValue(draft, entered, 0, { top: 2, zone: 0 }, false)
    expect(draft.size).toBe(0)
  })

  it('у участника без результата даже «нет» остаётся изменением', () => {
    const draft = fresh()
    setDraftValue(draft, waiting, 0, { top: 0, zone: 0 }, false)
    expect(draft.size).toBe(1)
    expect(cellValue(waiting, 0, draft)).toEqual({ top: 0, zone: 0 })
  })

  it('во французской системе сравниваются и топ, и зона', () => {
    const fr = person('Орлов', 'Егор', 3, {}, [{ top: 2, zone: 1 }, { top: 0, zone: 0 }, { top: 0, zone: 0 }])
    const draft = fresh()
    setDraftValue(draft, fr, 0, { top: 2, zone: 2 }, true)
    expect(draft.size).toBe(1)
    setDraftValue(draft, fr, 0, { top: 2, zone: 1 }, true)
    expect(draft.size).toBe(0)
  })

  it('ключи и счётчики', () => {
    const draft = fresh()
    setDraftValue(draft, waiting, 1, { top: 2, zone: 0 }, false)
    setDraftValue(draft, waiting, 3, { top: 1, zone: 0 }, false)
    setDraftValue(draft, entered, 2, { top: 2, zone: 0 }, false)
    expect(parseCellKey(cellKey(12, 34))).toEqual({ pid: 12, r: 34 })
    expect(draftStats(draft)).toEqual({ cells: 3, participants: 2 })
    expect(rowHasDraft(draft, waiting.id, 4)).toBe(true)
    expect(rowHasDraft(draft, 999, 4)).toBe(false)
  })

  it('запрос: по участнику, только изменённые трассы, вне французской системы только top', () => {
    const draft = fresh()
    setDraftValue(draft, waiting, 1, { top: 2, zone: 0 }, false)
    setDraftValue(draft, waiting, 3, { top: 1, zone: 0 }, false)
    setDraftValue(draft, entered, 2, { top: 2, zone: 0 }, false)
    expect(draftToChanges(draft, false)).toEqual([
      { participant: waiting.id, results: { 1: { top: 2 }, 3: { top: 1 } } },
      { participant: entered.id, results: { 2: { top: 2 } } },
    ])
    expect(draftToChanges(draft, true)[0].results[1]).toEqual({ top: 2, zone: 0 })
  })

  it('зона позже топа не даёт сохранить, но только во французской системе', () => {
    const draft = fresh()
    draft.set(cellKey(5, 2), { top: 1, zone: 3 })
    draft.set(cellKey(5, 3), { top: 0, zone: 4 })
    draft.set(cellKey(6, 0), { top: 2, zone: 2 })
    expect(invalidCells(draft, true)).toEqual([{ pid: 5, r: 2 }])
    expect(invalidCells(draft, false)).toEqual([])
  })

  describe('восстановление из браузера', () => {
    const people = [entered, waiting]
    const restore = (raw: unknown, fr = false) => restoreDraft(raw, people, 4, fr, 20)

    it('возвращает то, что ещё имеет смысл', () => {
      const restored = restore([[cellKey(waiting.id, 1), { top: 2, zone: 2 }], [cellKey(entered.id, 2), { top: 1, zone: 1 }]])
      expect(restored.size).toBe(2)
    })

    it('отбрасывает неизвестных, лишние трассы и мусор', () => {
      const restored = restore([
        [cellKey(999, 0), { top: 1, zone: 1 }],
        [cellKey(waiting.id, 9), { top: 1, zone: 1 }],
        [cellKey(waiting.id, -1), { top: 1, zone: 1 }],
        [cellKey(waiting.id, 0), { top: 'x', zone: 1 }],
        [cellKey(waiting.id, 1), { top: 3, zone: 3 }],
        [cellKey(waiting.id, 2), null],
        'строка',
        [5],
      ])
      expect(restored.size).toBe(0)
      expect(restore(null).size).toBe(0)
      expect(restore('x').size).toBe(0)
    })

    it('значение, уже совпавшее с сохранённым, в черновик не возвращается', () => {
      expect(restore([[cellKey(entered.id, 0), { top: 2, zone: 2 }]]).size).toBe(0)
    })

    it('французские попытки принимаются до предела', () => {
      expect(restore([[cellKey(waiting.id, 0), { top: 20, zone: 20 }]], true).size).toBe(1)
      expect(restore([[cellKey(waiting.id, 0), { top: 21, zone: 1 }]], true).size).toBe(0)
    })
  })
})

describe('поиск', () => {
  const { participants } = matrix()
  const shownAll = () => true

  it('по фамилии и имени, ё как е, регистр не важен', () => {
    expect(searchParticipants(participants, 'ЗАЙЦ', shownAll).map((p) => p.last_name)).toEqual(['Зайцева'])
    expect(searchParticipants(participants, 'олег', shownAll).map((p) => p.last_name)).toEqual(['Гаврилов'])
    expect(searchParticipants(participants, 'Юлия Зайцева', shownAll).map((p) => p.last_name)).toEqual(['Зайцева'])
    expect(searchParticipants(participants, 'Зайцева Юлия', shownAll)).toHaveLength(1)
    expect(searchParticipants([person('Ёлкина', 'Анна', 3)], 'елк', shownAll)).toHaveLength(1)
  })

  it('по началу PIN', () => {
    expect(searchParticipants(participants, '22', shownAll).map((p) => p.last_name)).toEqual(['Борисов'])
    expect(searchParticipants(participants, '5555', shownAll).map((p) => p.last_name)).toEqual(['Зайцева'])
  })

  it('видимые в таблице идут первыми, пустой запрос — никого', () => {
    const found = searchParticipants(participants, 'а', (p) => p.set_index === 1)
    expect(found[0].set_index).toBe(1)
    expect(searchParticipants(participants, '  ', shownAll)).toEqual([])
    expect(searchParticipants(participants, 'а', shownAll, 2)).toHaveLength(2)
  })
})

describe('курсор', () => {
  const rows = matrix().participants.slice(0, 3)
  const at = (index: number, r: number, sub: 0 | 1 = 0): Cursor => ({ pid: rows[index].id, r, sub })

  it('стрелки не выходят за границы', () => {
    expect(stepCursor(rows, at(0, 0), -1, -1, 6, false)).toEqual(at(0, 0))
    expect(stepCursor(rows, at(2, 5), 1, 1, 6, false)).toEqual(at(2, 5))
    expect(stepCursor(rows, at(0, 0), 1, 1, 6, false)).toEqual(at(1, 1))
  })

  it('во французской системе «т» и «з» — отдельные шаги', () => {
    expect(stepCursor(rows, at(0, 0, 0), 0, 1, 6, true)).toEqual(at(0, 0, 1))
    expect(stepCursor(rows, at(0, 0, 1), 0, 1, 6, true)).toEqual(at(0, 1, 0))
    expect(stepCursor(rows, at(0, 1, 0), 0, -1, 6, true)).toEqual(at(0, 0, 1))
    expect(stepCursor(rows, at(0, 5, 1), 0, 1, 6, true)).toEqual(at(0, 5, 1))
  })

  describe('после ввода', () => {
    it('вправо: следующая трасса, в конце строки следующий участник с подсказкой', () => {
      expect(advanceCursor(rows, at(0, 2), 'right', 6, false).cursor).toEqual(at(0, 3))
      const jump = advanceCursor(rows, at(0, 5), 'right', 6, false)
      expect(jump.cursor).toEqual(at(1, 0))
      expect(jump.jumpedTo).toBe(rows[1].id)
      expect(jump.hint).toBe('Следующий участник: Борисов Пётр')
    })

    it('вправо: у последнего участника остаёмся на месте', () => {
      const end = advanceCursor(rows, at(2, 5), 'right', 6, false)
      expect(end.cursor).toEqual(at(2, 5))
      expect(end.hint).toBe('Это последний участник в списке.')
    })

    it('вниз: следующий участник, в конце столбца первая строка следующей трассы', () => {
      expect(advanceCursor(rows, at(0, 2), 'down', 6, false).cursor).toEqual(at(1, 2))
      const jump = advanceCursor(rows, at(2, 2), 'down', 6, false)
      expect(jump.cursor).toEqual(at(0, 3))
      expect(jump.hint).toBe('Следующая трасса: 4')
    })

    it('вниз: у последней трассы остаёмся на месте', () => {
      const end = advanceCursor(rows, at(2, 5), 'down', 6, false)
      expect(end.cursor).toEqual(at(2, 5))
      expect(end.hint).toBe('Это последняя трасса.')
    })

    it('французская система: сначала топ, потом зона, потом дальше', () => {
      expect(advanceCursor(rows, at(0, 2, 0), 'right', 6, true).cursor).toEqual(at(0, 2, 1))
      expect(advanceCursor(rows, at(0, 2, 1), 'right', 6, true).cursor).toEqual(at(0, 3, 0))
      expect(advanceCursor(rows, at(0, 2, 1), 'down', 6, true).cursor).toEqual(at(1, 2, 0))
    })
  })

  it('после смены фильтров курсор остаётся на участнике, а если его нет, идёт на первого', () => {
    expect(fixCursor(rows, at(1, 3), 6, false)).toEqual(at(1, 3))
    expect(fixCursor(rows.slice(2), at(0, 9), 6, false)).toEqual({ pid: rows[2].id, r: 5, sub: 0 })
    expect(fixCursor([], at(0, 0), 6, false)).toBeNull()
    expect(fixCursor(rows, null, 6, true)).toEqual(at(0, 0))
  })
})

describe('клавиши', () => {
  it('стрелки, Tab и Shift+Tab', () => {
    expect(interpretKey(key({ key: 'ArrowLeft' }))).toEqual({ type: 'move', dRow: 0, dCol: -1 })
    expect(interpretKey(key({ key: 'ArrowDown' }))).toEqual({ type: 'move', dRow: 1, dCol: 0 })
    expect(interpretKey(key({ key: 'Tab' }))).toEqual({ type: 'move', dRow: 0, dCol: 1 })
    expect(interpretKey(key({ key: 'Tab', shiftKey: true }))).toEqual({ type: 'move', dRow: 0, dCol: -1 })
  })

  it('цифры в любой раскладке приходят как key', () => {
    expect(interpretKey(key({ key: '2', code: 'Digit2' }))).toEqual({ type: 'digit', digit: 2 })
    expect(interpretKey(key({ key: '7', code: 'Numpad7' }))).toEqual({ type: 'digit', digit: 7 })
  })

  it('буквы русской раскладки матрицу не интересуют', () => {
    expect(interpretKey(key({ key: 'ы', code: 'KeyS' }))).toBeNull()
    expect(interpretKey(key({ key: 'ф', code: 'KeyA' }))).toBeNull()
  })

  it('поиск: клавиша «/» на любой раскладке (по code)', () => {
    expect(interpretKey(key({ key: '.', code: 'Slash' }))).toEqual({ type: 'search' })
    expect(interpretKey(key({ key: '/', code: '' }))).toEqual({ type: 'search' })
    expect(isSlash({ key: ',', code: 'Slash' })).toBe(true)
  })

  it('служебные клавиши', () => {
    const names = ['Home', 'End', 'Backspace', 'Delete', 'Escape', 'Enter']
    const types = names.map((k) => interpretKey(key({ key: k }))?.type)
    expect(types).toEqual(['home', 'end', 'backspace', 'delete', 'escape', 'enter'])
    expect(interpretKey(key({ key: ' ' }))).toEqual({ type: 'space' })
  })

  it('с Ctrl, Cmd или Alt ничего не перехватываем', () => {
    expect(interpretKey(key({ key: '1', ctrlKey: true }))).toBeNull()
    expect(interpretKey(key({ key: 'ArrowRight', metaKey: true }))).toBeNull()
    expect(interpretKey(key({ key: 'Tab', altKey: true }))).toBeNull()
  })

  it('Ctrl+S по code: работает и на русской раскладке', () => {
    expect(isSaveShortcut({ code: 'KeyS', ctrlKey: true, metaKey: false })).toBe(true)
    expect(isSaveShortcut({ code: 'KeyS', ctrlKey: false, metaKey: true })).toBe(true)
    expect(isSaveShortcut({ code: 'KeyS', ctrlKey: false, metaKey: false })).toBe(false)
    expect(isSaveShortcut({ code: 'KeyD', ctrlKey: true, metaKey: false })).toBe(false)
  })
})
