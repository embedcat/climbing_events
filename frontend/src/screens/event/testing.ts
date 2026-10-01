// Заготовки для тестов страницы события: страница, участники и подменённый API.
import { vi } from 'vitest'
import type {
  EventApi, EventPage, MePayload, PayInfo, PeoplePayload, Person, RegistrationResult,
} from '../../api/event'
import { ApiError } from '../../api/http'
import { memoryStore } from '../../domain/storage'
import { fakeApi as fakeEntryApi, makeConfig } from '../entry/testing'
import { fakeResultsApi, standardPayload } from '../results/testing'
import { useEventApp } from './useEventApp'

export const EVENT_ID = 7

export function makePage(overrides: Partial<EventPage> = {}): EventPage {
  return {
    id: EVENT_ID,
    title: 'Осенний фестиваль',
    date: '4 октября 2026 г.',
    date_long: 'воскресенье, 4 октября 2026',
    date_short: '4 октября',
    gym: 'Скалодром на Лесной',
    poster: '/media/posters/a.png',
    description: '<h3>Формат</h3><p>Три сета по 2,5 часа.</p>',
    groups: ['Новички', 'Спорт'],
    sets: [
      { index: 0, name: '10:00', count: 14, capacity: 16, is_full: false },
      { index: 1, name: '13:00', count: 16, capacity: 16, is_full: true },
      { index: 2, name: '16:00', count: 12, capacity: 16, is_full: false },
    ],
    stage: 'reg',
    participants_count: 42,
    entered_count: 0,
    is_without_registration: false,
    is_results_allowed: true,
    registration: {
      is_open: true,
      until: '3 октября, 23:59',
      free_places: 6,
      min_age: 14,
      fields: ['gender', 'birth_year', 'grade', 'city', 'team', 'email', 'phone_number'],
      required_fields: ['birth_year'],
      grades: [{ value: 'BR', label: 'б/р' }, { value: '2C', label: '2 сп.р.' }],
      reg_types: [],
      show_pin: true,
    },
    pay: { is_allowed: false, type: 'yoomoney', price: null },
    podium: [],
    can_manage: false,
    ...overrides,
  }
}

export function makePerson(last: string, first: string, overrides: Partial<Person> = {}): Person {
  return {
    id: nextId++,
    last_name: last,
    first_name: first,
    gender: 'MALE',
    birth_year: 1990,
    grade: '1 сп.р.',
    city: 'Москва',
    team: '',
    group_index: 0,
    set_index: 0,
    reg_type_index: 0,
    entered: false,
    place: null,
    place_of: null,
    ...overrides,
  }
}
let nextId = 100

export const standardPeople = (): Person[] => [
  makePerson('Зайцева', 'Юлия', { id: 1, gender: 'FEMALE', group_index: 1, set_index: 2, city: 'Москва', team: 'Магнезия' }),
  makePerson('Кузнецов', 'Алексей', { id: 2, group_index: 0, set_index: 0, city: 'Тверь' }),
  makePerson('Орлова', 'Анна', { id: 3, gender: 'FEMALE', group_index: 0, set_index: 1, city: 'Москва' }),
  makePerson('Соколов', 'Дмитрий', { id: 4, group_index: 1, set_index: 0, city: 'Казань' }),
]

export const apiError = (code: string, status: number, message = 'ошибка', body: Record<string, unknown> = {}) =>
  new ApiError(status, code, message, body)

export function makeMe(overrides: Partial<MePayload> = {}): MePayload {
  return {
    participant: {
      id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1, group: 'Спорт',
      set_index: 2, set: '16:00', reg_type_index: 0, is_entered_result: false,
    },
    paid: false,
    standing: null,
    ...overrides,
  }
}

export function makeRegistered(overrides: Partial<RegistrationResult> = {}): RegistrationResult {
  return { participant: makeMe().participant, pin: 8335, paid: false, emailed: false, ...overrides }
}

/** API страницы события: каждый вызов подменяется в тесте через vi.fn. По умолчанию всё успешно. */
export function fakeEventApi(page: EventPage = makePage(), people: Person[] = standardPeople()) {
  return {
    getPage: vi.fn<EventApi['getPage']>(async () => page),
    getPeople: vi.fn<EventApi['getPeople']>(async (): Promise<PeoplePayload> => ({ participants: people, can_manage: false })),
    getMe: vi.fn<EventApi['getMe']>(async () => makeMe()),
    register: vi.fn<EventApi['register']>(async () => makeRegistered()),
    getPay: vi.fn<EventApi['getPay']>(async (): Promise<PayInfo> => ({
      type: 'yoomoney', amount: 1500, receiver: '4100', label: 'e7_p1', success_url: 'http://x/e/7/pay/done/',
      action: 'https://yoomoney.ru/quickpay/confirm.xml',
    })),
    checkPromo: vi.fn<EventApi['checkPromo']>(async () => ({ valid: false })),
  }
}

export interface AppOptions {
  page?: EventPage
  people?: Person[]
  path?: string
  store?: ReturnType<typeof memoryStore>
}

/** Страница события целиком, с подменёнными API и адресом /e/7/…, который выбирает тест. */
export function makeApp(options: AppOptions = {}) {
  window.history.replaceState(null, '', options.path ?? `/e/${EVENT_ID}/`)
  const api = fakeEventApi(options.page, options.people)
  const entry = fakeEntryApi(makeConfig({ id: EVENT_ID }))
  const results = fakeResultsApi(standardPayload())
  const store = options.store ?? memoryStore()
  const app = useEventApp({
    eventId: EVENT_ID, api, entryApi: entry, resultsApi: results.api, store, manageUrl: `/e/${EVENT_ID}/admin_actions/`,
    now: () => clock.now,
  })
  return { app, api, entry, results, store }
}

/** Время для тестов: двигаем руками. */
export const clock = { now: 1_000_000 }
