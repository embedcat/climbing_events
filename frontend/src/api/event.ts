// Страница события для участника: `/api/events/<id>/…` (page, participants, registration, me, pay)
import type { Http } from './http'
import type { Gender, GradeChoice, PublicParticipant, RegistrationPayload, Standing } from './entry'

/** Что сейчас с событием: reg — регистрация открыта, reg_closed — закрыта, live — идёт ввод результатов,
 * over — ввод закрыт, done — завершено. */
export type Stage = 'reg' | 'reg_closed' | 'live' | 'over' | 'done'

export interface EventSet {
  index: number
  name: string
  count: number
  /** мест в сете; 0 — без ограничения */
  capacity: number
  is_full: boolean
}

export interface RegType {
  index: number
  name: string
  price: number | null
}

export interface PodiumPlace {
  id: number
  last_name: string
  first_name: string
  place: number
}

export interface PodiumGroup {
  /** null — зачёт без разделения по группам */
  group_index: number | null
  group: string
  male: PodiumPlace[]
  female: PodiumPlace[]
}

export type PayType = 'yoomoney' | 'sbp'

export interface EventPage {
  id: number
  title: string
  date: string
  /** «воскресенье, 4 октября 2026»; у многодневного события — диапазон дат */
  date_long: string
  /** «4 октября» */
  date_short: string
  gym: string
  poster: string | null
  /** HTML описания: пишет организатор */
  description: string
  /** пусто, если группа одна */
  groups: string[]
  /** пусто, если сет один */
  sets: EventSet[]
  stage: Stage
  participants_count: number
  entered_count: number
  is_without_registration: boolean
  is_results_allowed: boolean
  registration: {
    /** регистрация открыта и на неё нужно регистрироваться заранее */
    is_open: boolean
    /** «3 октября, 23:59» */
    until: string | null
    /** null — лимита мест нет */
    free_places: number | null
    min_age: number
    fields: string[]
    required_fields: string[]
    grades: GradeChoice[]
    reg_types: RegType[]
    show_pin: boolean
  }
  pay: { is_allowed: boolean; type: PayType; price: number | null }
  /** только у завершённого события с открытыми результатами */
  podium: PodiumGroup[]
  /** организатор или суперпользователь */
  can_manage: boolean
}

/** Строка публичного списка. Поля pin, phone, email и paid приходят только организатору. */
export interface Person {
  id: number
  last_name: string
  first_name: string
  gender: Gender
  birth_year: number | null
  grade: string
  city: string
  team: string
  group_index: number
  set_index: number
  reg_type_index: number
  entered: boolean
  place: number | null
  place_of: number | null
  pin?: number | null
  phone?: string
  email?: string
  paid?: boolean
}

export interface PeoplePayload {
  participants: Person[]
  can_manage: boolean
}

export interface MePayload {
  participant: PublicParticipant
  paid: boolean
  standing: Standing | null
}

export interface RegistrationResult {
  participant: PublicParticipant
  /** null, если организатор не показывает PIN после регистрации */
  pin: number | null
  paid: boolean
  /** письмо с PIN и ссылкой на оплату ушло на email участника */
  emailed: boolean
}

export type PayInfo =
  | { type: 'paid' }
  | { type: 'yoomoney'; amount: number; receiver: string; label: string; success_url: string; action: string }
  | { type: 'sbp'; amount: number | null; link: string; qr: string }

export interface PromoResult {
  valid: boolean
  /** новая цена взноса, а не скидка */
  price?: number
  promocode_id?: number
}

export interface EventApi {
  getPage(eventId: number): Promise<EventPage>
  getPeople(eventId: number): Promise<PeoplePayload>
  getMe(eventId: number, participantId: number): Promise<MePayload>
  register(eventId: number, fields: RegistrationPayload): Promise<RegistrationResult>
  getPay(eventId: number, participantId: number): Promise<PayInfo>
  checkPromo(eventId: number, code: string): Promise<PromoResult>
}

export function createEventApi(http: Http): EventApi {
  const base = (eventId: number) => `/api/events/${eventId}`
  return {
    getPage: (eventId) => http.get(`${base(eventId)}/page/`),
    getPeople: (eventId) => http.get(`${base(eventId)}/participants/`),
    getMe: (eventId, participantId) => http.get(`${base(eventId)}/me/?participant=${participantId}`),
    register: (eventId, fields) => http.post(`${base(eventId)}/registration/`, fields),
    getPay: (eventId, participantId) => http.get(`${base(eventId)}/pay/?participant=${participantId}`),
    checkPromo: (eventId, code) => http.get(`${base(eventId)}/pay/promo/?code=${encodeURIComponent(code)}`),
  }
}
