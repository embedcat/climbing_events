import { describe, expect, it } from 'vitest'
import {
  cycleTile, emptyResults, invalidFrenchRoutes, isResultsShape, stepAttempt, summarize, toPayload,
} from './results'

describe('cycleTile', () => {
  it('идёт по кругу нет → flash → redpoint → нет', () => {
    let result = { top: 0, zone: 0 }
    const seen = []
    for (let i = 0; i < 4; i++) {
      result = cycleTile(result)
      seen.push(result.top)
    }
    expect(seen).toEqual([1, 2, 0, 1])
  })
})

describe('stepAttempt', () => {
  const step = (r: { top: number; zone: number }, kind: 'top' | 'zone', delta: number) => stepAttempt(r, kind, delta, 20)

  it('топ без зоны тянет зону на ту же попытку', () => {
    expect(step({ top: 0, zone: 0 }, 'top', 1)).toEqual({ top: 1, zone: 1 })
  })

  it('следующие попытки топа зону не трогают', () => {
    expect(step({ top: 1, zone: 1 }, 'top', 1)).toEqual({ top: 2, zone: 1 })
  })

  it('зона без топа может быть любой', () => {
    expect(step({ top: 0, zone: 0 }, 'zone', 1)).toEqual({ top: 0, zone: 1 })
    expect(step({ top: 0, zone: 1 }, 'zone', -1)).toEqual({ top: 0, zone: 0 })
  })

  it('при топе зона не опускается ниже первой попытки', () => {
    expect(step({ top: 3, zone: 1 }, 'zone', -1)).toEqual({ top: 3, zone: 1 })
  })

  it('номер попытки не выходит за границы', () => {
    expect(step({ top: 0, zone: 0 }, 'top', -1)).toEqual({ top: 0, zone: 0 })
    expect(stepAttempt({ top: 20, zone: 20 }, 'top', 1, 20)).toEqual({ top: 20, zone: 20 })
  })

  it('можно поднять зону выше топа, но трасса подсвечивается как ошибочная', () => {
    const result = step({ top: 2, zone: 2 }, 'zone', 1)
    expect(result).toEqual({ top: 2, zone: 3 })
    expect(invalidFrenchRoutes([{ top: 0, zone: 0 }, result])).toEqual([1])
  })
})

describe('invalidFrenchRoutes', () => {
  it('зона позже топа — ошибка, зона без топа и равные попытки — нет', () => {
    expect(invalidFrenchRoutes([
      { top: 2, zone: 3 }, { top: 0, zone: 4 }, { top: 3, zone: 3 }, { top: 3, zone: 1 },
    ])).toEqual([0])
  })
})

describe('summarize', () => {
  it('считает flash и redpoint', () => {
    const results = [{ top: 1, zone: 0 }, { top: 2, zone: 0 }, { top: 2, zone: 0 }, { top: 0, zone: 0 }]
    expect(summarize(results, false)).toEqual({ flash: 1, redpoint: 2, tops: 0, zones: 0, marked: 3 })
  })

  it('во французской системе считает топы и зоны отдельно', () => {
    const results = [{ top: 2, zone: 1 }, { top: 0, zone: 3 }, { top: 0, zone: 0 }]
    expect(summarize(results, true)).toEqual({ flash: 0, redpoint: 0, tops: 1, zones: 2, marked: 2 })
  })
})

describe('toPayload', () => {
  it('вне французской системы отправляет только top', () => {
    expect(toPayload([{ top: 2, zone: 0 }], false)).toEqual([{ top: 2 }])
  })

  it('во французской отправляет top и zone', () => {
    expect(toPayload([{ top: 2, zone: 1 }], true)).toEqual([{ top: 2, zone: 1 }])
  })
})

describe('isResultsShape', () => {
  it('принимает то, что подходит под число трасс и систему', () => {
    expect(isResultsShape(emptyResults(3), 3, false, 20)).toBe(true)
  })

  it('отвергает другое число трасс и мусор', () => {
    expect(isResultsShape(emptyResults(3), 4, false, 20)).toBe(false)
    expect(isResultsShape('x', 1, false, 20)).toBe(false)
    expect(isResultsShape([null], 1, false, 20)).toBe(false)
    expect(isResultsShape([{ top: 'a', zone: 0 }], 1, false, 20)).toBe(false)
    expect(isResultsShape([{ top: -1, zone: 0 }], 1, false, 20)).toBe(false)
  })

  it('вне французской системы top больше 2 недопустим, во французской можно', () => {
    expect(isResultsShape([{ top: 5, zone: 0 }], 1, false, 20)).toBe(false)
    expect(isResultsShape([{ top: 5, zone: 3 }], 1, true, 20)).toBe(true)
    expect(isResultsShape([{ top: 21, zone: 0 }], 1, true, 20)).toBe(false)
  })
})
