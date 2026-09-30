// Черновик ввода лежит в браузере: заполненное не должно теряться при обрыве связи или закрытой вкладке.
import { isResultsShape, type RouteResult } from './results'
import type { KeyValueStore } from './storage'

const PREFIX = 'rockevents-entry:v1'

export interface Draft {
  results: RouteResult[]
  /** анкета при вводе без регистрации */
  fields: Record<string, unknown> | null
  savedAt: number
}

/** who — PIN участника или 'wo' для ввода без регистрации. */
export const draftKey = (eventId: number, who: string): string => `${PREFIX}:${eventId}:${who}`

export function saveDraft(store: KeyValueStore, key: string, draft: Draft): boolean {
  return store.set(key, JSON.stringify({ v: draft.results, f: draft.fields, ts: draft.savedAt }))
}

export function loadDraft(
  store: KeyValueStore, key: string, count: number, french: boolean, maxAttempts: number,
): Draft | null {
  const raw = store.get(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    // настройки события могли поменяться (число трасс, система подсчёта): такой черновик не подходит
    if (!isResultsShape(parsed.v, count, french, maxAttempts)) return null
    const fields = parsed.f && typeof parsed.f === 'object' ? (parsed.f as Record<string, unknown>) : null
    return { results: parsed.v, fields, savedAt: Number(parsed.ts) || Date.now() }
  } catch {
    return null
  }
}

export const clearDraft = (store: KeyValueStore, key: string): void => store.remove(key)
