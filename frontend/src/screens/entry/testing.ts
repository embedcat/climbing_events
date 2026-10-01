// Заготовки для тестов экрана ввода: событие, участник и подменённый API.
import { vi } from 'vitest'
import type { EntryApi, EntryConfig, EntryPayload, PublicParticipant } from '../../api/entry'
import { ApiError } from '../../api/http'
import { emptyResults, type RouteResult } from '../../domain/results'

export function makeConfig(overrides: Partial<EntryConfig> = {}): EntryConfig {
  return {
    id: 7,
    title: 'Осенний фестиваль',
    date: '4 октября 2026 г.',
    gym: 'Скалодром',
    score_type: 'PROP',
    routes_num: 10,
    max_attempts: 20,
    groups: [],
    sets: [],
    grades: [{ value: 'BR', label: 'б/р' }, { value: '1C', label: '1 сп.р.' }],
    registration_fields: ['gender'],
    required_fields: [],
    is_enter_result_allowed: true,
    is_without_registration: false,
    is_check_result_before_enter: false,
    is_update_result_allowed: true,
    ...overrides,
  }
}

export function makeParticipant(overrides: Partial<PublicParticipant> = {}): PublicParticipant {
  return {
    id: 1,
    first_name: 'Юлия',
    last_name: 'Зайцева',
    gender: 'FEMALE',
    group_index: 0,
    group: '',
    set_index: 0,
    set: '',
    reg_type_index: 0,
    is_entered_result: false,
    ...overrides,
  }
}

export function makePayload(config: EntryConfig, overrides: Partial<EntryPayload> = {}): EntryPayload {
  return {
    participant: makeParticipant(),
    results: emptyResults(config.routes_num),
    ...overrides,
  }
}

export const apiError = (code: string, status: number, message = 'ошибка', body: Record<string, unknown> = {}) =>
  new ApiError(status, code, message, body)

export const networkError = () => new ApiError(0, 'network', 'Нет связи с сервером.')

/** API, в котором каждый вызов подменяется в тесте через vi.fn. По умолчанию всё успешно. */
export function fakeApi(config: EntryConfig = makeConfig()) {
  const api = {
    getConfig: vi.fn<EntryApi['getConfig']>(async () => config),
    identify: vi.fn<EntryApi['identify']>(async () => makePayload(config)),
    submit: vi.fn<EntryApi['submit']>(async (_id, _pin, results: RouteResult[]) => makePayload(config, {
      results, standing: { place: 3, of: 9 },
    })),
    submitWithoutRegistration: vi.fn<EntryApi['submitWithoutRegistration']>(async (_id, _fields, results: RouteResult[]) =>
      makePayload(config, { results, standing: { place: 1, of: 1 } })),
  }
  return api
}
