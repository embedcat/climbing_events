// Заготовки для тестов массового ввода: участники, события и подменённый API.
import { vi } from 'vitest'
import type { Gender } from '../../api/entry'
import type { MatrixApi, MatrixEvent, MatrixParticipant, MatrixPayload, MatrixSaved } from '../../api/matrix'
import { emptyResults, type RouteResult } from '../../domain/results'

let nextId = 1

/** Участник с результатами: res(2, 1) — redpoint на первой трассе, flash на второй, остальные «нет». */
export function person(
  last: string, first: string, routes: number, overrides: Partial<MatrixParticipant> = {}, results: RouteResult[] = [],
): MatrixParticipant {
  const entered = overrides.is_entered_result ?? results.length > 0
  const filled = emptyResults(routes).map((empty, i) => results[i] ?? empty)
  return {
    id: nextId++,
    last_name: last,
    first_name: first,
    gender: 'MALE' as Gender,
    pin: 1000 + nextId,
    group_index: 0,
    set_index: 0,
    is_entered_result: entered,
    results: filled,
    score: 0,
    score_view: '0',
    place: entered ? 1 : null,
    ...overrides,
  }
}

export const tops = (...values: number[]): RouteResult[] => values.map((top) => ({ top, zone: 0 }))
export const pairs = (...values: Array<[number, number]>): RouteResult[] => values.map(([top, zone]) => ({ top, zone }))

export function makeEvent(overrides: Partial<MatrixEvent> = {}): MatrixEvent {
  return {
    id: 7,
    title: 'Осенний фестиваль',
    date: '4 октября 2026 г.',
    score_type: 'PROP',
    routes_num: 6,
    max_attempts: 20,
    groups: [],
    sets: [],
    ...overrides,
  }
}

export function makeMatrix(participants: MatrixParticipant[], event: Partial<MatrixEvent> = {}): MatrixPayload {
  return { event: makeEvent(event), participants }
}

/**
 * Обычное событие: шесть трасс, два сета, две группы.
 * Андреев (внёс, сет 1), Борисов (внёс, сет 1), Власов (нет результата, сет 1), Гаврилов (нет, сет 2),
 * Зайцева (внесла, сет 2, женщина), Титова (нет, сет 2, женщина).
 */
export function standardMatrix(event: Partial<MatrixEvent> = {}): MatrixPayload {
  nextId = 1
  const n = event.routes_num ?? 6
  const fr = event.score_type === 'FR'
  const done = (...values: number[]) => (fr ? pairs(...values.map((v): [number, number] => [v, v])) : tops(...values))
  return makeMatrix([
    person('Андреев', 'Иван', n, { place: 1, pin: 1111 }, done(2, 1, 2)),
    person('Борисов', 'Пётр', n, { place: 2, pin: 2222 }, done(2, 0, 0, 2)),
    person('Власов', 'Глеб', n, { pin: 3333 }),
    person('Гаврилов', 'Олег', n, { set_index: 1, group_index: 1, pin: 4444 }),
    person('Зайцева', 'Юлия', n, { set_index: 1, gender: 'FEMALE', place: 1, pin: 5555 }, done(1, 1, 1)),
    person('Титова', 'Полина', n, { set_index: 1, gender: 'FEMALE', pin: 6666 }),
  ], { groups: ['Новички', 'Спорт'], sets: [{ index: 0, name: '10:00' }, { index: 1, name: '13:00' }], ...event })
}

/** API: getMatrix отдаёт state.current; save применяет изменения к state.current, как сервер (места не пересчитывает). */
export function fakeMatrixApi(initial: MatrixPayload) {
  const state = { current: initial }
  const api = {
    getMatrix: vi.fn<MatrixApi['getMatrix']>(async () => JSON.parse(JSON.stringify(state.current))),
    save: vi.fn<MatrixApi['save']>(async (_id, changes): Promise<MatrixSaved> => {
      const next = JSON.parse(JSON.stringify(state.current)) as MatrixPayload
      let cells = 0
      for (const change of changes) {
        const p = next.participants.find((x) => x.id === change.participant)!
        for (const [route, cell] of Object.entries(change.results)) {
          const top = cell.top
          p.results[Number(route)] = { top, zone: cell.zone ?? (top > 0 ? top : 0) }
          cells++
        }
        p.is_entered_result = true
        p.place = p.place ?? 1
      }
      state.current = next
      return { ...next, saved: { cells, participants: changes.length } }
    }),
  }
  return { api, state }
}
