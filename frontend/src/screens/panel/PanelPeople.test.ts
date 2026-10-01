import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import type { Person } from '../../api/event'
import { ApiError } from '../../api/http'
import { fakeEventApi, makePage, makePerson } from '../event/testing'
import PanelPeople from './PanelPeople.vue'
import { usePanelPeople } from './usePanelPeople'

const people = (): Person[] => [
  makePerson('Зайцева', 'Юлия', { id: 1, gender: 'FEMALE', group_index: 1, set_index: 2, pin: 8335, phone: '+7 999 000-11-22', email: 'yulia@example.com', paid: false, entered: false }),
  makePerson('Кузнецов', 'Алексей', { id: 2, group_index: 0, set_index: 0, pin: 4172, paid: true, entered: true }),
  makePerson('Орлова', 'Анна', { id: 3, gender: 'FEMALE', group_index: 0, set_index: 1, pin: 6029, paid: true }),
]

async function show(options: { page?: ReturnType<typeof makePage>, people?: Person[], api?: ReturnType<typeof fakeEventApi> } = {}) {
  const api = options.api ?? fakeEventApi(options.page ?? makePage({ pay: { is_allowed: true, type: 'yoomoney', price: 1500 } }), options.people ?? people())
  const app = usePanelPeople({ eventId: 7, api })
  const wrapper = mount(PanelPeople, { props: { app, csrfToken: 'TOKEN' } })
  await flushPromises()
  return { wrapper, app, api }
}

describe('«Участники» панели', () => {
  it('таблица по алфавиту: имя, PIN, группа, сет, оплата и результат', async () => {
    const { wrapper } = await show()
    const rows = wrapper.findAll('.re-p-row')
    expect(rows.map((r) => r.find('.re-p-name').text())).toEqual(['Зайцева Юлия', 'Кузнецов Алексей', 'Орлова Анна'])
    expect(wrapper.find('.re-p-cols').text()).toBe('УчастникPINГруппаСетОплатаРезультат')
    expect(rows[1].find('.re-p-pin').text()).toBe('4172')
    expect(rows[0].find('.re-p-meta').text()).toBe('Спорт · Ж · сет 3')
    expect(rows[0].find('.re-p-pill').text()).toBe('не оплачен')
    expect(rows[1].find('.re-p-pill').text()).toBe('оплачен')
    expect(rows[1].findAll('.re-p-cell').at(-1)!.text()).toBe('внесён')
    expect(rows[0].findAll('.re-p-cell').at(-1)!.text()).toBe('—')
  })

  it('без оплаты и сетов лишних колонок нет', async () => {
    const { wrapper } = await show({ page: makePage({ sets: [], pay: { is_allowed: false, type: 'yoomoney', price: null } }) })
    expect(wrapper.find('.re-p-cols').text()).toBe('УчастникPINГруппаРезультат')
    expect(wrapper.find('.re-p-pill').exists()).toBe(false)
  })

  it('поиск по фамилии и по началу PIN', async () => {
    const { wrapper } = await show()
    const input = wrapper.find('input[type="search"]')
    await input.setValue('орл')
    expect(wrapper.findAll('.re-p-row')).toHaveLength(1)
    await input.setValue('41')
    expect(wrapper.findAll('.re-p-row').map((r) => r.find('.re-p-name').text())).toEqual(['Кузнецов Алексей'])
    expect(wrapper.find('.re-p-hint').text()).toBe('Найдено 1 из 3 участника.')
    await input.setValue('999999')
    expect(wrapper.find('.re-p-none').text()).toContain('Никого не нашли')
  })

  it('строка открывает карточку с контактами, оплатой и ссылками на правку', async () => {
    const { wrapper } = await show()
    await wrapper.find('.re-p-row[data-id="1"]').trigger('click')
    const sheet = wrapper.find('.re-p-sheet')
    expect(sheet.text()).toContain('Зайцева Юлия')
    expect(sheet.text()).toContain('8335')
    expect(sheet.text()).toContain('+7 999 000-11-22')
    expect(sheet.text()).toContain('yulia@example.com')
    expect(sheet.text()).toContain('не оплачен')
    expect(sheet.find('a[href="/e/7/p/1/"]').exists()).toBe(true)
    expect(sheet.find('a[href="/e/7/matrix/#p=1"]').exists()).toBe(true)
    await sheet.find('.re-btn').trigger('click')
    expect(wrapper.find('.re-p-sheet').exists()).toBe(false)
  })

  it('«Стартовый список» отправляет форму с CSRF-токеном на страницу протоколов', async () => {
    const { wrapper } = await show()
    const form = wrapper.find('form')
    expect(form.attributes('action')).toBe('/e/7/admin_protocols')
    expect(form.attributes('method')).toBe('post')
    expect(form.find('input[name="csrfmiddlewaretoken"]').element.getAttribute('value') ?? (form.find('input[name="csrfmiddlewaretoken"]').element as HTMLInputElement).value).toBe('TOKEN')
    expect(form.find('button[name="export_startlist"]').exists()).toBe(true)
  })

  it('пустое событие и ошибка загрузки', async () => {
    const empty = await show({ people: [] })
    expect(empty.wrapper.find('.re-p-none').text()).toBe('Пока никто не зарегистрировался.')

    const api = fakeEventApi()
    api.getPeople.mockRejectedValueOnce(new ApiError(0, 'network', 'нет'))
    const failed = await show({ api })
    expect(failed.wrapper.find('.re-p-err').text()).toContain('Нет связи с сервером')
    await failed.wrapper.find('.re-p-err button').trigger('click')
    await flushPromises()
    expect(failed.wrapper.findAll('.re-p-row').length).toBeGreaterThan(0)
  })

  it('загрузка берёт страницу события и участников одним заходом', async () => {
    const { api } = await show()
    expect(api.getPage).toHaveBeenCalledWith(7)
    expect(api.getPeople).toHaveBeenCalledWith(7)
  })
})

describe('usePanelPeople', () => {
  it('повторная загрузка при ошибке не стирает показанный список', async () => {
    const api = fakeEventApi(makePage(), people())
    const app = usePanelPeople({ eventId: 7, api })
    await app.load()
    api.getPeople.mockRejectedValueOnce(new ApiError(0, 'network', 'нет'))
    await app.load()
    expect(app.status).toBe('ready')
    expect(app.rows).toHaveLength(3)
    expect(vi.isMockFunction(api.getPage)).toBe(true)
  })
})
