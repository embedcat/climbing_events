// Таблицы результатов: поиск строк, подписи ячеек и счёта, сравнение двух обновлений.
import type { Gender } from '../api/entry'
import type { ResultRow, ResultsPayload, ResultsTable } from '../api/results'
import type { RememberedParticipant } from './remember'
import type { RouteResult } from './results'

export const isFrenchScore = (scoreType: string): boolean => scoreType === 'FR'

/** Системы, где счёт — число очков. У остальных (французская: «3T7 4z9», NUM: «5/2») берём готовую строку. */
const POINTS_SCORE_TYPES = ['SUM', 'PROP', 'TBL']

const scoreFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2, useGrouping: false })

export const formatScore = (row: ResultRow, scoreType: string): string =>
  POINTS_SCORE_TYPES.includes(scoreType) ? scoreFormat.format(row.score) : row.score_view

const pointsFormat = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1, useGrouping: false })

/** Очки за трассу в нижней строке таблицы: одного знака после запятой хватает, столбцы узкие. */
export const formatPoints = (value: number): string => pointsFormat.format(value)

export const shortName = (row: Pick<ResultRow, 'last_name' | 'first_name'>): string =>
  `${row.last_name} ${row.first_name.charAt(0)}.`

export const fullName = (row: Pick<ResultRow, 'last_name' | 'first_name'>): string =>
  `${row.last_name} ${row.first_name}`

export const genderLabel = (gender: Gender): string => (gender === 'FEMALE' ? 'женщины' : 'мужчины')

// ---- поиск ----

export const tableKey = (table: Pick<ResultsTable, 'gender' | 'group_index'>): string =>
  `${table.gender}:${table.group_index}`

export const allRows = (table: ResultsTable): ResultRow[] => [...table.ranked, ...table.waiting]

export function findTable(payload: ResultsPayload, gender: Gender, groupIndex: number): ResultsTable | null {
  return payload.tables.find((t) => t.gender === gender && t.group_index === groupIndex) ?? null
}

export function findRow(payload: ResultsPayload, id: number): { row: ResultRow; table: ResultsTable } | null {
  for (const table of payload.tables) {
    const row = allRows(table).find((r) => r.id === id)
    if (row) return { row, table }
  }
  return null
}

/** Запомненный на телефоне участник в таблице: находим по имени и фамилии, регистр не важен. */
export function findRemembered(payload: ResultsPayload, me: RememberedParticipant | null): number | null {
  if (!me) return null
  const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase()
  for (const table of payload.tables) {
    if (table.gender !== me.gender) continue
    const row = allRows(table).find((r) => same(r.last_name, me.last_name) && same(r.first_name, me.first_name))
    if (row) return row.id
  }
  return null
}

// ---- ячейки и карточка ----

export interface CellView {
  text: string
  /** fl/rp: flash и redpoint; top/zone: французская система, топ и только зона */
  kind: '' | 'fl' | 'rp' | 'top' | 'zone'
  /** пролаз есть, но трасса не вошла в зачёт (считаются N лучших) */
  dim: boolean
}

export function cellView(result: RouteResult | undefined, french: boolean, counted: boolean): CellView {
  if (!result) return { text: '', kind: '', dim: false }
  if (french) {
    if (result.top > 0) return { text: `${result.top}/${result.zone || '–'}`, kind: 'top', dim: false }
    if (result.zone > 0) return { text: `–/${result.zone}`, kind: 'zone', dim: false }
    return { text: '', kind: '', dim: false }
  }
  if (result.top === 1) return { text: 'FL', kind: 'fl', dim: !counted }
  if (result.top === 2) return { text: 'RP', kind: 'rp', dim: !counted }
  return { text: '', kind: '', dim: false }
}

export function flashRedpointTotals(results: RouteResult[]): { flash: number; redpoint: number } {
  return {
    flash: results.filter((r) => r.top === 1).length,
    redpoint: results.filter((r) => r.top === 2).length,
  }
}

/** Топы и зоны французской системы: сколько взято и за сколько попыток в сумме. */
export function frenchTotals(results: RouteResult[]): { tops: number; topAttempts: number; zones: number; zoneAttempts: number } {
  const totals = { tops: 0, topAttempts: 0, zones: 0, zoneAttempts: 0 }
  for (const r of results) {
    if (r.top > 0) { totals.tops++; totals.topAttempts += r.top }
    if (r.zone > 0) { totals.zones++; totals.zoneAttempts += r.zone }
  }
  return totals
}

export function formatAgo(seconds: number): string {
  if (seconds < 10) return 'обновлено только что'
  if (seconds < 60) return `обновлено ${Math.floor(seconds)} с назад`
  return `обновлено ${Math.floor(seconds / 60)} мин назад`
}

// ---- что изменилось между двумя обновлениями ----

export interface ChangeEvent {
  id: number
  name: string
  gender: Gender
  group: string
  groupIndex: number
  /** entered — ввёл результат впервые, corrected — исправил */
  kind: 'entered' | 'corrected'
}

export interface ResultsDiff {
  /** на сколько мест поднялся участник (минус — опустился) */
  deltas: Map<number, number>
  /** у кого изменилось место или результат */
  changed: Set<number>
  events: ChangeEvent[]
}

export function diffResults(prev: ResultsPayload, next: ResultsPayload): ResultsDiff {
  const before = new Map<number, ResultRow>()
  for (const table of prev.tables) for (const row of allRows(table)) before.set(row.id, row)

  const diff: ResultsDiff = { deltas: new Map(), changed: new Set(), events: [] }
  for (const table of next.tables) {
    for (const row of allRows(table)) {
      const old = before.get(row.id)
      if (row.place === null) continue

      const event = (kind: ChangeEvent['kind']) => diff.events.push({
        id: row.id, name: fullName(row), gender: row.gender, group: table.group, groupIndex: table.group_index, kind,
      })
      if (!old || old.place === null) {
        event('entered')
        diff.changed.add(row.id)
        continue
      }
      if (JSON.stringify(old.results) !== JSON.stringify(row.results)) {
        event('corrected')
        diff.changed.add(row.id)
      }
      if (old.place !== row.place) {
        diff.deltas.set(row.id, old.place - row.place)
        diff.changed.add(row.id)
      }
    }
  }
  return diff
}

/** Короткое сообщение внизу экрана: кто ввёл результат. */
export function changeMessage(events: ChangeEvent[], isVisibleTable: (event: ChangeEvent) => boolean): string {
  if (events.length === 0) return ''
  if (events.length > 1) return `Обновились результаты: ${events.length}`
  const [e] = events
  const female = e.gender === 'FEMALE'
  const verb = e.kind === 'entered' ? (female ? 'ввела' : 'ввёл') : (female ? 'исправила' : 'исправил')
  const where = isVisibleTable(e) ? '' : ` (${[e.group, female ? 'Ж' : 'М'].filter(Boolean).join(', ')})`
  return `${e.name} ${verb} результат${where}`
}
