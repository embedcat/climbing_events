// Главная и кабинет организатора: `/api/site/{events,participations,my-events}/`
import type { Standing } from './entry'
import type { Stage } from './event'
import type { Http } from './http'

/** Этап события плюс draft: событие не опубликовано, его видит только владелец и суперпользователь. */
export type SiteStage = Stage | 'draft'

export interface SiteEventCard {
  id: number
  title: string
  /** «4 октября 2026 г.» или диапазон дат */
  date: string
  gym: string
  short_description: string | null
  poster: string | null
  stage: SiteStage
  is_results_allowed: boolean
  is_without_registration: boolean
  /** событие текущего пользователя */
  mine: boolean
}

export interface SiteCatalog {
  results: SiteEventCard[]
  counts: { upcoming: number, past: number }
  has_more: boolean
}

export type CatalogPeriod = 'upcoming' | 'past'

/** Что сервер знает про запомненного в браузере участника: статус оплаты, место, сет. */
export interface ParticipationMe {
  paid: boolean
  /** у события есть оплата взноса */
  pay_required: boolean
  standing: Standing | null
  group: string
  set: string
  set_index: number
}

export interface Participation {
  event: SiteEventCard
  me: ParticipationMe | null
}

/** Событие в кабинете организатора: карточка и числа. owner — только в режиме «все события сайта». */
export interface MyEventCard extends SiteEventCard {
  participants_count: number
  entered_count: number
  paid_count: number
  is_pay_allowed: boolean
  is_premium: boolean
  owner: string | null
}

export type MyEventsScope = 'mine' | 'all'

export interface MyEvents {
  scope: MyEventsScope
  is_superuser: boolean
  results: MyEventCard[]
}

/** Запись из браузера: событие и, если помним, участник в нём. */
export interface ParticipationRef {
  eventId: number
  participantId?: number
}

export interface SiteApi {
  events(params: { query: string, when: CatalogPeriod, offset: number }): Promise<SiteCatalog>
  participations(refs: ParticipationRef[]): Promise<Participation[]>
  myEvents(scope: MyEventsScope): Promise<MyEvents>
}

export function createSiteApi(http: Http): SiteApi {
  return {
    events: ({ query, when, offset }) => {
      const params = new URLSearchParams({ when })
      if (query.trim()) params.set('q', query.trim())
      if (offset > 0) params.set('offset', String(offset))
      return http.get<SiteCatalog>(`/api/site/events/?${params}`)
    },
    participations: async (refs) => {
      const value = refs.map((r) => (r.participantId ? `${r.eventId}:${r.participantId}` : String(r.eventId))).join(',')
      const body = await http.get<{ results: Participation[] }>(`/api/site/participations/?refs=${encodeURIComponent(value)}`)
      return body.results
    },
    myEvents: (scope) => http.get<MyEvents>(`/api/site/my-events/?scope=${scope}`),
  }
}
