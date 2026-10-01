import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { rememberParticipant } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import type { SiteContext } from './context'
import HomeApp from './HomeApp.vue'
import { fakeSiteApi, makeCard, makeCatalog, makeParticipation, networkError } from './testing'
import { useHomeApp } from './useHomeApp'

const LINKS = { home: '/', create: '/create/', mine: '/my_events/', login: '/accounts/login/', help: '/help/workflow/', stat: '/stat/', about: '/about/' }
const guest: SiteContext = { authenticated: false, isSuperuser: false, links: LINKS }
const organizer: SiteContext = { authenticated: true, isSuperuser: false, links: LINKS }

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

async function show(options: {
  ctx?: SiteContext
  catalog?: ReturnType<typeof makeCatalog> | null
  api?: ReturnType<typeof fakeSiteApi>
  store?: ReturnType<typeof memoryStore>
} = {}) {
  const api = options.api ?? fakeSiteApi()
  const app = useHomeApp({
    api, store: options.store ?? memoryStore(), initial: options.catalog === undefined ? makeCatalog() : options.catalog,
  })
  const wrapper = mount(HomeApp, { props: { app, ctx: options.ctx ?? guest } })
  await flushPromises()
  return { wrapper, app, api }
}

describe('главная', () => {
  it('показывает карточки: метка этапа, название-ссылка, дата и место, кнопки по этапу', async () => {
    const { wrapper } = await show({
      catalog: makeCatalog({ results: [makeCard(), makeCard({ id: 127, title: 'Ночной боулдеринг', stage: 'live' })] }),
    })
    const cards = wrapper.findAll('.re-h-ev')
    expect(cards).toHaveLength(2)
    expect(cards[0].text()).toContain('Регистрация открыта')
    expect(cards[0].find('.re-h-title a').attributes('href')).toBe('/e/128/')
    expect(cards[0].find('.re-h-meta').text()).toBe('4 октября 2026 г. · Скалодром на Лесной')
    expect(cards[0].findAll('.re-h-btn').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Зарегистрироваться', '/e/128/registration/'], ['Подробнее', '/e/128/'],
    ])
    expect(cards[1].find('.re-tag').classes()).toEqual(expect.arrayContaining(['is-ok', 'is-live']))
    expect(cards[1].find('.re-h-btn.is-primary').attributes('href')).toBe('/e/127/enter/')
  })

  it('без афиши подставляет картинку по умолчанию', async () => {
    const { wrapper } = await show({ catalog: makeCatalog({ results: [makeCard({ poster: null })] }) })
    expect(wrapper.find('.re-h-ev img').attributes('src')).toBe('/static/events/img/default_poster.png')
  })

  it('гость видит призыв создать событие, организатор свои ссылки и пометку «ваше»', async () => {
    const guestView = (await show()).wrapper
    expect(guestView.find('.re-h-promo').exists()).toBe(true)
    expect(guestView.text()).not.toContain('Вы вошли как организатор')

    const orgView = (await show({ ctx: organizer, catalog: makeCatalog({ results: [makeCard({ mine: true })] }) })).wrapper
    expect(orgView.find('.re-h-promo').exists()).toBe(false)
    expect(orgView.text()).toContain('Вы вошли как организатор')
    expect(orgView.find('.re-h-row a[href="/my_events/"]').exists()).toBe(true)
    expect(orgView.find('.re-h-ev').text()).toContain('ваше')
  })

  it('вкладки показывают счётчики и переключают период', async () => {
    const api = fakeSiteApi()
    const { wrapper } = await show({ api, catalog: makeCatalog({ counts: { upcoming: 4, past: 11 } }) })
    const [upcoming, past] = wrapper.findAll('.re-h-chips button')
    expect(upcoming.text()).toBe('Предстоящие4')
    expect(upcoming.attributes('aria-pressed')).toBe('true')
    await past.trigger('click')
    await flushPromises()
    expect(api.events).toHaveBeenCalledWith({ query: '', when: 'past', offset: 0 })
    expect(past.attributes('aria-pressed')).toBe('true')
  })

  it('поиск ищет после паузы в наборе', async () => {
    const api = fakeSiteApi()
    const { wrapper } = await show({ api })
    await wrapper.find('input[type="search"]').setValue('осенний')
    expect(api.events).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(300)
    expect(api.events).toHaveBeenCalledWith({ query: 'осенний', when: 'upcoming', offset: 0 })
  })

  it('пустой результат: подсказка для поиска и для пустого сайта', async () => {
    const { wrapper, app } = await show({ catalog: makeCatalog({ results: [] }) })
    expect(wrapper.find('.re-h-none').text()).toBe('Здесь пока нет событий.')
    app.query = 'нет такого'
    await flushPromises()
    expect(wrapper.find('.re-h-none').text()).toContain('Ничего не нашли')
  })

  it('ошибка загрузки: сообщение и «Повторить»', async () => {
    const api = fakeSiteApi({ events: vi.fn().mockRejectedValueOnce(networkError()).mockResolvedValueOnce(makeCatalog()) })
    const { wrapper } = await show({ api, catalog: null })
    expect(wrapper.find('.re-h-err').text()).toContain('Нет связи с сервером.')
    await wrapper.find('.re-h-err button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-h-err').exists()).toBe(false)
    expect(wrapper.findAll('.re-h-ev')).toHaveLength(1)
  })

  it('«Показать ещё» есть, пока сервер говорит, что есть ещё', async () => {
    const api = fakeSiteApi({ events: vi.fn().mockResolvedValue(makeCatalog({ results: [makeCard({ id: 2 })], has_more: false })) })
    const { wrapper } = await show({ api, catalog: makeCatalog({ has_more: true }) })
    await wrapper.find('.re-h-more').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.re-h-ev')).toHaveLength(2)
    expect(wrapper.find('.re-h-more').exists()).toBe(false)
  })

  it('«Вы участвуете»: строки по записям браузера со ссылкой и подписью', async () => {
    const store = memoryStore()
    rememberParticipant(store, 128, { id: 7, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 })
    const api = fakeSiteApi({ participations: vi.fn(async () => [makeParticipation()]) })
    const { wrapper } = await show({ api, store })
    const row = wrapper.find('.re-h-mcard')
    expect(row.attributes('href')).toBe('/e/128/')
    expect(row.text()).toContain('Осенний фестиваль')
    expect(row.text()).toContain('Зайцева Юлия · Сет 3, 16:00 · взнос не оплачен')
    expect(row.text()).toContain('Открыть →')
  })

  it('без записей в браузере блока «Вы участвуете» нет; в подвале ссылки на проект', async () => {
    const { wrapper } = await show()
    expect(wrapper.find('.re-h-mine').exists()).toBe(false)
    expect(wrapper.find('.re-h-foot a[href="/stat/"]').exists()).toBe(true)
    expect(wrapper.find('.re-h-foot a[href="/about/"]').exists()).toBe(true)
  })
})
