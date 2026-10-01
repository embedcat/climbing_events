// Публичный список участников: поиск, фильтры и подписи.
import type { Person } from '../api/event'
import { plural } from './format'

export type GenderFilter = 'all' | 'MALE' | 'FEMALE'

export interface PeopleFilters {
  gender: GenderFilter
  /** -1 — все группы */
  group: number
  /** -1 — все сеты */
  set: number
  q: string
}

export const emptyFilters = (): PeopleFilters => ({ gender: 'all', group: -1, set: -1, q: '' })

export const isFiltered = (f: PeopleFilters): boolean =>
  f.gender !== 'all' || f.group >= 0 || f.set >= 0 || f.q.trim() !== ''

export const genderLetter = (gender: string): string => (gender === 'FEMALE' ? 'Ж' : 'М')

export const personName = (p: Pick<Person, 'last_name' | 'first_name'>): string => `${p.last_name} ${p.first_name}`

/** «Зайцева Ю.»: имя в списках призёров и таблицах. */
export const shortPersonName = (p: Pick<Person, 'last_name' | 'first_name'>): string =>
  `${p.last_name} ${p.first_name.charAt(0)}.`

export const byName = (a: Person, b: Person): number => personName(a).localeCompare(personName(b), 'ru')

export function matchesQuery(p: Person, query: string): boolean {
  const q = query.trim().toLowerCase()
  if (!q) return true
  return `${p.last_name} ${p.first_name}`.toLowerCase().includes(q) || `${p.first_name} ${p.last_name}`.toLowerCase().includes(q)
}

export function filterPeople(people: Person[], f: PeopleFilters): Person[] {
  return people
    .filter((p) => (f.gender === 'all' || p.gender === f.gender)
      && (f.group < 0 || p.group_index === f.group)
      && (f.set < 0 || p.set_index === f.set)
      && matchesQuery(p, f.q))
    .sort(byName)
}

/** Строка под списком: «Москва 5 · Тверь 3 · ещё 2 города». Пустая, если города никто не указал. */
export function cityLine(people: Person[], shown = 3): string {
  const counts = new Map<string, number>()
  for (const p of people) {
    const city = p.city.trim()
    if (city) counts.set(city, (counts.get(city) ?? 0) + 1)
  }
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1])
  if (!top.length) return ''
  const rest = top.length - shown
  const line = top.slice(0, shown).map(([city, n]) => `${city} ${n}`).join(' · ')
  return rest > 0 ? `${line} · ещё ${rest} ${plural(rest, 'город', 'города', 'городов')}` : line
}

/** Строка данных на телефоне: «1996 · 2 сп.р. · Москва · «Магнезия»». */
export function personMeta(p: Person): string {
  return [p.birth_year, p.grade, p.city, p.team ? `«${p.team}»` : ''].filter(Boolean).join(' · ')
}
