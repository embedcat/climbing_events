import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { SiteContext } from '../home/context'
import { fakeSiteApi, makeMyCard, makeMyEvents, networkError } from '../home/testing'
import MineApp from './MineApp.vue'
import { useMineApp } from './useMineApp'

const LINKS = { home: '/', create: '/create/', mine: '/my_events/', login: '/accounts/login/', help: '/help/workflow/', stat: '/stat/', about: '/about/' }
const ctx: SiteContext = { authenticated: true, isSuperuser: false, links: LINKS }

async function show(initial: ReturnType<typeof makeMyEvents> | null, api = fakeSiteApi()) {
  const app = useMineApp({ api, initial })
  const wrapper = mount(MineApp, { props: { app, ctx } })
  await flushPromises()
  return { wrapper, app, api }
}

describe('кабинет «Мои события»', () => {
  it('карточка: этап, числа и кнопки панели', async () => {
    const { wrapper } = await show(makeMyEvents({
      results: [makeMyCard({ id: 128, stage: 'live', participants_count: 42, entered_count: 21, paid_count: 31 })],
    }))
    const card = wrapper.find('.re-h-card')
    expect(card.text()).toContain('Идёт сейчас')
    expect(card.text()).toContain('★ полный доступ')
    expect(card.find('.re-h-stats').text()).toBe('участников 42внесли результат 21оплатили 31')
    expect(card.findAll('.re-h-btn').map((a) => [a.text(), a.attributes('href')])).toEqual([
      ['Панель', '/e/128/admin_actions/'], ['Страница события', '/e/128/'], ['Ввод результатов', '/e/128/matrix/'],
    ])
  })

  it('без оплаты числа об оплате не показываются, до начала ввода кнопки ввода нет', async () => {
    const { wrapper } = await show(makeMyEvents({ results: [makeMyCard({ stage: 'reg', is_pay_allowed: false })] }))
    expect(wrapper.find('.re-h-stats').text()).not.toContain('оплатили')
    expect(wrapper.text()).not.toContain('Ввод результатов')
    expect(wrapper.text()).not.toContain('с оплатой')
  })

  it('фильтр скрывает лишние события, счётчики остаются', async () => {
    const { wrapper } = await show(makeMyEvents({
      results: [makeMyCard({ id: 1, title: 'Идёт', stage: 'live' }), makeMyCard({ id: 2, title: 'Позже', stage: 'reg' })],
    }))
    const buttons = wrapper.findAll('[aria-label="Фильтр"] button')
    expect(buttons.map((b) => b.text())).toEqual(['Все2', 'Идут1', 'Впереди1', 'Завершены0'])
    await buttons[2].trigger('click')
    expect(wrapper.findAll('.re-h-card')).toHaveLength(1)
    expect(wrapper.find('.re-h-card').text()).toContain('Позже')
    await buttons[3].trigger('click')
    expect(wrapper.find('.re-h-none').text()).toBe('В этом фильтре пока ничего нет.')
  })

  it('суперпользователь видит переключатель и владельца события', async () => {
    const api = fakeSiteApi({
      myEvents: vi.fn(async () => makeMyEvents({
        scope: 'all', is_superuser: true, results: [makeMyCard({ owner: 'anna@lesnaya.ru' })],
      })),
    })
    const { wrapper } = await show(makeMyEvents({ is_superuser: true }), api)
    expect(wrapper.find('h1').text()).toBe('Мои события')
    await wrapper.findAll('[aria-label="Чьи события"] button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.find('h1').text()).toBe('Все события')
    expect(wrapper.find('.re-h-meta').text()).toContain('anna@lesnaya.ru')
  })

  it('обычному организатору переключателя нет', async () => {
    const { wrapper } = await show(makeMyEvents())
    expect(wrapper.find('[aria-label="Чьи события"]').exists()).toBe(false)
  })

  it('пусто: предлагает создать событие', async () => {
    const { wrapper } = await show(makeMyEvents({ results: [] }))
    expect(wrapper.find('.re-h-none').text()).toContain('Создайте первое событие')
    expect(wrapper.find('a[href="/create/"]').exists()).toBe(true)
  })

  it('ошибка загрузки: сообщение и «Повторить»', async () => {
    const api = fakeSiteApi({ myEvents: vi.fn().mockRejectedValueOnce(networkError()).mockResolvedValue(makeMyEvents()) })
    const { wrapper } = await show(null, api)
    expect(wrapper.find('.re-h-err').text()).toContain('Нет связи с сервером.')
    await wrapper.find('.re-h-err button').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.re-h-card')).toHaveLength(1)
  })
})
