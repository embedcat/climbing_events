// Заготовки для тестов главной и кабинета: карточки событий и подменённый API.
import { vi } from 'vitest'
import { ApiError } from '../../api/http'
import type { MyEventCard, MyEvents, Participation, SiteApi, SiteCatalog, SiteEventCard } from '../../api/site'

export function makeCard(patch: Partial<SiteEventCard> = {}): SiteEventCard {
  return {
    id: 128, title: 'Осенний фестиваль', date: '4 октября 2026 г.', gym: 'Скалодром на Лесной',
    short_description: 'Три сета, 15 трасс.', poster: '/media/posters/a.png', stage: 'reg',
    is_results_allowed: true, is_without_registration: false, mine: false, ...patch,
  }
}

export function makeMyCard(patch: Partial<MyEventCard> = {}): MyEventCard {
  return {
    ...makeCard(), participants_count: 42, entered_count: 0, paid_count: 31, is_pay_allowed: true, is_premium: true,
    owner: null, ...patch,
  }
}

export function makeCatalog(patch: Partial<SiteCatalog> = {}): SiteCatalog {
  return { results: [makeCard()], counts: { upcoming: 1, past: 0 }, has_more: false, ...patch }
}

export function makeMyEvents(patch: Partial<MyEvents> = {}): MyEvents {
  return { scope: 'mine', is_superuser: false, results: [makeMyCard()], ...patch }
}

export function makeParticipation(patch: Partial<Participation> = {}): Participation {
  return {
    event: makeCard(),
    me: { paid: false, pay_required: true, standing: null, group: 'Спорт', set: '16:00', set_index: 2 },
    ...patch,
  }
}

export type FakeSiteApi = { [K in keyof SiteApi]: ReturnType<typeof vi.fn<SiteApi[K]>> }

export function fakeSiteApi(overrides: Partial<SiteApi> = {}): FakeSiteApi {
  return {
    events: vi.fn<SiteApi['events']>(async () => makeCatalog()),
    participations: vi.fn<SiteApi['participations']>(async () => []),
    myEvents: vi.fn<SiteApi['myEvents']>(async () => makeMyEvents()),
    ...overrides,
  } as FakeSiteApi
}

export const networkError = (): ApiError => new ApiError(0, 'network', 'Нет связи с сервером.')
