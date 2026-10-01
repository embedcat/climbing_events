// Заготовки для тестов панели события: обзор и подменённый API.
import { vi } from 'vitest'
import type { PanelApi, PanelOverview } from '../../api/panel'

export const EVENT_ID = 128

export function makeOverview(patch: Partial<PanelOverview> = {}): PanelOverview {
  return {
    id: EVENT_ID, title: 'Осенний фестиваль', date: '4 октября 2026 г.', gym: 'Скалодром на Лесной', stage: 'reg',
    is_expired: false, is_premium: true, is_pay_allowed: true,
    flags: { is_published: true, is_registration_open: true, is_enter_result_allowed: false, is_results_allowed: true },
    participants_count: 42, entered_count: 0, paid_count: 31,
    checklist: [
      { id: 'description', done: true, poster: true },
      { id: 'pay', done: true, optional: true, price: 1500 },
      { id: 'publish', done: true },
    ],
    ...patch,
  }
}

export type FakePanelApi = { [K in keyof PanelApi]: ReturnType<typeof vi.fn<PanelApi[K]>> }

/** По умолчанию переключатель просто применяется к обзору, как это делает сервер. */
export function fakePanelApi(base: PanelOverview = makeOverview(), overrides: Partial<PanelApi> = {}): FakePanelApi {
  let state = base
  return {
    overview: vi.fn<PanelApi['overview']>(async () => state),
    setFlags: vi.fn<PanelApi['setFlags']>(async (_id, flags) => {
      state = { ...state, flags: { ...state.flags, ...flags } }
      return state
    }),
    runAction: vi.fn<PanelApi['runAction']>(async () => state),
    ...overrides,
  } as FakePanelApi
}
