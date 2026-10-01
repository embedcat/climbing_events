// Карточки событий на главной и в кабинете: метка этапа, кнопки по этапу, строка «Вы участвуете», фильтры кабинета.
import type { MyEventCard, Participation, SiteEventCard, SiteStage } from '../api/site'
import type { RememberedParticipant } from './remember'

export interface StageTag {
  label: string
  /** ok — зелёная, live — зелёная с пульсом, warn — оранжевая, пусто — серая */
  kind: '' | 'ok' | 'live' | 'warn'
}

export const STAGE_TAG: Record<SiteStage, StageTag> = {
  reg: { label: 'Регистрация открыта', kind: 'ok' },
  reg_closed: { label: 'Регистрация закрыта', kind: '' },
  live: { label: 'Идёт сейчас', kind: 'live' },
  over: { label: 'Ввод закрыт', kind: '' },
  done: { label: 'Завершено', kind: '' },
  draft: { label: 'Черновик', kind: 'warn' },
}

export const eventUrl = (id: number, tab = ''): string => `/e/${id}/${tab ? `${tab}/` : ''}`
export const panelUrl = (id: number): string => `/e/${id}/admin_actions/`
export const matrixUrl = (id: number): string => `/e/${id}/matrix/`

export interface CardAction {
  label: string
  href: string
  primary: boolean
}

/** Кнопки карточки по этапу: главное действие участника, затем запасное. */
export function cardActions(card: SiteEventCard): CardAction[] {
  const info: CardAction = { label: 'Подробнее', href: eventUrl(card.id), primary: false }
  const results: CardAction | null = card.is_results_allowed
    ? { label: 'Результаты', href: eventUrl(card.id, 'results'), primary: false }
    : null
  switch (card.stage) {
    case 'draft':
      return [{ label: 'Продолжить настройку', href: panelUrl(card.id), primary: true }]
    case 'reg':
      // без регистрации анкета не нужна: участник вносит результат сам
      return card.is_without_registration
        ? [{ ...info, primary: true }]
        : [{ label: 'Зарегистрироваться', href: eventUrl(card.id, 'registration'), primary: true }, info]
    case 'live':
      return [{ label: 'Внести результат', href: eventUrl(card.id, 'enter'), primary: true }, results ?? info]
    case 'reg_closed':
      return [info]
    default:
      return results ? [{ ...results, primary: true }] : [info]
  }
}

export interface ParticipationRow {
  id: number
  title: string
  poster: string | null
  /** «Зайцева Юлия · 4 место из 14 · Спорт» */
  note: string
  go: string
  href: string
}

/** Строка «Вы участвуете»: что про участника известно в этом событии и куда его вести. */
export function participationRow(item: Participation, who: RememberedParticipant | null): ParticipationRow {
  const { event, me } = item
  const parts: string[] = []
  if (who) parts.push(`${who.last_name} ${who.first_name}`.trim())
  if (me) {
    if (me.standing) {
      parts.push(`${me.standing.place} место из ${me.standing.of}`)
      if (me.group) parts.push(me.group)
    } else {
      if (me.set) parts.push(`Сет ${me.set_index + 1}, ${me.set}`)
      if (me.pay_required && !me.paid) parts.push('взнос не оплачен')
    }
  }
  let tab = ''
  let go = 'Открыть'
  if (me?.standing || ((event.stage === 'done' || event.stage === 'over') && event.is_results_allowed)) {
    tab = 'results'
    go = 'Результаты'
  } else if (event.stage === 'live') {
    tab = 'enter'
    go = 'Внести результат'
  }
  return { id: event.id, title: event.title, poster: event.poster, note: parts.join(' · '), go, href: eventUrl(event.id, tab) }
}

export type MineFilter = 'all' | 'live' | 'soon' | 'done'

export const MINE_FILTERS: { value: MineFilter, label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'live', label: 'Идут' },
  { value: 'soon', label: 'Впереди' },
  { value: 'done', label: 'Завершены' },
]

export function matchesFilter(card: MyEventCard, filter: MineFilter): boolean {
  switch (filter) {
    case 'live': return card.stage === 'live' || card.stage === 'over'
    case 'soon': return card.stage === 'reg' || card.stage === 'reg_closed' || card.stage === 'draft'
    case 'done': return card.stage === 'done'
    default: return true
  }
}
