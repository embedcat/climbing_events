import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import type { ResultsPayload } from '../../api/results'
import { rememberParticipant } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import { apiError } from '../entry/testing'
import ResultsApp from './ResultsApp.vue'
import { fakeResultsApi, fr, makePayload, makeRow, makeTable, res, standardPayload } from './testing'
import { useResultsFlow } from './useResultsFlow'

const EVENT_ID = 7
const editUrl = (id: number) => `/e/${EVENT_ID}/p/${id}/routes`

async function mountApp(payload: ResultsPayload = standardPayload(), options: { me?: [string, string, string, number] } = {}) {
  const { api, state } = fakeResultsApi(payload)
  const store = memoryStore()
  if (options.me) {
    const [last, first, gender, group] = options.me
    rememberParticipant(store, EVENT_ID, { first_name: first, last_name: last, gender, group_index: group })
  }
  const flow = useResultsFlow({ eventId: EVENT_ID, api, store, isHidden: () => false })
  const wrapper = mount(ResultsApp, { props: { flow, editUrl }, attachTo: document.body })
  await flushPromises()
  return { wrapper, flow, api, state, store }
}

const rows = (wrapper: VueWrapper) => wrapper.findAll('tbody tr[data-id]')
const names = (wrapper: VueWrapper) => rows(wrapper).map((r) => r.find('.n').text())
const press = (wrapper: VueWrapper, selector: string, text: string) =>
  wrapper.findAll(selector).find((b) => b.text().startsWith(text))!

beforeEach(() => { document.body.innerHTML = '' })

describe('таблица', () => {
  it('места, имена и счёт, а участники без результата отдельным блоком без места', async () => {
    const { wrapper } = await mountApp()
    expect(names(wrapper)).toEqual(['Андреев И.', 'Борисов П.', 'Власов Г.'])
    const first = rows(wrapper)[0]
    expect(first.find('.s1').text()).toBe('1')
    expect(first.find('.v').text()).toBe('180,5')
    expect(wrapper.find('tr.sep').text()).toContain('Ещё не ввёл результат')
    const waiting = rows(wrapper)[2]
    expect(waiting.find('.s1').text()).toBe('—')
    expect(waiting.find('.v').text()).toBe('нет результата')
    expect(waiting.classes()).toContain('is-wait')
  })

  it('заголовок блока меняется по числу и полу ожидающих', async () => {
    const { wrapper } = await mountApp()
    await press(wrapper, '.re-seg button', 'Ж').trigger('click')
    expect(wrapper.find('tr.sep').text()).toContain('Ещё не ввели результат')
  })

  it('ячейки FL и RP и номера трасс в шапке', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.findAll('thead th.c').map((th) => th.text())).toEqual(['1', '2', '3', '4', '5'])
    const cells = rows(wrapper)[0].findAll('td.c')
    expect(cells.map((c) => c.text())).toEqual(['RP', 'FL', 'RP', '', ''])
    expect(cells[0].classes()).toContain('k-rp')
    expect(cells[1].classes()).toContain('k-fl')
  })

  it('нижняя строка: очки за RP по трассам', async () => {
    const { wrapper } = await mountApp()
    const foot = wrapper.find('tfoot')
    expect(foot.find('.s2').text()).toBe('Очков за RP')
    expect(foot.findAll('td.c').map((c) => c.text())).toEqual(['50', '80', '50', '80', '—'])
  })

  it('без очков за трассы нижней строки нет', async () => {
    const payload = standardPayload()
    payload.tables[0].route_points = null
    const { wrapper } = await mountApp(payload)
    expect(wrapper.find('tfoot').exists()).toBe(false)
  })

  it('пустая группа', async () => {
    const { wrapper } = await mountApp()
    await press(wrapper, '.re-seg button', 'Ж').trigger('click')
    await press(wrapper, '.re-chips button', 'Спорт').trigger('click')
    expect(rows(wrapper)).toHaveLength(0)
    expect(wrapper.text()).toContain('В этой группе пока нет участников')
  })

  it('события с одной группой без чипов', async () => {
    const payload = makePayload([
      makeTable('MALE', 0, '', [makeRow('Андреев', 'Иван', 1, res(2, 1))]), makeTable('FEMALE', 0, '', []),
    ], { groups: [], routes_num: 2 })
    const { wrapper } = await mountApp(payload)
    expect(wrapper.find('.re-chips').exists()).toBe(false)
    expect(names(wrapper)).toEqual(['Андреев И.'])
  })

  it('прохождения скрыты настройкой события: остаются место, имя и счёт', async () => {
    const payload = standardPayload({ is_view_full_results: false })
    for (const t of payload.tables) for (const r of [...t.ranked, ...t.waiting]) { r.results = []; r.counted = [] }
    payload.tables[0].route_points = null
    const { wrapper } = await mountApp(payload)
    expect(wrapper.findAll('thead th.c')).toHaveLength(0)
    expect(rows(wrapper)[0].find('.s1').text()).toBe('1')
    expect(wrapper.find('tfoot').exists()).toBe(false)
    expect(wrapper.find('.re-tbl-wrap').text()).not.toContain('RP')
  })

  it('трассы вне зачёта бледнеют, в легенде об этом сказано', async () => {
    const payload = standardPayload({ best_routes_num: 2 })
    payload.tables[0].ranked[0].counted = [true, true, false, false, false]
    const { wrapper } = await mountApp(payload)
    expect(rows(wrapper)[0].findAll('td.c')[2].classes()).toContain('nc')
    expect(wrapper.find('.re-legend').text()).toContain('не в зачёте')
  })

  it('категория и цвет трассы в шапке, если события их показывают', async () => {
    const routes = [1, 2, 3, 4, 5].map((n) => ({ number: n, grade: '6A', color: '#ff0000' }))
    const { wrapper } = await mountApp(standardPayload({ routes }))
    expect(wrapper.find('thead th.c').text()).toContain('6A')
    expect(wrapper.find('.re-rcolor').exists()).toBe(true)
  })
})

describe('французская система', () => {
  const payload = () => makePayload([
    makeTable('MALE', 0, '', [
      makeRow('Андреев', 'Иван', 1, fr([2, 1], [0, 3], [1, 1]), { score_view: '2T3 3z5' }),
      makeRow('Борисов', 'Пётр', 2, fr([0, 0], [0, 4], [1, 1]), { score_view: '1T1 2z5' }),
    ]),
    makeTable('FEMALE', 0, '', []),
  ], { score_type: 'FR', routes_num: 3, groups: [] })

  it('в ячейках попытки топа и зоны, счёт — готовая строка, снизу число топов', async () => {
    const { wrapper } = await mountApp(payload())
    const cells = rows(wrapper)[0].findAll('td.c')
    expect(cells.map((c) => c.text())).toEqual(['2/1', '–/3', '1/1'])
    expect(cells[1].classes()).toContain('k-zone')
    expect(rows(wrapper)[0].find('.v').text()).toBe('2T3 3z5')
    expect(wrapper.find('tfoot .s2').text()).toBe('Топов')
    expect(wrapper.findAll('tfoot td.c').map((c) => c.text())).toEqual(['1', '0', '2'])
    expect(wrapper.find('.re-legend').text()).toContain('попытка топа / зоны')
  })

  it('карточка участника: топы и зоны с числом попыток', async () => {
    const { wrapper } = await mountApp(payload())
    await rows(wrapper)[0].trigger('click')
    const sheet = wrapper.get('[role="dialog"]')
    expect(sheet.text()).toContain('2 топа за 3 попытки, 3 зоны за 5 попыток')
    expect(sheet.findAll('.re-rgrid span')[1].text()).toContain('Т– З3')
  })
})

describe('строка «идёт»', () => {
  it('идущее событие: точка, время обновления и кнопка', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.find('.re-live').text()).toContain('Идёт · обновлено только что')
    expect(wrapper.find('.re-refresh').exists()).toBe(true)
  })

  it('кнопка «Обновить» запрашивает свежие данные', async () => {
    const { wrapper, api } = await mountApp()
    await wrapper.get('.re-refresh').trigger('click')
    await flushPromises()
    expect(api.getResults).toHaveBeenCalledTimes(2)
  })

  it('завершённое событие: итоговые результаты', async () => {
    const { wrapper } = await mountApp(standardPayload({ is_live: false, is_expired: true }))
    expect(wrapper.find('.re-live').text()).toBe('Итоговые результаты. Соревнование завершено.')
    expect(wrapper.find('.re-refresh').exists()).toBe(false)
  })

  it('ввод закрыт, но событие не завершено', async () => {
    const { wrapper } = await mountApp(standardPayload({ is_live: false, is_expired: false }))
    expect(wrapper.find('.re-live').text()).toBe('Ввод результатов закрыт.')
  })

  it('связь пропала: таблица остаётся, в строке про данные от такого-то времени', async () => {
    const { wrapper, api } = await mountApp()
    api.getResults.mockRejectedValueOnce(apiError('network', 0))
    await wrapper.get('.re-refresh').trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-live').text()).toMatch(/Нет связи · данные от \d\d:\d\d/)
    expect(rows(wrapper)).toHaveLength(3)
  })
})

describe('выбор таблицы', () => {
  it('пол и группа переключают таблицу, на чипах число участников', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.findAll('.re-chips button').map((b) => b.text().replace(/\s+/g, ' '))).toEqual(['Новички3', 'Спорт1'])
    await press(wrapper, '.re-chips button', 'Спорт').trigger('click')
    expect(names(wrapper)).toEqual(['Гаврилов О.'])
    await press(wrapper, '.re-seg button', 'Ж').trigger('click')
    expect(rows(wrapper)).toHaveLength(0)
    await press(wrapper, '.re-chips button', 'Новички').trigger('click')
    expect(names(wrapper)).toEqual(['Зайцева Ю.', 'Титова П.', 'Уварова А.'])
  })
})

describe('карточка участника', () => {
  it('открывается по строке и показывает данные, которые видны всем', async () => {
    const { wrapper } = await mountApp()
    await rows(wrapper)[0].trigger('click')
    const sheet = wrapper.get('[role="dialog"]')
    expect(sheet.find('h3').text()).toBe('Андреев Иван')
    expect(sheet.find('.re-sh-place').text()).toContain('1')
    expect(sheet.find('.re-sh-place').text()).toContain('место из 2 · Новички, мужчины · 180,5')
    expect(sheet.find('.re-facts').text()).toBe('1995 г. р. · б/р · Москва · «Скала» · сет 1, 10:00')
    expect(sheet.findAll('.re-rgrid span').map((s) => s.classes().find((c) => c.startsWith('k-')))).toEqual(
      ['k-rp', 'k-fl', 'k-rp', undefined, undefined])
    expect(sheet.text()).toContain('Flash 1 · redpoint 2')
  })

  it('без года рождения и с разрядом', async () => {
    const { wrapper } = await mountApp()
    await press(wrapper, '.re-seg button', 'Ж').trigger('click')
    await rows(wrapper)[0].trigger('click')
    expect(wrapper.get('.re-facts').text()).toBe('КМС · Москва')
  })

  it('участник без результата: сообщение вместо сетки', async () => {
    const { wrapper } = await mountApp()
    await rows(wrapper)[2].trigger('click')
    const sheet = wrapper.get('[role="dialog"]')
    expect(sheet.text()).toContain('Результат ещё не введён')
    expect(sheet.find('.re-rgrid').exists()).toBe(false)
  })

  it('при N лучших трассах говорит, какие считаются', async () => {
    const payload = standardPayload({ best_routes_num: 10 })
    const { wrapper } = await mountApp(payload)
    await rows(wrapper)[0].trigger('click')
    expect(wrapper.get('[role="dialog"]').text()).toContain('В зачёт идут 10 лучших трасс')
  })

  it('закрывается кнопкой, подложкой и Escape', async () => {
    const { wrapper } = await mountApp()
    for (const close of [
      () => wrapper.get('.re-sheet-actions .re-btn:not(.is-primary)').trigger('click'),
      () => wrapper.get('.re-sheet-bg').trigger('click'),
      () => { document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) },
    ]) {
      await rows(wrapper)[0].trigger('click')
      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
      await close()
      await flushPromises()
      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    }
  })

  it('«Это я, запомнить» запоминает и выделяет строку', async () => {
    const { wrapper, store } = await mountApp()
    await rows(wrapper)[1].trigger('click')
    await wrapper.get('.re-sheet-actions .re-btn.is-primary').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(rows(wrapper)[1].classes()).toContain('is-me')
    expect(store.data.size).toBe(1)
    expect(wrapper.get('.re-toast').text()).toContain('Запомнили')

    await rows(wrapper)[1].trigger('click')
    expect(wrapper.get('.re-is-me').text()).toContain('Это вы')
    expect(wrapper.find('.re-sheet-actions .re-btn.is-primary').exists()).toBe(false)
  })

  it('организатор видит ссылку на правку результатов', async () => {
    const { wrapper } = await mountApp(standardPayload({ can_edit: true }))
    await rows(wrapper)[0].trigger('click')
    const link = wrapper.get('a.re-edit-link')
    expect(link.attributes('href')).toBe(`/e/${EVENT_ID}/p/${rows(wrapper)[0].attributes('data-id')}/routes`)
  })

  it('обычный зритель ссылки на правку не видит', async () => {
    const { wrapper } = await mountApp()
    await rows(wrapper)[0].trigger('click')
    expect(wrapper.find('a[href$="/routes"]').exists()).toBe(false)
  })
})

describe('плашка «Вы»', () => {
  it('строка в другой таблице: плашка с местом и переход по нажатию', async () => {
    const { wrapper } = await mountApp(standardPayload(), { me: ['Зайцева', 'Юлия', 'FEMALE', 0] })
    // запомненный открывает свою группу, поэтому уходим из неё
    await press(wrapper, '.re-seg button', 'М').trigger('click')
    const bar = wrapper.get('.re-me-bar')
    expect(bar.text()).toContain('Вы: 1 место из 1')
    expect(bar.text()).toContain('Новички, женщины. Открыть')
    await bar.trigger('click')
    await flushPromises()
    expect(names(wrapper)).toEqual(['Зайцева Ю.', 'Титова П.', 'Уварова А.'])
    expect(rows(wrapper)[0].classes()).toContain('is-me')
  })

  it('своя строка на виду: плашки нет', async () => {
    const { wrapper } = await mountApp(standardPayload(), { me: ['Зайцева', 'Юлия', 'FEMALE', 0] })
    expect(wrapper.find('.re-me-bar').exists()).toBe(false)
    // зато группа помечена на чипе
    expect(wrapper.findAll('.re-chips button')[0].find('.re-medot').exists()).toBe(true)
  })

  it('своя строка уехала за край: плашка появляется', async () => {
    const { wrapper, flow } = await mountApp(standardPayload(), { me: ['Зайцева', 'Юлия', 'FEMALE', 0] })
    flow.setMeRowVisible(false)
    await flushPromises()
    expect(wrapper.find('.re-me-bar').text()).toContain('Показать мою строку')
  })

  it('свою группу помечает точка на чипе', async () => {
    const { wrapper } = await mountApp(standardPayload(), { me: ['Гаврилов', 'Олег', 'MALE', 1] })
    expect(wrapper.findAll('.re-chips button')[1].find('.re-medot').exists()).toBe(true)
    expect(wrapper.findAll('.re-chips button')[0].find('.re-medot').exists()).toBe(false)
  })

  it('участник ещё не ввёл результат', async () => {
    const { wrapper, flow } = await mountApp(standardPayload(), { me: ['Титова', 'Полина', 'FEMALE', 0] })
    flow.setMeRowVisible(false)
    await flushPromises()
    const bar = wrapper.get('.re-me-bar')
    expect(bar.text()).toContain('Вы ещё не ввели результат')
    expect(bar.find('.re-mb-pl').text()).toBe('?')
  })
})

describe('состояния экрана', () => {
  it('просмотр закрыт', async () => {
    const { api } = fakeResultsApi(standardPayload())
    api.getResults.mockRejectedValueOnce(apiError('results_closed', 403))
    const flow = useResultsFlow({ eventId: EVENT_ID, api, store: memoryStore(), isHidden: () => false })
    const wrapper = mount(ResultsApp, { props: { flow, editUrl }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('Просмотр результатов закрыт')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('ошибка загрузки с кнопкой «Повторить»', async () => {
    const { api } = fakeResultsApi(standardPayload())
    api.getResults.mockRejectedValueOnce(apiError('network', 0, 'Нет связи с сервером.'))
    const flow = useResultsFlow({ eventId: EVENT_ID, api, store: memoryStore(), isHidden: () => false })
    const wrapper = mount(ResultsApp, { props: { flow, editUrl }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('Повторить')
    await wrapper.get('[role="alert"] .re-linkbtn').trigger('click')
    await flushPromises()
    expect(wrapper.find('table').exists()).toBe(true)
  })
})
