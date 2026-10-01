// Эндпоинты ввода результатов участником: `/api/events/<id>/entry/…`
import type { Http } from './http'
import { toPayload, type RouteResult } from '../domain/results'

export type Gender = 'MALE' | 'FEMALE'

export interface SetChoice {
  index: number
  name: string
  is_full: boolean
}

export interface GradeChoice {
  value: string
  label: string
}

export interface EntryConfig {
  id: number
  title: string
  date: string
  gym: string
  /** SUM | PROP | TBL | NUM | FR */
  score_type: string
  routes_num: number
  max_attempts: number
  /** пусто, если группа одна */
  groups: string[]
  /** пусто, если сет один */
  sets: SetChoice[]
  grades: GradeChoice[]
  registration_fields: string[]
  required_fields: string[]
  is_enter_result_allowed: boolean
  is_without_registration: boolean
  is_check_result_before_enter: boolean
  is_update_result_allowed: boolean
}

export interface PublicParticipant {
  id: number
  first_name: string
  last_name: string
  gender: Gender
  group_index: number
  group: string
  set_index: number
  set: string
  /** тип регистрации: от него зависит цена взноса */
  reg_type_index: number
  is_entered_result: boolean
}

export interface Standing {
  place: number
  of: number
}

export interface EntryPayload {
  participant: PublicParticipant
  results: RouteResult[]
  /** null: организатор скрыл результаты, места не показываем */
  standing?: Standing | null
  /** повторный ввод запрещён, а участник уже вносил результат: его отметки только для просмотра */
  locked?: boolean
}

/** Анкета при вводе без регистрации. Набор полей зависит от настроек события. */
export type RegistrationPayload = Record<string, string | number>

export const isFrench = (config: Pick<EntryConfig, 'score_type'>): boolean => config.score_type === 'FR'

export interface EntryApi {
  getConfig(eventId: number): Promise<EntryConfig>
  identify(eventId: number, pin: string): Promise<EntryPayload>
  submit(eventId: number, pin: string, results: RouteResult[], french: boolean): Promise<EntryPayload>
  submitWithoutRegistration(
    eventId: number, fields: RegistrationPayload, results: RouteResult[], french: boolean,
  ): Promise<EntryPayload>
}

export function createEntryApi(http: Http): EntryApi {
  const base = (eventId: number) => `/api/events/${eventId}/entry`
  return {
    getConfig: (eventId) => http.get(`${base(eventId)}/config/`),
    identify: (eventId, pin) => http.post(`${base(eventId)}/identify/`, { pin }),
    submit: (eventId, pin, results, french) =>
      http.post(`${base(eventId)}/submit/`, { pin, results: toPayload(results, french) }),
    submitWithoutRegistration: (eventId, fields, results, french) =>
      http.post(`${base(eventId)}/submit-without-registration/`, { ...fields, results: toPayload(results, french) }),
  }
}
