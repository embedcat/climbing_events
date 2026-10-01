// Панель события организатора: `/api/events/<id>/panel/` (обзор, переключатели, служебные действия)
import type { Http } from './http'
import type { SiteStage } from './site'

/** Четыре переключателя дня события: их дёргают с телефона в зале. */
export type PanelFlag = 'is_published' | 'is_registration_open' | 'is_enter_result_allowed' | 'is_results_allowed'

export const PANEL_FLAGS: readonly PanelFlag[] = [
  'is_published', 'is_registration_open', 'is_enter_result_allowed', 'is_results_allowed',
]

export type PanelAction = 'update_score' | 'clear_results' | 'clear_event' | 'remove_event' | 'mock_data'

export interface ChecklistItem {
  id: 'description' | 'pay' | 'publish'
  done: boolean
  /** не держит чек-лист открытым: оплата нужна не всем */
  optional?: boolean
  /** description: афиша загружена (не картинка по умолчанию) */
  poster?: boolean
  /** pay: взнос в рублях, если оплата настроена */
  price?: number | null
}

export interface PanelOverview {
  id: number
  title: string
  date: string
  gym: string
  stage: SiteStage
  is_expired: boolean
  is_premium: boolean
  is_pay_allowed: boolean
  flags: Record<PanelFlag, boolean>
  participants_count: number
  entered_count: number
  paid_count: number
  checklist: ChecklistItem[]
}

/** Событие удалено: ответ несёт адрес, куда вести дальше. */
export interface PanelRemoved {
  removed: true
  redirect: string
}

export interface PanelApi {
  overview(eventId: number): Promise<PanelOverview>
  setFlags(eventId: number, flags: Partial<Record<PanelFlag, boolean>>): Promise<PanelOverview>
  runAction(eventId: number, action: PanelAction): Promise<PanelOverview | PanelRemoved>
}

export const isRemoved = (value: PanelOverview | PanelRemoved): value is PanelRemoved => 'removed' in value

export function createPanelApi(http: Http): PanelApi {
  const base = (eventId: number) => `/api/events/${eventId}/panel`
  return {
    overview: (eventId) => http.get(`${base(eventId)}/`),
    setFlags: (eventId, flags) => http.post(`${base(eventId)}/flags/`, flags),
    runAction: (eventId, action) => http.post(`${base(eventId)}/actions/`, { action }),
  }
}
