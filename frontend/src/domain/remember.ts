// Браузер запоминает участника после регистрации и ввода результатов, а ещё по кнопке «Это я»: на странице события
// появляется карточка «Вы», а в результатах сразу открывается его группа. Это не аккаунт, запись лежит только в браузере.
// PIN не храним.
import { ref, type Ref } from 'vue'
import type { KeyValueStore } from './storage'

export interface RememberedParticipant {
  /** id участника: по нему берём статус оплаты и место. У записей, сделанных до страницы события, его нет */
  id?: number
  first_name: string
  last_name: string
  gender: string
  group_index: number
  set_index?: number
}

const REMEMBER_PREFIX = 'rockevents-me:v1:'
export const rememberKey = (eventId: number): string => `${REMEMBER_PREFIX}${eventId}`

function pick(who: RememberedParticipant): RememberedParticipant {
  const picked: RememberedParticipant = {
    first_name: who.first_name, last_name: who.last_name, gender: who.gender, group_index: who.group_index,
  }
  if (typeof who.id === 'number') picked.id = who.id
  if (typeof who.set_index === 'number') picked.set_index = who.set_index
  return picked
}

export function rememberParticipant(store: KeyValueStore, eventId: number, who: RememberedParticipant): void {
  store.set(rememberKey(eventId), JSON.stringify(pick(who)))
}

export function loadRememberedParticipant(store: KeyValueStore, eventId: number): RememberedParticipant | null {
  const raw = store.get(rememberKey(eventId))
  if (!raw) return null
  try {
    const value = JSON.parse(raw)
    return typeof value.last_name === 'string' ? pick(value) : null
  } catch {
    return null
  }
}

/** Все события, в которых браузер помнит участника: для «Вы участвуете» на главной и строки в меню сайта */
export function listRememberedEvents(store: KeyValueStore): { eventId: number, who: RememberedParticipant }[] {
  const found: { eventId: number, who: RememberedParticipant }[] = []
  for (const key of store.keys()) {
    if (!key.startsWith(REMEMBER_PREFIX)) continue
    const eventId = Number(key.slice(REMEMBER_PREFIX.length))
    if (!Number.isInteger(eventId) || eventId <= 0) continue
    const who = loadRememberedParticipant(store, eventId)
    if (who) found.push({ eventId, who })
  }
  return found.sort((a, b) => b.eventId - a.eventId)
}

export function forgetParticipant(store: KeyValueStore, eventId: number): void {
  store.remove(rememberKey(eventId))
}

export interface RememberedMe {
  me: Ref<RememberedParticipant | null>
  remember(who: RememberedParticipant): void
  forget(): void
}

/** Запомненный участник как общее состояние: страница события, ввод и результаты видят одно и то же. */
export function createRememberedMe(store: KeyValueStore, eventId: number): RememberedMe {
  const me = ref<RememberedParticipant | null>(loadRememberedParticipant(store, eventId))
  return {
    me,
    remember(who) {
      rememberParticipant(store, eventId, who)
      me.value = pick(who)
    },
    forget() {
      forgetParticipant(store, eventId)
      me.value = null
    },
  }
}
