// Результаты участника по трассам. Формат совпадает с API (`/api/events/<id>/entry/…`).
// Вне французской системы top: 0 — нет, 1 — flash, 2 — redpoint, zone не используется.
// Во французской top и zone — номера попыток, 0 — не взяли.

export interface RouteResult {
  top: number
  zone: number
}

export type AttemptKind = 'top' | 'zone'

export interface Summary {
  flash: number
  redpoint: number
  tops: number
  zones: number
  marked: number
}

export const emptyResults = (count: number): RouteResult[] =>
  Array.from({ length: count }, () => ({ top: 0, zone: 0 }))

export const cloneResults = (results: RouteResult[]): RouteResult[] => results.map((r) => ({ ...r }))

/** Нажатие на плитку: нет → flash → redpoint → нет. */
export const cycleTile = (result: RouteResult): RouteResult => ({ top: (result.top + 1) % 3, zone: 0 })

/**
 * Счётчик попыток во французской системе. Повторяет правила формы:
 * топ без зоны тянет зону на ту же попытку, при топе зона не может быть меньше первой попытки.
 */
export function stepAttempt(result: RouteResult, kind: AttemptKind, delta: number, max: number): RouteResult {
  const clamp = (value: number, min: number) => Math.max(min, Math.min(max, value))
  if (kind === 'top') {
    const top = clamp(result.top + delta, 0)
    return { top, zone: top > 0 && result.zone === 0 ? top : result.zone }
  }
  return { top: result.top, zone: clamp(result.zone + delta, result.top > 0 ? 1 : 0) }
}

/** Индексы трасс (с нуля), где зона позже топа. Сервер отклоняет такие результаты. */
export const invalidFrenchRoutes = (results: RouteResult[]): number[] =>
  results.flatMap((r, i) => (r.top > 0 && r.zone > r.top ? [i] : []))

export function summarize(results: RouteResult[], french: boolean): Summary {
  const summary: Summary = { flash: 0, redpoint: 0, tops: 0, zones: 0, marked: 0 }
  for (const r of results) {
    if (french) {
      if (r.top > 0) summary.tops++
      if (r.zone > 0) summary.zones++
      if (r.top > 0 || r.zone > 0) summary.marked++
    } else {
      if (r.top === 1) summary.flash++
      if (r.top === 2) summary.redpoint++
      if (r.top > 0) summary.marked++
    }
  }
  return summary
}

/** Что отправляем на сервер: вне французской системы достаточно top. */
export const toPayload = (results: RouteResult[], french: boolean): Array<{ top: number; zone?: number }> =>
  results.map((r) => (french ? { top: r.top, zone: r.zone } : { top: r.top }))

/** Подходит ли пришедшее из хранилища значение под текущие настройки события. */
export function isResultsShape(
  value: unknown, count: number, french: boolean, maxAttempts: number,
): value is RouteResult[] {
  if (!Array.isArray(value) || value.length !== count) return false
  return value.every((item) => {
    if (typeof item !== 'object' || item === null) return false
    const { top, zone } = item as Record<string, unknown>
    if (!Number.isInteger(top) || !Number.isInteger(zone)) return false
    const t = top as number
    const z = zone as number
    return t >= 0 && z >= 0 && z <= maxAttempts && (french ? t <= maxAttempts : t <= 2)
  })
}
