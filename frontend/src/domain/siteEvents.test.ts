import { describe, expect, it } from 'vitest'
import type { MyEventCard, Participation, SiteEventCard } from '../api/site'
import { cardActions, eventUrl, matchesFilter, MINE_FILTERS, participationRow, STAGE_TAG } from './siteEvents'

const card = (patch: Partial<SiteEventCard> = {}): SiteEventCard => ({
  id: 128, title: 'Осенний фестиваль', date: '4 октября 2026 г.', gym: 'Скалодром', short_description: 'Кратко',
  poster: '/media/p.png', stage: 'reg', is_results_allowed: true, is_without_registration: false, mine: false, ...patch,
})
const labels = (c: SiteEventCard) => cardActions(c).map((a) => a.label)

describe('кнопки карточки по этапу', () => {
  it('регистрация открыта: записаться и подробнее', () => {
    expect(labels(card())).toEqual(['Зарегистрироваться', 'Подробнее'])
    expect(cardActions(card())[0]).toEqual({ label: 'Зарегистрироваться', href: '/e/128/registration/', primary: true })
  })

  it('без регистрации анкета не нужна: только «Подробнее»', () => {
    expect(cardActions(card({ is_without_registration: true }))).toEqual([
      { label: 'Подробнее', href: '/e/128/', primary: true },
    ])
  })

  it('идёт ввод: внести результат и результаты; без открытых результатов — подробнее', () => {
    expect(labels(card({ stage: 'live' }))).toEqual(['Внести результат', 'Результаты'])
    expect(labels(card({ stage: 'live', is_results_allowed: false }))).toEqual(['Внести результат', 'Подробнее'])
  })

  it('регистрация закрыта: только «Подробнее»', () => {
    expect(labels(card({ stage: 'reg_closed' }))).toEqual(['Подробнее'])
  })

  it('ввод закрыт и завершено: результаты главной кнопкой, пока они открыты', () => {
    for (const stage of ['over', 'done'] as const) {
      expect(cardActions(card({ stage }))).toEqual([{ label: 'Результаты', href: '/e/128/results/', primary: true }])
      expect(labels(card({ stage, is_results_allowed: false }))).toEqual(['Подробнее'])
    }
  })

  it('черновик: продолжить настройку в панели', () => {
    expect(cardActions(card({ stage: 'draft' }))).toEqual([
      { label: 'Продолжить настройку', href: '/e/128/admin_actions/', primary: true },
    ])
  })

  it('у каждого этапа есть метка', () => {
    expect(STAGE_TAG.live).toEqual({ label: 'Идёт сейчас', kind: 'live' })
    expect(STAGE_TAG.draft.kind).toBe('warn')
    expect(eventUrl(5)).toBe('/e/5/')
    expect(eventUrl(5, 'enter')).toBe('/e/5/enter/')
  })
})

describe('строка «Вы участвуете»', () => {
  const who = { id: 7, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 }
  const me = (patch = {}) => ({ paid: false, pay_required: true, standing: null, group: 'Спорт', set: '16:00', set_index: 2, ...patch })
  const item = (eventPatch: Partial<SiteEventCard>, mePatch: object | null): Participation =>
    ({ event: card(eventPatch), me: mePatch === null ? null : me(mePatch) })

  it('до результатов: сет и неоплаченный взнос', () => {
    const row = participationRow(item({}, {}), who)
    expect(row.note).toBe('Зайцева Юлия · Сет 3, 16:00 · взнос не оплачен')
    expect(row.go).toBe('Открыть')
    expect(row.href).toBe('/e/128/')
  })

  it('оплаченный взнос и событие без оплаты ничего не пишут про оплату', () => {
    expect(participationRow(item({}, { paid: true }), who).note).toBe('Зайцева Юлия · Сет 3, 16:00')
    expect(participationRow(item({}, { pay_required: false }), who).note).toBe('Зайцева Юлия · Сет 3, 16:00')
  })

  it('есть место: показываем его с группой и ведём в результаты', () => {
    const row = participationRow(item({ stage: 'done' }, { standing: { place: 4, of: 14 } }), who)
    expect(row.note).toBe('Зайцева Юлия · 4 место из 14 · Спорт')
    expect(row.go).toBe('Результаты')
    expect(row.href).toBe('/e/128/results/')
  })

  it('идёт ввод: ведём сразу во ввод', () => {
    const row = participationRow(item({ stage: 'live' }, {}), who)
    expect(row.go).toBe('Внести результат')
    expect(row.href).toBe('/e/128/enter/')
  })

  it('событие завершено, результаты скрыты: открываем страницу события', () => {
    expect(participationRow(item({ stage: 'done', is_results_allowed: false }, {}), who).href).toBe('/e/128/')
  })

  it('сервер про участника не ответил: только имя из браузера', () => {
    expect(participationRow(item({}, null), who).note).toBe('Зайцева Юлия')
    expect(participationRow(item({}, null), null).note).toBe('')
  })
})

describe('фильтры кабинета', () => {
  const mine = (stage: MyEventCard['stage']): MyEventCard => ({
    ...card({ stage }), participants_count: 0, entered_count: 0, paid_count: 0, is_pay_allowed: false, is_premium: false, owner: null,
  })

  it('идут: ввод открыт или только что закрыт; впереди: регистрация и черновики; завершены', () => {
    const by = (filter: (typeof MINE_FILTERS)[number]['value']) =>
      (['reg', 'reg_closed', 'live', 'over', 'done', 'draft'] as const).filter((s) => matchesFilter(mine(s), filter))
    expect(by('all')).toHaveLength(6)
    expect(by('live')).toEqual(['live', 'over'])
    expect(by('soon')).toEqual(['reg', 'reg_closed', 'draft'])
    expect(by('done')).toEqual(['done'])
  })
})
