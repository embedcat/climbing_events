import { describe, expect, it } from 'vitest'
import type { ChecklistItem } from '../api/panel'
import { ACTION_INFO, ACTION_ORDER, checklistProgress, checklistRows, FLAG_INFO, hallLinks } from './panel'

const items = (patch: Partial<Record<ChecklistItem['id'], Partial<ChecklistItem>>> = {}): ChecklistItem[] => [
  { id: 'description', done: false, poster: false, ...patch.description },
  { id: 'pay', done: false, optional: true, price: null, ...patch.pay },
  { id: 'publish', done: false, ...patch.publish },
]

describe('чек-лист подготовки', () => {
  it('сначала всё не сделано: две обязательные строки, оплата необязательная', () => {
    expect(checklistProgress(items())).toEqual({ done: 0, total: 2, open: true })
    const rows = checklistRows(items(), 128)
    expect(rows.map((r) => [r.id, r.hint, r.optional])).toEqual([
      ['description', 'замените текст по умолчанию и добавьте афишу', false],
      ['pay', 'выключена, можно пропустить', true],
      ['publish', 'участники пока не видят', false],
    ])
    expect(rows[0].href).toBe('/e/128/admin_description/')
    expect(rows[1].href).toBe('/e/128/pay_settings/')
  })

  it('афиша уже есть: подсказка просит только заменить текст', () => {
    expect(checklistRows(items({ description: { poster: true } }), 1)[0].hint).toBe('замените текст по умолчанию')
  })

  it('всё сделано: карточка закрывается, оплата показывает взнос', () => {
    const done = items({ description: { done: true }, publish: { done: true }, pay: { done: true, price: 1500 } })
    expect(checklistProgress(done)).toEqual({ done: 2, total: 2, open: false })
    expect(checklistRows(done, 1).map((r) => r.hint)).toEqual(['заполнено', '1500 ₽', 'опубликовано'])
  })

  it('оплата не настроена, а остальное сделано: чек-лист закрыт', () => {
    expect(checklistProgress(items({ description: { done: true }, publish: { done: true } })).open).toBe(false)
  })

  it('оплата настроена без цены в данных: просто «настроена»', () => {
    expect(checklistRows(items({ pay: { done: true, price: null } }), 1)[1].hint).toBe('настроена')
  })

  it('публикация ведёт к переключателю на этой же странице', () => {
    expect(checklistRows(items(), 1)[2].href).toBe('#re-switch-is_published')
  })
})

describe('подписи панели', () => {
  it('четыре переключателя дня события', () => {
    expect(FLAG_INFO.map((f) => f.flag)).toEqual([
      'is_published', 'is_registration_open', 'is_enter_result_allowed', 'is_results_allowed',
    ])
  })

  it('у каждого служебного действия есть вопрос подтверждения и опасное помечено', () => {
    expect(ACTION_ORDER).toHaveLength(5)
    for (const action of ACTION_ORDER) expect(ACTION_INFO[action].question).not.toBe('')
    expect(ACTION_INFO.update_score.danger).toBe(false)
    expect(ACTION_INFO.remove_event.danger).toBe(true)
  })

  it('ссылки для зала: мужская и женская таблицы с автообновлением', () => {
    expect(hallLinks(128, 'https://rockevents.ru')).toEqual([
      { gender: 'М', url: 'https://rockevents.ru/e/128/results/?autorefresh&m' },
      { gender: 'Ж', url: 'https://rockevents.ru/e/128/results/?autorefresh&f' },
    ])
  })
})
