// Телефон запоминает участника после ввода результатов: в результатах сразу откроется его группа.
// Это не аккаунт, запись лежит только в браузере. PIN не храним.
import type { KeyValueStore } from './storage'

export interface RememberedParticipant {
  first_name: string
  last_name: string
  gender: string
  group_index: number
}

export const rememberKey = (eventId: number): string => `rockevents-me:v1:${eventId}`

export function rememberParticipant(store: KeyValueStore, eventId: number, who: RememberedParticipant): void {
  store.set(rememberKey(eventId), JSON.stringify({
    first_name: who.first_name, last_name: who.last_name, gender: who.gender, group_index: who.group_index,
  }))
}

export function loadRememberedParticipant(store: KeyValueStore, eventId: number): RememberedParticipant | null {
  const raw = store.get(rememberKey(eventId))
  if (!raw) return null
  try {
    const value = JSON.parse(raw)
    return typeof value.last_name === 'string' ? value : null
  } catch {
    return null
  }
}
