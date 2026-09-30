// Заготовки для тестов экрана результатов: таблицы, участники и подменённый API.
import { vi } from 'vitest'
import type { Gender } from '../../api/entry'
import type { ResultRow, ResultsApi, ResultsPayload, ResultsTable } from '../../api/results'
import type { RouteResult } from '../../domain/results'

/** Результаты PROP по трассам: res(2, 1, 0) — redpoint, flash, нет. */
export const res = (...tops: number[]): RouteResult[] => tops.map((top) => ({ top, zone: 0 }))
/** Результаты французской системы: fr([3, 2], [0, 4]) — топ с 3-й попытки и зона со 2-й; только зона с 4-й. */
export const fr = (...pairs: Array<[number, number]>): RouteResult[] => pairs.map(([top, zone]) => ({ top, zone }))

let nextId = 1

export function makeRow(last: string, first: string, place: number | null, results: RouteResult[] = [],
  overrides: Partial<ResultRow> = {}): ResultRow {
  return {
    id: nextId++,
    last_name: last,
    first_name: first,
    gender: 'MALE',
    birth_year: 1995,
    grade: 'б/р',
    city: 'Москва',
    team: '',
    set_index: 0,
    set: '',
    place,
    score: place === null ? 0 : 200 - place * 10,
    score_view: place === null ? '0' : String(200 - place * 10),
    results: place === null ? [] : results,
    counted: results.map((r) => r.top > 0),
    ...overrides,
  }
}

export function makeTable(gender: Gender, groupIndex: number, group: string, ranked: ResultRow[],
  waiting: ResultRow[] = [], overrides: Partial<ResultsTable> = {}): ResultsTable {
  return {
    gender,
    group_index: groupIndex,
    group,
    route_points: null,
    ranked: ranked.map((r) => ({ ...r, gender })),
    waiting: waiting.map((r) => ({ ...r, gender })),
    ...overrides,
  }
}

interface PayloadOptions {
  score_type?: string
  routes_num?: number
  groups?: string[]
  is_live?: boolean
  is_expired?: boolean
  can_edit?: boolean
  is_view_full_results?: boolean
  best_routes_num?: number
  routes?: ResultsPayload['routes']
}

export function makePayload(tables: ResultsTable[], options: PayloadOptions = {}): ResultsPayload {
  const routesNum = options.routes_num ?? 5
  return {
    event: {
      id: 7,
      title: 'Осенний фестиваль',
      date: '4 октября 2026 г.',
      gym: 'Скалодром',
      score_type: options.score_type ?? 'PROP',
      routes_num: routesNum,
      is_live: options.is_live ?? true,
      is_expired: options.is_expired ?? false,
      can_edit: options.can_edit ?? false,
    },
    display: {
      is_view_full_results: options.is_view_full_results ?? true,
      best_routes_num: options.best_routes_num ?? 0,
    },
    routes: options.routes ?? Array.from({ length: routesNum }, (_, i) => ({ number: i + 1, grade: null, color: null })),
    groups: options.groups ?? [],
    tables,
  }
}

/**
 * Обычное событие для тестов: две группы, у мужчин и женщин по таблице.
 * Мужчины/Новички: Андреев (1 место), Борисов (2), Власов без результата.
 */
export function standardPayload(options: PayloadOptions = {}): ResultsPayload {
  const promo = (last: string, first: string, place: number, results: RouteResult[], o: Partial<ResultRow> = {}) =>
    makeRow(last, first, place, results, o)
  return makePayload([
    makeTable('MALE', 0, 'Новички', [
      promo('Андреев', 'Иван', 1, res(2, 1, 2, 0, 0), { score: 180.5, score_view: '180.5', team: 'Скала', set: '10:00' }),
      promo('Борисов', 'Пётр', 2, res(2, 0, 0, 2, 0), { score: 120, score_view: '120' }),
    ], [makeRow('Власов', 'Глеб', null)], {
      route_points: [{ flash: 62.5, redpoint: 50 }, { flash: 100, redpoint: 80 }, { flash: 62.5, redpoint: 50 },
        { flash: 100, redpoint: 80 }, { flash: 0, redpoint: 0 }],
    }),
    makeTable('MALE', 1, 'Спорт', [promo('Гаврилов', 'Олег', 1, res(1, 1, 1, 1, 1))]),
    makeTable('FEMALE', 0, 'Новички', [
      promo('Зайцева', 'Юлия', 1, res(2, 2, 0, 0, 2), { birth_year: null, grade: 'КМС' }),
    ], [makeRow('Титова', 'Полина', null), makeRow('Уварова', 'Алла', null)]),
    makeTable('FEMALE', 1, 'Спорт', []),
  ], { groups: ['Новички', 'Спорт'], ...options })
}

/** API, которое отдаёт то, что лежит в current; тесты меняют current, чтобы «обновить результаты на сервере». */
export function fakeResultsApi(initial: ResultsPayload) {
  const state = { current: initial }
  const api = {
    getResults: vi.fn<ResultsApi['getResults']>(async () => JSON.parse(JSON.stringify(state.current))),
  }
  return { api, state }
}
