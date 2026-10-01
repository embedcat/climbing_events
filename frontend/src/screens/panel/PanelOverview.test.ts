import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ApiError } from '../../api/http'
import type { PanelOverview as Overview } from '../../api/panel'
import type { PanelSectionGroup } from './context'
import PanelOverview from './PanelOverview.vue'
import { EVENT_ID, fakePanelApi, makeOverview } from './testing'
import { usePanelOverview } from './usePanelOverview'

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

const SECTIONS: PanelSectionGroup[] = [
  { title: '', items: [{ url_name: 'admin_actions', url: '/e/128/admin_actions/', title: 'Обзор', hint: 'Главное в день события', external: false, current: true }] },
  {
    title: 'В день события',
    items: [
      { url_name: 'panel_participants', url: '/e/128/people/', title: 'Участники', hint: 'PIN, контакты, оплата', external: false, current: false },
      { url_name: 'matrix', url: '/e/128/matrix/', title: 'Ввод результатов', hint: 'Матрица для бумажных карточек', external: true, current: false },
    ],
  },
]

async function show(options: { overview?: Overview, api?: ReturnType<typeof fakePanelApi>, isSuperuser?: boolean } = {}) {
  const api = options.api ?? fakePanelApi(options.overview)
  const navigate = vi.fn()
  const app = usePanelOverview({
    eventId: EVENT_ID, api, isSuperuser: options.isSuperuser, navigate, copy: vi.fn(async () => {}), origin: 'https://rockevents.ru',
  })
  const wrapper = mount(PanelOverview, { props: { app, sections: SECTIONS } })
  await flushPromises()
  return { wrapper, app, api, navigate }
}

const switchOf = (wrapper: Awaited<ReturnType<typeof show>>['wrapper'], flag: string) => wrapper.get(`#re-switch-${flag}`)

describe('«Обзор» панели', () => {
  it('показывает четыре переключателя в их текущем положении', async () => {
    const { wrapper } = await show()
    expect(wrapper.findAll('.re-p-sw')).toHaveLength(4)
    expect(switchOf(wrapper, 'is_published').attributes('aria-checked')).toBe('true')
    expect(switchOf(wrapper, 'is_enter_result_allowed').attributes('aria-checked')).toBe('false')
    expect(wrapper.text()).toContain('Этап для участников: Регистрация открыта')
  })

  it('нажатие переключает сразу и отправляет только его', async () => {
    const { wrapper, api } = await show()
    await switchOf(wrapper, 'is_enter_result_allowed').trigger('click')
    expect(switchOf(wrapper, 'is_enter_result_allowed').attributes('aria-checked')).toBe('true')
    await flushPromises()
    expect(api.setFlags).toHaveBeenCalledWith(EVENT_ID, { is_enter_result_allowed: true })
  })

  it('ошибка возвращает переключатель и показывает сообщение', async () => {
    const api = fakePanelApi(makeOverview(), { setFlags: vi.fn().mockRejectedValue(new ApiError(0, 'network', 'Нет связи с сервером.')) })
    const { wrapper } = await show({ api })
    await switchOf(wrapper, 'is_results_allowed').trigger('click')
    await flushPromises()
    expect(switchOf(wrapper, 'is_results_allowed').attributes('aria-checked')).toBe('true')
    expect(wrapper.find('.re-toast').text()).toBe('Нет связи с сервером.')
  })

  it('числа: участники, внесли результат, оплатили; без оплаты вместо числа прочерк', async () => {
    const { wrapper } = await show({ overview: makeOverview({ participants_count: 42, entered_count: 21, paid_count: 31 }) })
    expect(wrapper.findAll('.re-p-kpi').map((k) => k.text())).toEqual(['42участника', '21внесли результат', '31оплатили взнос'])
    expect(wrapper.find('.re-p-bar i').attributes('style')).toContain('width: 50%')
    const free = await show({ overview: makeOverview({ is_pay_allowed: false, entered_count: 0 }) })
    expect(free.wrapper.findAll('.re-p-kpi')[2].text()).toContain('—')
    expect(free.wrapper.find('.re-p-bar').exists()).toBe(false)
  })

  it('чек-лист виден, пока не сделано обязательное, и ведёт в нужные разделы', async () => {
    const { wrapper } = await show({
      overview: makeOverview({ checklist: [{ id: 'description', done: false, poster: false }, { id: 'pay', done: false, optional: true }, { id: 'publish', done: true }] }),
    })
    expect(wrapper.find('#re-p-todo').text()).toBe('Подготовка · 1 из 2')
    const links = wrapper.findAll('.re-p-todo a')
    expect(links.map((a) => a.attributes('href'))).toEqual(['/e/128/admin_description/', '/e/128/pay_settings/', '#re-switch-is_published'])
    expect(links[0].text()).toContain('замените текст по умолчанию и добавьте афишу')
  })

  it('когда всё готово, чек-лист скрыт', async () => {
    const { wrapper } = await show()
    expect(wrapper.find('#re-p-todo').exists()).toBe(false)
  })

  it('«Для зала»: ссылки на мониторы копируются', async () => {
    const { wrapper } = await show()
    const codes = wrapper.findAll('.re-p-link code').map((c) => c.text())
    expect(codes).toEqual(['rockevents.ru/e/128/results/?autorefresh&m', 'rockevents.ru/e/128/results/?autorefresh&f'])
    await wrapper.findAll('.re-p-link button')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-toast').text()).toBe('Ссылка скопирована (мужчины)')
  })

  it('разделы списком для телефона без самого «Обзора»', async () => {
    const { wrapper } = await show()
    expect(wrapper.findAll('.re-p-secmenu a').map((a) => [a.find('b').text(), a.attributes('href')])).toEqual([
      ['Участники', '/e/128/people/'], ['Ввод результатов ↗', '/e/128/matrix/'],
    ])
  })

  it('служебное действие: окно подтверждения, отмена и подтверждение', async () => {
    const { wrapper, api } = await show()
    const clear = wrapper.findAll('.re-p-acts button').find((b) => b.text() === 'Удалить результаты')!
    await clear.trigger('click')
    expect(wrapper.find('[role="alertdialog"]').text()).toContain('Удалить результаты всех участников?')
    await wrapper.findAll('[role="alertdialog"] button')[0].trigger('click')
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
    expect(api.runAction).not.toHaveBeenCalled()

    await clear.trigger('click')
    await wrapper.findAll('[role="alertdialog"] button')[1].trigger('click')
    await flushPromises()
    expect(api.runAction).toHaveBeenCalledWith(EVENT_ID, 'clear_results')
    expect(wrapper.find('.re-toast').text()).toBe('Результаты удалены')
  })

  it('Escape закрывает окно подтверждения', async () => {
    const { wrapper } = await show()
    await wrapper.findAll('.re-p-acts button')[0].trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(wrapper.find('[role="alertdialog"]').exists()).toBe(false)
  })

  it('удаление события уводит на адрес из ответа', async () => {
    const api = fakePanelApi(makeOverview(), { runAction: vi.fn(async () => ({ removed: true as const, redirect: '/my_events/' })) })
    const { wrapper, navigate } = await show({ api })
    await wrapper.findAll('.re-p-acts button').find((b) => b.text() === 'Удалить событие')!.trigger('click')
    await wrapper.findAll('[role="alertdialog"] button')[1].trigger('click')
    await flushPromises()
    expect(navigate).toHaveBeenCalledWith('/my_events/')
  })

  it('завершённое событие: «Очистить событие» недоступно; тестовые данные только суперпользователю', async () => {
    const done = await show({ overview: makeOverview({ is_expired: true }) })
    const clear = done.wrapper.findAll('.re-p-acts button').find((b) => b.text() === 'Очистить событие')!
    expect(clear.attributes('disabled')).toBeDefined()
    expect(done.wrapper.text()).not.toContain('Тестовые данные')
    const admin = await show({ isSuperuser: true })
    expect(admin.wrapper.text()).toContain('Тестовые данные')
  })

  it('ошибка загрузки: сообщение и «Повторить»', async () => {
    const api = fakePanelApi(makeOverview(), {
      overview: vi.fn().mockRejectedValueOnce(new ApiError(403, 'error', 'Доступно только организатору события.')).mockResolvedValue(makeOverview()),
    })
    const { wrapper } = await show({ api })
    expect(wrapper.find('.re-p-err').text()).toContain('Доступно только организатору события.')
    await wrapper.find('.re-p-err button').trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-p-err').exists()).toBe(false)
    expect(wrapper.findAll('.re-p-sw')).toHaveLength(4)
  })
})
