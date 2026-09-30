// Матрица массового ввода: какие строки показываем, куда идёт курсор, что попадёт на сервер.
// Всё здесь чистые функции, чтобы клавиатурную логику можно было проверять без браузера.
import type { Gender } from '../api/entry'
import type { MatrixChange, MatrixParticipant } from '../api/matrix'
import type { RouteResult } from './results'

export type Direction = 'right' | 'down'
/** sub: 0 — «топ» (или единственный столбец), 1 — «зона» во французской системе */
export interface Cursor { pid: number; r: number; sub: 0 | 1 }

export interface Filters {
  /** индекс сета, -1 — все */
  set: number
  /** индекс группы, -1 — все */
  group: number
  gender: 'all' | Gender
  /** только те, у кого на сервере ещё нет результата */
  missing: boolean
}

export const defaultFilters = (): Filters => ({ set: -1, group: -1, gender: 'all', missing: false })

// ---- черновик: изменённые ячейки ----

export type Draft = Map<string, RouteResult>

export const cellKey = (pid: number, route: number): string => `${pid}:${route}`

export function parseCellKey(key: string): { pid: number; r: number } {
  const [pid, r] = key.split(':').map(Number)
  return { pid, r }
}

export const sameResult = (a: RouteResult, b: RouteResult, french: boolean): boolean =>
  french ? a.top === b.top && a.zone === b.zone : a.top === b.top

/** Значение ячейки с учётом несохранённого изменения. */
export function cellValue(p: MatrixParticipant, route: number, draft: Draft): RouteResult {
  return draft.get(cellKey(p.id, route)) ?? p.results[route]
}

/**
 * Записывает значение в черновик. Если оно совпало с сохранённым, изменение снимается. Но у участника без
 * результата любое значение, даже «нет», остаётся изменением: карточку перенесли, он считается внёсшим результат.
 */
export function setDraftValue(draft: Draft, p: MatrixParticipant, route: number, value: RouteResult, french: boolean): void {
  const key = cellKey(p.id, route)
  if (p.is_entered_result && sameResult(value, p.results[route], french)) draft.delete(key)
  else draft.set(key, { top: value.top, zone: value.zone })
}

/** Во французской системе зона не может быть позже топа: такие изменения сохранить нельзя. */
export function invalidCells(draft: Draft, french: boolean): Array<{ pid: number; r: number }> {
  if (!french) return []
  const bad: Array<{ pid: number; r: number }> = []
  draft.forEach((value, key) => {
    if (value.top > 0 && value.zone > value.top) bad.push(parseCellKey(key))
  })
  return bad
}

export function draftStats(draft: Draft): { cells: number; participants: number } {
  return { cells: draft.size, participants: new Set([...draft.keys()].map((k) => parseCellKey(k).pid)).size }
}

export const rowHasDraft = (draft: Draft, pid: number, routes: number): boolean => {
  for (let r = 0; r < routes; r++) if (draft.has(cellKey(pid, r))) return true
  return false
}

/** Черновик → тело запроса: по участнику, только изменённые трассы. Вне французской системы только top. */
export function draftToChanges(draft: Draft, french: boolean): MatrixChange[] {
  const byParticipant = new Map<number, MatrixChange>()
  draft.forEach((value, key) => {
    const { pid, r } = parseCellKey(key)
    let change = byParticipant.get(pid)
    if (!change) {
      change = { participant: pid, results: {} }
      byParticipant.set(pid, change)
    }
    change.results[String(r)] = french ? { top: value.top, zone: value.zone } : { top: value.top }
  })
  return [...byParticipant.values()]
}

/** Черновик из браузера → только то, что ещё имеет смысл: участник есть, трасса есть, значения разумные. */
export function restoreDraft(
  raw: unknown, participants: MatrixParticipant[], routes: number, french: boolean, maxAttempts: number,
): Draft {
  const draft: Draft = new Map()
  if (!Array.isArray(raw)) return draft
  const known = new Map(participants.map((p) => [p.id, p]))
  for (const entry of raw) {
    if (!Array.isArray(entry) || typeof entry[0] !== 'string' || typeof entry[1] !== 'object' || entry[1] === null) continue
    const { pid, r } = parseCellKey(entry[0])
    const p = known.get(pid)
    const { top, zone } = entry[1] as Record<string, unknown>
    if (!p || !Number.isInteger(r) || r < 0 || r >= routes) continue
    if (!Number.isInteger(top) || !Number.isInteger(zone)) continue
    const t = top as number
    const z = zone as number
    if (t < 0 || z < 0 || z > maxAttempts || t > (french ? maxAttempts : 2)) continue
    setDraftValue(draft, p, r, { top: t, zone: french ? z : t > 0 ? t : 0 }, french)
  }
  return draft
}

// ---- строки ----

export const byName = (a: MatrixParticipant, b: MatrixParticipant): number =>
  `${a.last_name} ${a.first_name}`.localeCompare(`${b.last_name} ${b.first_name}`, 'ru')

function matchesFilters(p: MatrixParticipant, f: Filters): boolean {
  return (f.set < 0 || p.set_index === f.set)
    && (f.group < 0 || p.group_index === f.group)
    && (f.gender === 'all' || p.gender === f.gender)
}

/** Строки под фильтром по фамилии. missingCount — сколько в выбранных сете, группе и поле без результата. */
export function visibleRows(participants: MatrixParticipant[], f: Filters): { rows: MatrixParticipant[]; missingCount: number } {
  const inScope = participants.filter((p) => matchesFilters(p, f))
  const missingCount = inScope.filter((p) => !p.is_entered_result).length
  const rows = (f.missing ? inScope.filter((p) => !p.is_entered_result) : inScope).slice().sort(byName)
  return { rows, missingCount }
}

/** Фильтры, при которых участник точно виден: нужны, когда к нему переходят поиском. */
export const filtersShowing = (p: MatrixParticipant, hasSets: boolean): Filters => ({
  set: hasSets ? p.set_index : -1, group: -1, gender: 'all', missing: false,
})

export const isVisible = (p: MatrixParticipant, f: Filters): boolean =>
  matchesFilters(p, f) && (!f.missing || !p.is_entered_result)

const normalize = (s: string): string => s.toLowerCase().replace(/ё/g, 'е')

/** Поиск по фамилии, имени или началу PIN. Видимые в таблице идут первыми. */
export function searchParticipants(
  participants: MatrixParticipant[], query: string, isShown: (p: MatrixParticipant) => boolean, limit = 6,
): MatrixParticipant[] {
  const q = normalize(query.trim())
  if (!q) return []
  const byPin = /^\d+$/.test(q)
  return participants
    .filter((p) => byPin
      ? p.pin !== null && String(p.pin).startsWith(q)
      : normalize(`${p.last_name} ${p.first_name}`).includes(q) || normalize(`${p.first_name} ${p.last_name}`).includes(q))
    .sort((a, b) => Number(isShown(b)) - Number(isShown(a)) || byName(a, b))
    .slice(0, limit)
}

// ---- курсор ----

const clamp = (x: number, min: number, max: number): number => Math.max(min, Math.min(max, x))

/** Шаг стрелкой. Во французской системе столбец «т» и «з» каждой трассы — отдельные шаги. */
export function stepCursor(
  rows: MatrixParticipant[], c: Cursor, dRow: number, dCol: number, routes: number, french: boolean,
): Cursor {
  const index = rows.findIndex((p) => p.id === c.pid)
  const row = rows[clamp(index + dRow, 0, rows.length - 1)]
  let { r, sub } = c
  if (dCol) {
    if (french) {
      const flat = clamp(r * 2 + sub + dCol, 0, routes * 2 - 1)
      r = Math.floor(flat / 2)
      sub = (flat % 2) as 0 | 1
    } else {
      r = clamp(r + dCol, 0, routes - 1)
    }
  }
  return { pid: row.id, r, sub }
}

export interface Advance {
  cursor: Cursor
  /** подсказка, если курсор перескочил на другую строку или трассу, или дальше идти некуда */
  hint: string
  /** строка, на которую перескочили: её подсвечиваем */
  jumpedTo: number | null
}

/**
 * Куда идёт курсор после ввода. Направление «вправо»: переносим карточку участника, в конце строки курсор
 * сразу идёт к следующему участнику. «Вниз»: переносим протокол трассы, в конце столбца идёт к следующей трассе.
 */
export function advanceCursor(
  rows: MatrixParticipant[], c: Cursor, direction: Direction, routes: number, french: boolean,
): Advance {
  const stay = (hint = ''): Advance => ({ cursor: c, hint, jumpedTo: null })
  const index = rows.findIndex((p) => p.id === c.pid)
  const last = rows.length - 1
  if (french && c.sub === 0) return { cursor: { ...c, sub: 1 }, hint: '', jumpedTo: null }

  if (direction === 'right') {
    if (c.r < routes - 1) return { cursor: { pid: c.pid, r: c.r + 1, sub: 0 }, hint: '', jumpedTo: null }
    if (index < last) {
      const next = rows[index + 1]
      return { cursor: { pid: next.id, r: 0, sub: 0 }, hint: `Следующий участник: ${next.last_name} ${next.first_name}`, jumpedTo: next.id }
    }
    return stay('Это последний участник в списке.')
  }

  if (index < last) return { cursor: { pid: rows[index + 1].id, r: c.r, sub: 0 }, hint: '', jumpedTo: null }
  if (c.r < routes - 1) {
    return { cursor: { pid: rows[0].id, r: c.r + 1, sub: 0 }, hint: `Следующая трасса: ${c.r + 2}`, jumpedTo: null }
  }
  return stay('Это последняя трасса.')
}

/** Курсор, который остался валидным после смены фильтров: на том же участнике, а если его нет, на первом. */
export function fixCursor(rows: MatrixParticipant[], c: Cursor | null, routes: number, french: boolean): Cursor | null {
  if (!rows.length) return null
  const same = c && rows.some((p) => p.id === c.pid)
  const pid = same ? c!.pid : rows[0].id
  const r = c ? Math.min(c.r, routes - 1) : 0
  return { pid, r, sub: french && c ? c.sub : 0 }
}
