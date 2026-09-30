import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import type { EntryConfig } from '../../api/entry'
import { memoryStore } from '../../domain/storage'
import EntryApp from './EntryApp.vue'
import { apiError, fakeApi, makeConfig, makeParticipant, makePayload, networkError } from './testing'
import { useEntryFlow } from './useEntryFlow'

const RESULTS_URL = '/e/7/results/'

async function mountApp(configOverrides: Partial<EntryConfig> = {}) {
  const config = makeConfig(configOverrides)
  const api = fakeApi(config)
  const flow = useEntryFlow({ eventId: 7, api, store: memoryStore(), readHash: () => '', clearHash: () => {} })
  const wrapper = mount(EntryApp, { props: { flow, resultsUrl: RESULTS_URL }, attachTo: document.body })
  await flushPromises()
  return { wrapper, api, flow, config }
}

async function typePin(wrapper: VueWrapper, pin = '1234') {
  await wrapper.get('input.re-pin').setValue(pin)
  await flushPromises()
}

const tile = (wrapper: VueWrapper, number: number) => wrapper.get(`button[aria-label^="Трасса ${number}:"]`)
const submitButton = (wrapper: VueWrapper) => wrapper.get('.re-action .re-btn.is-primary')

beforeEach(() => { document.body.innerHTML = '' })

describe('экран ввода: PIN и плитки', () => {
  it('от PIN до «Результаты отправлены»', async () => {
    const { wrapper, api } = await mountApp()
    expect(wrapper.text()).toContain('Введите PIN')

    await typePin(wrapper)
    expect(wrapper.text()).toContain('Зайцева Юлия')
    expect(wrapper.findAll('.re-tile')).toHaveLength(10)
    expect(wrapper.text()).toContain('отмечено 0 из 10')

    await tile(wrapper, 1).trigger('click')
    expect(tile(wrapper, 1).attributes('aria-label')).toBe('Трасса 1: flash')
    await tile(wrapper, 1).trigger('click')
    expect(tile(wrapper, 1).attributes('aria-label')).toBe('Трасса 1: redpoint')
    await tile(wrapper, 2).trigger('click')
    expect(wrapper.get('.re-s.is-fl').text()).toBe('FL 1')
    expect(wrapper.get('.re-s.is-rp').text()).toBe('RP 1')
    expect(wrapper.get('.re-of').text()).toBe('отмечено 2 из 10')

    await submitButton(wrapper).trigger('click')
    await flushPromises()
    expect(api.submit).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Результаты отправлены')
    expect(wrapper.get('.re-pc-place').text()).toBe('3')
    expect(wrapper.get('.re-pc-of').text()).toContain('из 9')
    expect(wrapper.get('a.re-btn.is-primary').attributes('href')).toBe(RESULTS_URL)
  })

  it('неверный PIN: сообщение под полем, поле остаётся', async () => {
    const { wrapper, api } = await mountApp()
    api.identify.mockRejectedValueOnce(apiError('pin_not_found', 404))
    await typePin(wrapper, '1111')
    expect(wrapper.get('.re-pin-msg').classes()).toContain('is-error')
    expect(wrapper.get('.re-pin-msg').text()).toContain('1111')
    expect(wrapper.find('input.re-pin').exists()).toBe(true)
  })

  it('буквы в PIN сразу исчезают из поля', async () => {
    const { wrapper } = await mountApp()
    const input = wrapper.get('input.re-pin')
    await input.setValue('12ab')
    expect((input.element as HTMLInputElement).value).toBe('12')
  })

  it('«Не вы?» возвращает к PIN', async () => {
    const { wrapper } = await mountApp()
    await typePin(wrapper)
    await wrapper.get('.re-who .re-linkbtn').trigger('click')
    expect(wrapper.find('input.re-pin').exists()).toBe(true)
    expect(wrapper.find('.re-tiles').exists()).toBe(false)
  })

  it('показывает группу и сет участника', async () => {
    const config = makeConfig({ groups: ['Новички', 'Спорт'], sets: [{ index: 0, name: '10:00', is_full: false }] })
    const { wrapper, api } = await mountApp({ groups: config.groups, sets: config.sets })
    api.identify.mockResolvedValueOnce(makePayload(config, {
      participant: makeParticipant({ group: 'Спорт', group_index: 1, set: '10:00' }),
    }))
    await typePin(wrapper)
    expect(wrapper.get('.re-who-meta').text()).toBe('Спорт · Ж · сет 1, 10:00')
  })

  it('нет связи при отправке: сообщение, кнопка «Отправить ещё раз», отметки на месте', async () => {
    const { wrapper, api } = await mountApp()
    await typePin(wrapper)
    await tile(wrapper, 4).trigger('click')
    api.submit.mockRejectedValueOnce(networkError())
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(wrapper.get('.re-send-err').text()).toContain('Нет связи с сервером')
    expect(submitButton(wrapper).text()).toBe('Отправить ещё раз')
    expect(tile(wrapper, 4).attributes('aria-label')).toBe('Трасса 4: flash')

    await submitButton(wrapper).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Результаты отправлены')
  })

  it('ввод закрыт', async () => {
    const { wrapper } = await mountApp({ is_enter_result_allowed: false })
    expect(wrapper.text()).toContain('Ввод результатов закрыт')
    expect(wrapper.find('input.re-pin').exists()).toBe(false)
  })

  it('«Исправить» после отправки возвращает к плиткам', async () => {
    const { wrapper } = await mountApp()
    await typePin(wrapper)
    await tile(wrapper, 1).trigger('click')
    await submitButton(wrapper).trigger('click')
    await flushPromises()
    await wrapper.get('.re-act-row.is-two .re-btn:not(.is-primary)').trigger('click')
    expect(tile(wrapper, 1).attributes('aria-label')).toBe('Трасса 1: flash')
  })
})

describe('экран ввода: проверка перед отправкой', () => {
  it('шторка со сводкой, «Изменить» закрывает, «Всё верно» отправляет', async () => {
    const { wrapper, api } = await mountApp({ is_check_result_before_enter: true })
    await typePin(wrapper)
    await tile(wrapper, 1).trigger('click')
    await tile(wrapper, 3).trigger('click')
    await tile(wrapper, 3).trigger('click')
    await submitButton(wrapper).trigger('click')

    const sheet = wrapper.get('[role="dialog"]')
    expect(sheet.text()).toContain('Проверьте перед отправкой')
    expect(sheet.findAll('.re-ck')[0].text()).toContain('1')
    expect(sheet.findAll('.re-ck')[1].text()).toContain('3')
    expect(sheet.text()).toContain('Без пролаза: 8 трасс')
    expect(api.submit).not.toHaveBeenCalled()

    await sheet.get('.re-btn:not(.is-primary)').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)

    await submitButton(wrapper).trigger('click')
    await wrapper.get('[role="dialog"] .re-btn.is-primary').trigger('click')
    await flushPromises()
    expect(api.submit).toHaveBeenCalledOnce()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Результаты отправлены')
  })

  it('Escape закрывает шторку', async () => {
    const { wrapper } = await mountApp({ is_check_result_before_enter: true })
    await typePin(wrapper)
    await submitButton(wrapper).trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
})

describe('экран ввода: французская система', () => {
  it('у каждой трассы два счётчика, зона позже топа блокирует кнопку', async () => {
    const { wrapper, api } = await mountApp({ score_type: 'FR', routes_num: 5 })
    await typePin(wrapper)
    expect(wrapper.findAll('.re-frow')).toHaveLength(5)
    expect(wrapper.text()).toContain('0 топов')

    const plus = (route: number, kind: 'топ' | 'зона') =>
      wrapper.get(`button[aria-label="Трасса ${route}, ${kind}: на попытку больше"]`)
    await plus(2, 'топ').trigger('click')
    expect(wrapper.findAll('.re-frow')[1].findAll('output').map((o) => o.text())).toEqual(['1', '1'])
    await plus(2, 'зона').trigger('click')

    expect(wrapper.findAll('.re-frow')[1].text()).toContain('Зона не может быть позже топа')
    expect(wrapper.get('.re-action').text()).toContain('Трасса 2: зона позже топа')
    expect(submitButton(wrapper).attributes('disabled')).toBeDefined()
    await submitButton(wrapper).trigger('click')
    expect(api.submit).not.toHaveBeenCalled()

    await wrapper.get('button[aria-label="Трасса 2, зона: на попытку меньше"]').trigger('click')
    expect(submitButton(wrapper).attributes('disabled')).toBeUndefined()
    await submitButton(wrapper).trigger('click')
    await flushPromises()
    expect(api.submit).toHaveBeenCalledWith(7, '1234', expect.arrayContaining([{ top: 1, zone: 1 }]), true)
  })
})

describe('экран ввода: без регистрации', () => {
  const config = {
    is_without_registration: true,
    groups: ['Новички', 'Спорт'],
    sets: [{ index: 0, name: '10:00', is_full: false }, { index: 1, name: '13:00', is_full: true }],
    registration_fields: ['gender', 'city'],
  }

  it('анкета и плитки на одном экране, пустая анкета не отправляется', async () => {
    const { wrapper, api } = await mountApp(config)
    expect(wrapper.text()).toContain('Кто вы')
    expect(wrapper.findAll('.re-tile')).toHaveLength(10)
    expect(wrapper.text()).toContain('13:00 · мест нет')

    await submitButton(wrapper).trigger('click')
    expect(api.submitWithoutRegistration).not.toHaveBeenCalled()
    expect(wrapper.get('.re-toast').text()).toContain('Заполните фамилию, имя, пол, группу, сет')
    expect(wrapper.findAll('.re-fld.is-invalid').length).toBeGreaterThan(0)
  })

  it('заполненная анкета уходит вместе с результатами', async () => {
    const { wrapper, api } = await mountApp(config)
    const inputs = wrapper.findAll('.re-row2 input')
    await inputs[0].setValue('Маркова')
    await inputs[1].setValue('Мария')
    const press = async (label: string) => {
      const button = wrapper.findAll('.re-choice button').find((b) => b.text().startsWith(label))!
      await button.trigger('click')
    }
    await press('Женщины')
    await press('Спорт')
    await press('10:00')
    await wrapper.get('select, input[autocomplete="address-level2"]').setValue('Тула')
    await tile(wrapper, 2).trigger('click')
    await submitButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.submitWithoutRegistration).toHaveBeenCalledWith(7, {
      last_name: 'Маркова', first_name: 'Мария', gender: 'FEMALE', group_index: 1, set_index: 0, city: 'Тула',
    }, expect.arrayContaining([{ top: 1, zone: 0 }]), false)
    expect(wrapper.text()).toContain('Результаты отправлены')
  })
})
