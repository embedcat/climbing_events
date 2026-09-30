// Массовый ввод организатором: `/api/events/<id>/matrix/`. Только для организатора события и суперпользователя.
import type { Gender } from './entry'
import type { Http } from './http'
import type { RouteResult } from '../domain/results'

export interface MatrixParticipant {
  id: number
  last_name: string
  first_name: string
  gender: Gender
  pin: number | null
  group_index: number
  set_index: number
  is_entered_result: boolean
  /** по всем трассам; у тех, кто ещё не вводил, нули */
  results: RouteResult[]
  score: number
  /** счёт строкой: «3T7 4z9» у французской системы, «5/2» у NUM */
  score_view: string
  /** null — результата нет, места тоже */
  place: number | null
}

export interface MatrixEvent {
  id: number
  title: string
  date: string
  /** SUM | PROP | TBL | NUM | FR */
  score_type: string
  routes_num: number
  max_attempts: number
  /** пусто, если группа одна */
  groups: string[]
  /** пусто, если сет один */
  sets: Array<{ index: number; name: string }>
}

export interface MatrixPayload {
  event: MatrixEvent
  participants: MatrixParticipant[]
}

/** Изменения одного участника: только те трассы, которые правили. Ключ — номер трассы с нуля. */
export interface MatrixChange {
  participant: number
  results: Record<string, { top: number; zone?: number }>
}

export interface MatrixSaved extends MatrixPayload {
  saved: { cells: number; participants: number }
}

export interface MatrixApi {
  getMatrix(eventId: number): Promise<MatrixPayload>
  save(eventId: number, changes: MatrixChange[]): Promise<MatrixSaved>
}

export function createMatrixApi(http: Http): MatrixApi {
  return {
    getMatrix: (eventId) => http.get(`/api/events/${eventId}/matrix/`),
    save: (eventId, changes) => http.post(`/api/events/${eventId}/matrix/save/`, { changes }),
  }
}
