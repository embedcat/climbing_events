import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { EventPage } from '../../api/event'
import { rememberKey } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import { standardPayload } from '../results/testing'
import EventApp from './EventApp.vue'
import { apiError, clock, EVENT_ID, makeApp, makeMe, makePage, makePerson, makeRegistered, standardPeople, type AppOptions } from './testing'

const wrappers: VueWrapper[] = []

async function mountApp(options: AppOptions & { me?: boolean } = {}) {
  const store = options.store ?? (options.me
    ? memoryStore({ [rememberKey(EVENT_ID)]: JSON.stringify({ id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1, set_index: 2 }) })
    : memoryStore())
  const ctx = makeApp({ ...options, store })
  const wrapper = mount(EventApp, { props: { app: ctx.app }, attachTo: document.body })
  wrappers.push(wrapper)
  await flushPromises()
  return { wrapper, ...ctx }
}

const byText = (wrapper: VueWrapper, selector: string, text: string) =>
  wrapper.findAll(selector).find((el) => el.text().includes(text))
const actionText = (wrapper: VueWrapper) => (wrapper.find('.re-action').exists() ? wrapper.get('.re-action').text() : '')
const page = (overrides: Partial<EventPage> = {}) => makePage(overrides)
const pay = { is_allowed: true, type: 'yoomoney' as const, price: 1500 }

beforeEach(() => { clock.now = 1_000_000; document.body.innerHTML = '' })
afterEach(() => { wrappers.splice(0).forEach((w) => w.unmount()) })

describe('шапка и вкладки', () => {
  it('название, дата со скалодромом и четыре вкладки с адресами', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.get('.re-title').text()).toBe('Осенний фестиваль')
    expect(wrapper.get('.re-date').text()).toBe('4 октября 2026 г. · Скалодром на Лесной')
    const tabs = wrapper.findAll('.re-tabs a')
    expect(tabs.map((t) => t.text())).toEqual(['Инфо', 'Ввод', 'Участники', 'Результаты'])
    expect(tabs.map((t) => t.attributes('href'))).toEqual(['/e/7/', '/e/7/enter/', '/e/7/participants/', '/e/7/results/'])
    expect(tabs[0].attributes('aria-current')).toBe('page')
  })

  it('переход по вкладке без перезагрузки: меняется адрес, вкладка и содержимое', async () => {
    const { wrapper } = await mountApp()
    await wrapper.findAll('.re-tabs a')[2].trigger('click')
    await flushPromises()
    expect(window.location.pathname).toBe('/e/7/participants/')
    expect(wrapper.findAll('.re-tabs a')[2].attributes('aria-current')).toBe('page')
    expect(wrapper.findAll('.re-tabs a')[0].attributes('aria-current')).toBeUndefined()
    expect(wrapper.text()).toContain('4 участника')
  })

  it('ссылка управления только у организатора', async () => {
    expect((await mountApp()).wrapper.find('.re-manage').exists()).toBe(false)
    const { wrapper } = await mountApp({ page: page({ can_manage: true }) })
    expect(wrapper.get('.re-manage').attributes('href')).toBe('/e/7/admin_actions/')
  })

  it('событие не загрузилось: сообщение и «Повторить»', async () => {
    const ctx = makeApp()
    ctx.api.getPage.mockRejectedValueOnce(apiError('network', 0))
    const wrapper = mount(EventApp, { props: { app: ctx.app }, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('Нет связи')
    await wrapper.get('[role=alert] button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role=alert]').exists()).toBe(false)
    expect(wrapper.get('.re-title').text()).toBe('Осенний фестиваль')
  })
})

describe('«Инфо»: этап события', () => {
  it('регистрация открыта: срок, участники, места; сеты с полосой; кнопка', async () => {
    const { wrapper } = await mountApp()
    const status = wrapper.get('.re-status')
    expect(status.text()).toContain('Регистрация открыта')
    expect(status.text()).toContain('До 3 октября, 23:59 · 42 участника · свободно 6 мест')
    const sets = wrapper.findAll('.re-sets li').map((li) => li.text())
    expect(sets[0]).toContain('Сет 1')
    expect(sets[0]).toContain('свободно 2')
    expect(sets[1]).toContain('мест нет')
    expect(wrapper.find('.re-sets li.is-full').exists()).toBe(true)
    expect(wrapper.text()).toContain('Сет выбираете при регистрации')
    const button = wrapper.get('.re-action a.re-btn')
    expect(button.text()).toBe('Зарегистрироваться')
    expect(button.attributes('href')).toBe('/e/7/registration/')
    expect(actionText(wrapper)).toContain('свободно 6 мест')
  })

  it('описание организатора выводится как есть', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.get('.re-prose h3').text()).toBe('Формат')
  })

  it('регистрации не нужно: объясняем, где указать имя и сет, и кнопки регистрации нет', async () => {
    const { wrapper } = await mountApp({ page: page({ is_without_registration: true, registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.get('.re-status').text()).toContain('Регистрация не нужна')
    expect(wrapper.text()).toContain('Сет укажете вместе с результатами')
    expect(actionText(wrapper)).toBe('')
  })

  it('регистрация закрыта: написать организатору', async () => {
    const { wrapper } = await mountApp({ page: page({ stage: 'reg_closed', registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.get('.re-status').text()).toContain('Регистрация закрыта')
    expect(wrapper.get('.re-status').text()).toContain('напишите организатору')
    expect(wrapper.find('.re-action').exists()).toBe(false)
  })

  it('идёт: сколько внесли, где взять PIN; внизу «Результаты» и «Внести результат»', async () => {
    const { wrapper } = await mountApp({ page: page({ stage: 'live', entered_count: 12 }) })
    expect(wrapper.get('.re-status').text()).toContain('Идёт')
    expect(wrapper.get('.re-status').text()).toContain('внесли 12 из 42')
    expect(wrapper.get('.re-status').text()).toContain('PIN для ввода напечатан')
    expect(wrapper.findAll('.re-action a').map((a) => a.text())).toEqual(['Результаты', 'Внести результат'])
  })

  it('идёт, а результаты скрыты: только «Внести результат»', async () => {
    const { wrapper } = await mountApp({ page: page({ stage: 'live', is_results_allowed: false }) })
    expect(wrapper.findAll('.re-action a').map((a) => a.text())).toEqual(['Внести результат'])
  })

  it('идёт при открытой регистрации: ссылка «Зарегистрироваться» в карточке этапа', async () => {
    const { wrapper } = await mountApp({ page: page({ stage: 'live' }) })
    expect(wrapper.get('.re-status a').attributes('href')).toBe('/e/7/registration/')
  })

  it('ввод закрыт: к организатору; внизу «Результаты»', async () => {
    const { wrapper } = await mountApp({ page: page({ stage: 'over', entered_count: 30, registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.get('.re-status').text()).toContain('Ввод результатов закрыт')
    expect(wrapper.get('.re-status').text()).toContain('Внесли результат 30 из 42')
    expect(wrapper.get('.re-action a').text()).toBe('Результаты')
  })

  it('завершено: итоговые результаты и призёры вместо сетов', async () => {
    const podium = [{
      group_index: 1, group: 'Спорт',
      male: [{ id: 4, last_name: 'Соколов', first_name: 'Дмитрий', place: 1 }],
      female: [{ id: 1, last_name: 'Зайцева', first_name: 'Юлия', place: 1 }, { id: 3, last_name: 'Орлова', first_name: 'Анна', place: 2 }],
    }]
    const { wrapper } = await mountApp({ page: page({ stage: 'done', podium, registration: { ...makePage().registration, is_open: false } }), me: true })
    expect(wrapper.get('.re-status').text()).toContain('Соревнование завершено')
    expect(wrapper.find('.re-sets').exists()).toBe(false)
    expect(wrapper.get('.re-pod').text()).toContain('Соколов Д.')
    expect(wrapper.findAll('.re-pod li').map((li) => li.text())).toEqual(['1Соколов Д.', '1Зайцева Ю.', '2Орлова А.'])
    expect(wrapper.get('.re-pod li.is-me').text()).toContain('Зайцева')
    expect(wrapper.get('.re-action a').text()).toBe('Итоговые результаты')
  })

  it('завершено, а результаты скрыты: ни призёров, ни кнопки', async () => {
    const { wrapper } = await mountApp({ page: page({ stage: 'done', is_results_allowed: false }) })
    expect(wrapper.text()).toContain('появятся, когда организатор их откроет')
    expect(wrapper.find('.re-pod').exists()).toBe(false)
    expect(wrapper.find('.re-action').exists()).toBe(false)
  })

  it('факты: взнос только при онлайн-оплате, группы только если их несколько', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.get('.re-fact-list').text()).not.toContain('Взнос')
    expect(wrapper.get('.re-fact-list').text()).toContain('Новички, Спорт')
    const paid = await mountApp({ page: page({ pay, groups: [] }) })
    expect(paid.wrapper.get('.re-fact-list').text()).toContain('Взнос')
    expect(paid.wrapper.get('.re-fact-list').text().replace(/\s/g, ' ')).toContain('1 500 ₽')
    expect(paid.wrapper.get('.re-fact-list').text()).not.toContain('Группы')
  })

  it('афиша открывается на весь экран и закрывается', async () => {
    const { wrapper } = await mountApp()
    await wrapper.get('.re-poster').trigger('click')
    expect(wrapper.find('.re-lightbox img').attributes('src')).toBe('/media/posters/a.png')
    await wrapper.get('.re-lightbox .re-btn').trigger('click')
    expect(wrapper.find('.re-lightbox').exists()).toBe(false)
  })
})

describe('«Инфо»: карточка «Вы»', () => {
  it('зарегистрирован: вместо приглашения карточка с группой и сетом, кнопки регистрации нет', async () => {
    const { wrapper } = await mountApp({ me: true })
    const card = wrapper.get('.re-me-card')
    expect(card.text()).toContain('Вы зарегистрированы')
    expect(card.text()).toContain('Зайцева Юлия')
    expect(card.text()).toContain('Спорт · Ж · сет 3, 16:00')
    expect(card.text()).toContain('Результаты вносите по PIN')
    expect(wrapper.find('.re-status').exists()).toBe(false)
    expect(wrapper.find('.re-action').exists()).toBe(false)
  })

  it('оплата: статус в карточке и «Оплатить» внизу, у оплатившего нет ни того, ни другого', async () => {
    const { wrapper, api } = await mountApp({ me: true, page: page({ pay }) })
    expect(wrapper.get('.re-me-card .re-pill').text()).toBe('не оплачен')
    expect(wrapper.get('.re-me-card').text().replace(/\s/g, ' ')).toContain('Взнос 1 500 ₽')
    const button = wrapper.get('.re-action a.re-btn')
    expect(button.text()).toBe('Оплатить')
    expect(button.attributes('href')).toBe('/e/7/pay/?p=1')

    api.getMe.mockResolvedValue(makeMe({ paid: true }))
    await wrapper.findAll('.re-tabs a')[2].trigger('click')
    await flushPromises()
    await wrapper.findAll('.re-tabs a')[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-me-card .re-pill').text()).toBe('оплачен')
    expect(wrapper.find('.re-action').exists()).toBe(false)
  })

  it('СБП: предупреждаем, что оплату отмечают вручную', async () => {
    const { wrapper } = await mountApp({ me: true, page: page({ pay: { ...pay, type: 'sbp' } }) })
    expect(wrapper.get('.re-me-card').text()).toContain('Оплату по СБП организатор отмечает вручную')
  })

  it('идёт, результата ещё нет: где взять PIN', async () => {
    const { wrapper } = await mountApp({ me: true, page: page({ stage: 'live' }) })
    expect(wrapper.get('.re-me-card').text()).toContain('Вы участвуете')
    expect(wrapper.get('.re-me-card').text()).toContain('Вы ещё не внесли результат')
  })

  it('внёс результат: место в группе', async () => {
    const { wrapper, api } = await mountApp({ page: page({ stage: 'live' }), me: true })
    api.getMe.mockResolvedValue(makeMe({ standing: { place: 3, of: 14 }, participant: { ...makeMe().participant, is_entered_result: true } }))
    await wrapper.findAll('.re-tabs a')[2].trigger('click')
    await flushPromises()
    await wrapper.findAll('.re-tabs a')[0].trigger('click')
    await flushPromises()
    const card = wrapper.get('.re-me-card')
    expect(card.get('.re-mc-place b').text()).toBe('3')
    expect(card.get('.re-mc-place').text()).toContain('место из 14')
    expect(card.text()).toContain('Спорт, женщины')
    expect(card.text()).toContain('Места меняются')
  })

  it('внёс результат, а результаты скрыты: места нет', async () => {
    const { wrapper } = await mountApp({
      page: page({ stage: 'over', is_results_allowed: false }), me: true,
    })
    expect(wrapper.get('.re-me-card').text()).toContain('Вы не внесли результат')
    const ctx = await mountApp({ page: page({ stage: 'over', is_results_allowed: false }), me: true })
    ctx.api.getMe.mockResolvedValue(makeMe({ participant: { ...makeMe().participant, is_entered_result: true } }))
    await ctx.wrapper.findAll('.re-tabs a')[2].trigger('click')
    await flushPromises()
    await ctx.wrapper.findAll('.re-tabs a')[0].trigger('click')
    await flushPromises()
    expect(ctx.wrapper.get('.re-me-card').text()).toContain('Результат внесён.')
    expect(ctx.wrapper.get('.re-me-card').text()).toContain('Место появится, когда организатор откроет результаты')
    expect(ctx.wrapper.find('.re-mc-place').exists()).toBe(false)
  })

  it('«Не вы?» убирает карточку и возвращает приглашение', async () => {
    const { wrapper } = await mountApp({ me: true })
    await wrapper.get('.re-me-card .re-linkbtn').trigger('click')
    expect(wrapper.find('.re-me-card').exists()).toBe(false)
    expect(wrapper.get('.re-status').text()).toContain('Регистрация открыта')
    expect(wrapper.get('.re-action a').text()).toBe('Зарегистрироваться')
  })
})

describe('«Ввод», пока он закрыт', () => {
  const open = async (options: AppOptions & { me?: boolean }) => {
    const ctx = await mountApp(options)
    await ctx.wrapper.findAll('.re-tabs a')[1].trigger('click')
    await flushPromises()
    return ctx
  }

  it('до дня события: когда откроется и что делать', async () => {
    const { wrapper } = await open({})
    expect(wrapper.get('.re-closed h2').text()).toBe('Ввод откроется в день соревнований')
    expect(wrapper.get('.re-closed').text()).toContain('4 октября организатор откроет ввод')
    expect(wrapper.get('.re-closed').text()).toContain('введите PIN с карточки участника')
    expect(wrapper.get('.re-action a').text()).toBe('Зарегистрироваться')
  })

  it('без регистрации: имя, группу и сет укажут вместе с результатами', async () => {
    const { wrapper } = await open({ page: page({ is_without_registration: true, registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.get('.re-closed').text()).toContain('имя, группу и сет укажете вместе с результатами')
    expect(wrapper.get('.re-closed').text()).toContain('Регистрироваться заранее не нужно')
  })

  it('кто-то уже внёс результат: ввод закрыт, исправит организатор', async () => {
    const { wrapper } = await open({ page: page({ stage: 'over', registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.get('.re-closed h2').text()).toBe('Ввод результатов закрыт')
    expect(wrapper.get('.re-closed').text()).toContain('подойдите к организатору')
    expect(wrapper.get('.re-action a').text()).toBe('Результаты')
  })

  it('событие завершено', async () => {
    const { wrapper } = await open({ page: page({ stage: 'done', registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.get('.re-closed h2').text()).toBe('Соревнование завершено')
    expect(wrapper.get('.re-closed').text()).toContain('Исправить результат может только организатор')
    expect(wrapper.get('.re-action a').text()).toBe('Итоговые результаты')
  })

  it('когда ввод открыт, это форма с PIN', async () => {
    const { wrapper, entry } = await open({ page: page({ stage: 'live' }) })
    expect(entry.getConfig).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Введите PIN с вашей карточки участника')
    expect(wrapper.find('input.re-pin').exists()).toBe(true)
  })

  it('идёт, результат отправлен: после отправки браузер помнит участника и «Инфо» показывает карточку', async () => {
    const { wrapper, entry, api } = await open({ page: page({ stage: 'live' }) })
    entry.identify.mockResolvedValueOnce({
      participant: makeMe().participant,
      results: Array.from({ length: 10 }, () => ({ top: 0, zone: 0 })),
    })
    await wrapper.get('input.re-pin').setValue('8335')
    await flushPromises()
    expect(wrapper.get('.re-who-name').text()).toBe('Зайцева Юлия')
    await wrapper.get('.re-tile').trigger('click')
    await wrapper.get('.re-action .re-btn.is-primary').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Результаты отправлены')
    expect(api.getMe).toHaveBeenCalled()
    await wrapper.findAll('.re-tabs a')[0].trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-me-card').text()).toContain('Зайцева Юлия')
  })

  it('переход на другую вкладку и обратно не сбрасывает введённый PIN и отметки', async () => {
    const { wrapper } = await open({ page: page({ stage: 'live' }) })
    await wrapper.get('input.re-pin').setValue('8335')
    await flushPromises()
    await wrapper.get('.re-tile').trigger('click')
    await wrapper.findAll('.re-tabs a')[2].trigger('click')
    await flushPromises()
    await wrapper.findAll('.re-tabs a')[1].trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-who-name').text()).toBe('Зайцева Юлия')
    expect(wrapper.get('.re-tile').classes()).toContain('is-fl')
  })
})

describe('«Результаты»', () => {
  const open = async (options: AppOptions & { me?: boolean }) => {
    const ctx = await mountApp(options)
    await ctx.wrapper.findAll('.re-tabs a')[3].trigger('click')
    await flushPromises()
    return ctx
  }

  it('скрыты организатором: так и говорим, запросов за таблицей нет', async () => {
    const { wrapper, results } = await open({ page: page({ stage: 'live', is_results_allowed: false }) })
    expect(wrapper.get('.re-closed h2').text()).toBe('Результаты пока скрыты')
    expect(results.api.getResults).not.toHaveBeenCalled()
    expect(wrapper.get('.re-action a').text()).toBe('Внести результат')
  })

  it('никто не ввёл результат: вместо таблицы из «ещё не ввели» объяснение', async () => {
    const empty = standardPayload()
    empty.tables.forEach((t) => { t.waiting = [...t.ranked, ...t.waiting]; t.ranked = [] })
    const ctx = makeApp({ page: page({ stage: 'live' }), path: '/e/7/results/' })
    ctx.results.state.current = empty
    const wrapper = mount(EventApp, { props: { app: ctx.app }, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    expect(wrapper.get('.re-closed h2').text()).toBe('Результатов пока нет')
    expect(wrapper.get('.re-closed').text()).toContain('Они появятся 4 октября')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('есть результаты: таблица группы', async () => {
    const { wrapper, results } = await open({ page: page({ stage: 'live' }) })
    expect(results.api.getResults).toHaveBeenCalled()
    expect(wrapper.find('table.re-rt').exists()).toBe(true)
    expect(wrapper.text()).toContain('Андреев И.')
  })

  it('запомненный участник сразу открывает свою группу; общая запись видна и вкладкам «Инфо» и «Участники»', async () => {
    const store = memoryStore({
      [rememberKey(EVENT_ID)]: JSON.stringify({ id: 9, first_name: 'Иван', last_name: 'Андреев', gender: 'MALE', group_index: 0 }),
    })
    const { wrapper } = await open({ page: page({ stage: 'live' }), store })
    expect(wrapper.find('tr.is-me').exists()).toBe(true)
  })
})

describe('«Участники»', () => {
  const open = async (options: AppOptions & { me?: boolean } = {}) => {
    const ctx = await mountApp(options)
    await ctx.wrapper.findAll('.re-tabs a')[2].trigger('click')
    await flushPromises()
    return ctx
  }
  const names = (wrapper: VueWrapper) => wrapper.findAll('.re-prow .re-pr-name').map((n) => n.text())

  it('список по фамилии с группой, полом и сетом; строка данных', async () => {
    const { wrapper } = await open()
    expect(names(wrapper)).toEqual(['Зайцева Юлия', 'Кузнецов Алексей', 'Орлова Анна', 'Соколов Дмитрий'])
    expect(wrapper.findAll('.re-prow')[0].text()).toContain('Спорт · Ж')
    expect(wrapper.findAll('.re-prow')[0].text()).toContain('сет 3')
    expect(wrapper.findAll('.re-pr-meta')[0].text()).toBe('1990 · 1 сп.р. · Москва · «Магнезия»')
    expect(wrapper.get('.re-plist-head').text()).toContain('4 участника')
    expect(wrapper.get('.re-plist-head').text()).toContain('М 2 · Ж 2')
  })

  it('поиск по фамилии, подсчёт найденных', async () => {
    const { wrapper } = await open()
    await wrapper.get('#re-q').setValue('ов')
    expect(names(wrapper)).toEqual(['Кузнецов Алексей', 'Орлова Анна', 'Соколов Дмитрий'])
    expect(wrapper.get('.re-plist-head').text()).toContain('Найдено 3')
    expect(wrapper.get('.re-plist-head').text()).toContain('из 4')
  })

  it('фильтры по полу, группе и сету; карточка сета работает как фильтр и снимается повторным нажатием', async () => {
    const { wrapper } = await open()
    await byText(wrapper, '.re-seg button', 'Ж')!.trigger('click')
    expect(names(wrapper)).toEqual(['Зайцева Юлия', 'Орлова Анна'])
    await byText(wrapper, '.re-chips button', 'Новички')!.trigger('click')
    expect(names(wrapper)).toEqual(['Орлова Анна'])
    await byText(wrapper, '.re-chips button', 'Все группы')!.trigger('click')
    const card = byText(wrapper, '.re-setcard', 'Сет 3')!
    await card.trigger('click')
    expect(names(wrapper)).toEqual(['Зайцева Юлия'])
    expect(card.attributes('aria-pressed')).toBe('true')
    await card.trigger('click')
    expect(names(wrapper)).toEqual(['Зайцева Юлия', 'Орлова Анна'])
  })

  it('на фильтрах групп число участников, на карточках сетов заполненность', async () => {
    const { wrapper } = await open()
    expect(byText(wrapper, '.re-chips button', 'Спорт')!.text()).toContain('2')
    expect(byText(wrapper, '.re-setcard', 'Сет 1')!.text()).toContain('2 из 16')
  })

  it('никого не нашли: подсказка и «Показать всех»', async () => {
    const { wrapper } = await open()
    await wrapper.get('#re-q').setValue('яяя')
    expect(wrapper.get('.re-none').text()).toContain('Проверьте фамилию')
    expect(wrapper.get('.re-none').text()).toContain('вы ещё не зарегистрированы')
    await wrapper.get('.re-none .re-linkbtn').trigger('click')
    expect(names(wrapper)).toHaveLength(4)
  })

  it('внизу приглашение зарегистрироваться, пока браузер не помнит участника', async () => {
    expect(actionText((await open()).wrapper)).toContain('нет вас в списке? зарегистрируйтесь')
    expect(actionText((await open({ me: true })).wrapper)).toBe('')
  })

  it('список пуст: объяснение, для «ввода без регистрации» — другое', async () => {
    const empty = await open({ people: [] })
    expect(empty.wrapper.get('.re-none').text()).toBe('Пока никто не зарегистрировался.')
    const wo = await open({ people: [], page: page({ is_without_registration: true }) })
    expect(wo.wrapper.get('.re-none').text()).toContain('Участники появятся здесь, когда начнут вносить результаты')
  })

  it('нет связи: ошибка и «Повторить»', async () => {
    const ctx = makeApp({ path: '/e/7/participants/' })
    ctx.api.getPeople.mockRejectedValueOnce(apiError('network', 0))
    const wrapper = mount(EventApp, { props: { app: ctx.app }, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    expect(wrapper.get('[role=alert]').text()).toContain('Нет связи')
    await wrapper.get('[role=alert] button').trigger('click')
    await flushPromises()
    expect(names(wrapper)).toHaveLength(4)
  })

  it('поля, которые событие не собирает, в таблице не показываются', async () => {
    const p = page({ registration: { ...makePage().registration, fields: ['gender', 'city'] } })
    const { wrapper } = await open({ page: p })
    expect(wrapper.get('.re-plist-cols').text()).toBe('УчастникГородГруппаСет')
  })

  it('карточка участника и «Это я, запомнить»', async () => {
    const { wrapper } = await open()
    await wrapper.findAll('.re-prow')[1].trigger('click')
    const sheet = wrapper.get('.re-sheet')
    expect(sheet.get('h3').text()).toBe('Кузнецов Алексей')
    expect(sheet.text()).toContain('Новички, мужчины')
    expect(sheet.text()).toContain('1, 10:00')
    expect(sheet.text()).not.toContain('PIN')
    await byText(sheet as unknown as VueWrapper, 'button', 'Это я')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-sheet').exists()).toBe(false)
    expect(wrapper.get('.re-toast').text()).toContain('Запомнили')
    expect(wrapper.findAll('.re-prow')[1].classes()).toContain('is-me')
    expect(wrapper.findAll('.re-prow')[1].find('.re-tag').text()).toBe('вы')
  })

  it('своя карточка: пояснение вместо «Это я»', async () => {
    const { wrapper } = await open({ me: true })
    await wrapper.findAll('.re-prow')[0].trigger('click')
    expect(wrapper.get('.re-sheet').text()).toContain('Это вы')
    expect(byText(wrapper.get('.re-sheet') as unknown as VueWrapper, 'button', 'Это я')).toBeUndefined()
  })

  it('место в карточке только когда результаты открыты', async () => {
    const people = standardPeople()
    people[0] = { ...people[0], entered: true, place: 2, place_of: 9 }
    const { wrapper } = await open({ people })
    await wrapper.findAll('.re-prow')[0].trigger('click')
    expect(wrapper.get('.re-sheet').text()).toContain('2 из 9')
    const hidden = await open({ people: standardPeople() })
    await hidden.wrapper.findAll('.re-prow')[0].trigger('click')
    expect(hidden.wrapper.get('.re-sheet').text()).not.toContain('Место')
  })

  it('организатору в карточке видны PIN, контакты, оплата и ссылка на правку анкеты', async () => {
    const ctx = makeApp({ path: '/e/7/participants/', page: page({ pay, can_manage: true }) })
    ctx.api.getPeople.mockResolvedValue({
      can_manage: true,
      participants: [makePerson('Иванов', 'Иван', { id: 9, pin: 4321, phone: '+79990001122', email: 'ivan@example.com', paid: false, entered: true })],
    })
    const wrapper = mount(EventApp, { props: { app: ctx.app }, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    await wrapper.get('.re-prow').trigger('click')
    const sheet = wrapper.get('.re-sheet').text()
    expect(sheet).toContain('4321')
    expect(sheet).toContain('+79990001122')
    expect(sheet).toContain('ivan@example.com')
    expect(sheet).toContain('не оплачен')
    expect(sheet).toContain('внесён')
    expect(wrapper.get('.re-sheet a').attributes('href')).toBe('/e/7/p/9/')
  })
})

describe('регистрация', () => {
  const open = async (options: AppOptions = {}) => {
    const ctx = await mountApp({ ...options, path: '/e/7/registration/' })
    return ctx
  }
  const field = (wrapper: VueWrapper, label: string) =>
    wrapper.findAll('.re-fld').find((f) => f.text().startsWith(label))!
  const fillIn = async (wrapper: VueWrapper) => {
    await field(wrapper, 'Фамилия').get('input').setValue('Зайцева')
    await field(wrapper, 'Имя').get('input').setValue('Юлия')
    await byText(wrapper, '.re-choice button', 'Женщины')!.trigger('click')
    await field(wrapper, 'Год рождения').get('input').setValue('1996')
    await byText(wrapper, '.re-choice button', 'Спорт')!.trigger('click')
    await wrapper.findAll('.re-setpick button')[2].trigger('click')
  }

  it('три блока и поля из настроек события; необязательные помечены', async () => {
    const { wrapper } = await open()
    expect(wrapper.findAll('.re-form h3').map((h) => h.text())).toEqual(['О себе', 'Группа и сет', 'Связь'])
    expect(field(wrapper, 'Город').text()).toContain('необязательно')
    expect(field(wrapper, 'Год рождения').text()).not.toContain('необязательно')
    expect(wrapper.text()).toContain('Email и телефон видит только организатор')
    expect(wrapper.text()).toContain('В списке участников видны год рождения, разряд, город, команда')
  })

  it('событие не просит email, телефон и город — этих полей нет', async () => {
    const { wrapper } = await open({ page: page({ registration: { ...makePage().registration, fields: ['gender'] } }) })
    expect(wrapper.findAll('.re-form h3').map((h) => h.text())).toEqual(['О себе', 'Группа и сет'])
    expect(wrapper.find('input[type=email]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Город')
  })

  it('сеты со временем и свободными местами; заполненный выбрать нельзя', async () => {
    const { wrapper } = await open()
    const sets = wrapper.findAll('.re-setpick button')
    expect(sets[0].text()).toContain('10:00')
    expect(sets[0].text()).toContain('свободно 2 места')
    expect(sets[1].text()).toContain('мест нет')
    expect(sets[1].attributes('disabled')).toBeDefined()
    await sets[2].trigger('click')
    expect(sets[2].attributes('aria-checked')).toBe('true')
  })

  it('с онлайн-оплатой email обязателен, а внизу цена', async () => {
    const reg = { ...makePage().registration, required_fields: ['birth_year', 'email'] }
    const { wrapper } = await open({ page: page({ pay, registration: reg }) })
    expect(field(wrapper, 'Email').text()).not.toContain('необязательно')
    expect(wrapper.text()).toContain('Пришлём PIN и ссылку на оплату взноса')
    expect(actionText(wrapper).replace(/\s/g, ' ')).toContain('1 500 ₽')
    expect(actionText(wrapper)).toContain('оплата после регистрации')
  })

  it('пустая анкета: подсвечены поля, подсказка, запросов нет', async () => {
    const { wrapper, api } = await open()
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.re-fld.is-invalid').length).toBeGreaterThan(3)
    expect(wrapper.get('.re-toast').text()).toBe('Заполните фамилию, имя, пол, группу, сет, год рождения.')
    expect(api.register).not.toHaveBeenCalled()
  })

  it('успех: экран с PIN, память браузера и «Участники» / «К событию»', async () => {
    const { wrapper, api } = await open()
    await fillIn(wrapper)
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    expect(api.register).toHaveBeenCalledOnce()
    expect(wrapper.get('.re-done h2').text()).toBe('Вы зарегистрированы')
    expect(wrapper.get('.re-pin-big').text()).toBe('8335')
    expect(wrapper.text()).toContain('Мы запомнили вас на этом телефоне')
    expect(wrapper.findAll('.re-action a').map((a) => a.text())).toEqual(['Участники', 'К событию'])
    expect(window.location.pathname).toBe('/e/7/registration/')
    await byText(wrapper, '.re-action a', 'К событию')!.trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-me-card').text()).toContain('Зайцева Юлия')
  })

  it('организатор не показывает PIN: говорим, что он будет на карточке', async () => {
    const { wrapper, api } = await open()
    api.register.mockResolvedValue(makeRegistered({ pin: null }))
    await fillIn(wrapper)
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-pin-big').exists()).toBe(false)
    expect(wrapper.text()).toContain('PIN для ввода результатов будет на карточке участника')
  })

  it('с оплатой: статус, письмо и «Позже» / «Оплатить»', async () => {
    const { wrapper, api } = await open({ page: page({ pay }) })
    api.register.mockResolvedValue(makeRegistered({ emailed: true }))
    await fillIn(wrapper)
    await field(wrapper, 'Email').get('input').setValue('yulia@example.com')
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-card .re-pill').text()).toBe('не оплачен')
    expect(wrapper.text()).toContain('PIN и ссылку на оплату отправили на yulia@example.com')
    const buttons = wrapper.findAll('.re-action a')
    expect(buttons.map((a) => a.text().replace(/\s/g, ' '))).toEqual(['Позже', 'Оплатить 1 500 ₽'])
    expect(buttons[1].attributes('href')).toBe('/e/7/pay/?p=1')
  })

  it('«Зарегистрировать ещё одного»: пустая анкета с прежним городом', async () => {
    const { wrapper } = await open()
    await fillIn(wrapper)
    await field(wrapper, 'Город').get('input').setValue('Тверь')
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    await wrapper.get('.re-done .re-linkbtn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-done').exists()).toBe(false)
    expect((field(wrapper, 'Фамилия').get('input').element as HTMLInputElement).value).toBe('')
    expect((field(wrapper, 'Город').get('input').element as HTMLInputElement).value).toBe('Тверь')
  })

  it('такой участник уже есть: объяснение со ссылкой на список', async () => {
    const { wrapper, api } = await open()
    api.register.mockRejectedValueOnce(apiError('duplicate', 409))
    await fillIn(wrapper)
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    const banner = wrapper.get('.re-banner.is-error')
    expect(banner.text()).toContain('Зайцева Юлия уже есть в списке участников')
    expect(banner.text()).toContain('PIN подскажет организатор')
    await banner.get('.re-linkbtn').trigger('click')
    await flushPromises()
    expect(window.location.pathname).toBe('/e/7/participants/')
    expect((wrapper.get('#re-q').element as HTMLInputElement).value).toBe('Зайцева')
  })

  it('младше допустимого и сет заполнился', async () => {
    const { wrapper, api } = await open()
    api.register.mockRejectedValueOnce(apiError('too_young', 400, '', { min_age: 14 }))
    await fillIn(wrapper)
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-banner.is-error').text()).toContain('Участвовать можно с 14 лет')
    api.register.mockRejectedValueOnce(apiError('set_full', 400))
    await wrapper.get('.re-action .re-btn').trigger('click')
    await flushPromises()
    expect(wrapper.get('.re-banner.is-error').text()).toContain('Сет 3 заполнился, пока вы заполняли анкету')
    expect(wrapper.findAll('.re-setpick button').every((b) => b.attributes('aria-checked') === 'false')).toBe(true)
  })

  it('регистрация закрыта: вместо анкеты сообщение', async () => {
    const { wrapper } = await open({ page: page({ stage: 'reg_closed', registration: { ...makePage().registration, is_open: false } }) })
    expect(wrapper.text()).toContain('Регистрация закрыта или достигнут лимит участников')
    expect(wrapper.find('.re-form').exists()).toBe(false)
    expect(wrapper.find('.re-action').exists()).toBe(false)
  })

  it('«К событию» возвращает на «Инфо»', async () => {
    const { wrapper } = await open()
    await wrapper.get('.re-back').trigger('click')
    await flushPromises()
    expect(window.location.pathname).toBe('/e/7/')
    expect(wrapper.find('.re-info').exists()).toBe(true)
  })
})

describe('оплата', () => {
  it('ЮMoney: сумма, промокод и кнопка с ценой', async () => {
    const { wrapper, api } = await mountApp({ page: page({ pay }), path: '/e/7/pay/?p=1', me: true })
    expect(api.getPay).toHaveBeenCalledWith(EVENT_ID, 1)
    expect(wrapper.get('.re-amount').text().replace(/\s/g, ' ')).toBe('1 500 ₽')
    expect(wrapper.get('.re-lead').text()).toContain('Зайцева Юлия')
    expect(wrapper.get('.re-action .re-btn').text().replace(/\s/g, ' ')).toBe('Перейти к оплате · 1 500 ₽')
  })

  it('СБП: сумма, QR-код для другого устройства, предупреждение про ручную отметку', async () => {
    const ctx = makeApp({ page: page({ pay: { ...pay, type: 'sbp' } }), path: '/e/7/pay/?p=1' })
    ctx.api.getPay.mockResolvedValue({ type: 'sbp', amount: 1500, link: 'https://qr.nspk.ru/X', qr: 'data:image/svg+xml,x' })
    const wrapper = mount(EventApp, { props: { app: ctx.app }, attachTo: document.body })
    wrappers.push(wrapper)
    await flushPromises()
    expect(wrapper.get('.re-qr').attributes('src')).toBe('data:image/svg+xml,x')
    expect(wrapper.text()).toContain('Оплату по СБП организатор отмечает вручную')
    expect(wrapper.findAll('.re-action .re-btn').map((b) => b.text())).toEqual(['Готово', 'Открыть банк'])
  })

  it('не знаем, за кого платить: ведём в список участников', async () => {
    const { wrapper } = await mountApp({ page: page({ pay }), path: '/e/7/pay/' })
    expect(wrapper.get('.re-banner').text()).toContain('Не знаем, за кого платить')
    expect(wrapper.get('.re-banner a').attributes('href')).toBe('/e/7/participants/')
  })

  it('оплата недоступна и уже оплачено', async () => {
    const a = makeApp({ page: page({ pay }), path: '/e/7/pay/?p=1' })
    a.api.getPay.mockRejectedValue(apiError('pay_unavailable', 403))
    const wa = mount(EventApp, { props: { app: a.app }, attachTo: document.body })
    wrappers.push(wa)
    await flushPromises()
    expect(wa.text()).toContain('Онлайн-оплата временно недоступна')

    const b = makeApp({ page: page({ pay }), path: '/e/7/pay/?p=1' })
    b.api.getPay.mockResolvedValue({ type: 'paid' })
    const wb = mount(EventApp, { props: { app: b.app }, attachTo: document.body })
    wrappers.push(wb)
    await flushPromises()
    expect(wb.text()).toContain('Платить ещё раз не нужно')
  })

  it('возврат со страницы оплаты: «Платёж отправлен», пока подтверждения нет', async () => {
    const { wrapper } = await mountApp({ page: page({ pay }), path: '/e/7/pay/done/', me: true })
    expect(wrapper.get('.re-done h2').text()).toBe('Платёж отправлен')
    expect(wrapper.get('.re-action a').text()).toBe('К событию')
  })
})
