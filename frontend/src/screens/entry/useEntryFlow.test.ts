import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { EntryConfig } from '../../api/entry'
import { draftKey } from '../../domain/draft'
import { createRememberedMe, loadRememberedParticipant } from '../../domain/remember'
import { emptyResults } from '../../domain/results'
import { memoryStore } from '../../domain/storage'
import { apiError, fakeApi, makeConfig, makeParticipant, makePayload, networkError } from './testing'
import { useEntryFlow } from './useEntryFlow'

const EVENT_ID = 7

function setup(configOverrides: Partial<EntryConfig> = {}, options: { hash?: string; store?: ReturnType<typeof memoryStore> } = {}) {
  const config = makeConfig(configOverrides)
  const api = fakeApi(config)
  const store = options.store ?? memoryStore()
  const clearHash = vi.fn()
  const scrollToError = vi.fn()
  const flow = useEntryFlow({
    eventId: EVENT_ID, api, store, readHash: () => options.hash ?? '', clearHash, scrollToError, now: () => 1_700_000_000_000,
  })
  return { config, api, store, flow, clearHash, scrollToError }
}

async function enter(flow: ReturnType<typeof setup>['flow'], pin = '1234') {
  await flow.init()
  await flow.identify(pin)
}

// flushPromises опирается на setImmediate, поэтому подменяем только таймеры тостов
beforeEach(() => { vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] }) })
afterEach(() => { vi.useRealTimers() })

describe('запуск', () => {
  it('просит PIN, если события с регистрацией и ввод открыт', async () => {
    const { flow, api } = setup()
    expect(flow.step).toBe('loading')
    await flow.init()
    expect(api.getConfig).toHaveBeenCalledWith(EVENT_ID)
    expect(flow.step).toBe('identify')
  })

  it('ввод закрыт организатором', async () => {
    const { flow } = setup({ is_enter_result_allowed: false })
    await flow.init()
    expect(flow.step).toBe('closed')
  })

  it('нет связи при загрузке события — можно повторить', async () => {
    const { flow, api } = setup()
    api.getConfig.mockRejectedValueOnce(networkError())
    await flow.init()
    expect(flow.step).toBe('fatal')
    expect(flow.fatalMessage).toMatch(/Нет связи/)
    await flow.init()
    expect(flow.step).toBe('identify')
  })

  it('событие не найдено', async () => {
    const { flow, api } = setup()
    api.getConfig.mockRejectedValueOnce(apiError('error', 404))
    await flow.init()
    expect(flow.step).toBe('fatal')
    expect(flow.fatalMessage).toMatch(/не найдено/)
  })

  it('ввод без регистрации открывает анкету сразу', async () => {
    const { flow, api } = setup({ is_without_registration: true })
    await flow.init()
    expect(flow.step).toBe('entry')
    expect(flow.withoutRegistration).toBe(true)
    expect(flow.results).toHaveLength(10)
    expect(api.identify).not.toHaveBeenCalled()
  })
})

describe('вход по PIN', () => {
  it('ищет участника только когда набраны четыре цифры', async () => {
    const { flow, api } = setup()
    await flow.init()
    await flow.identify('12')
    await flow.identify('12a')
    expect(api.identify).not.toHaveBeenCalled()
    expect(flow.step).toBe('identify')
    await flow.identify('1234')
    expect(api.identify).toHaveBeenCalledWith(EVENT_ID, '1234')
    expect(flow.step).toBe('entry')
    expect(flow.who?.last_name).toBe('Зайцева')
  })

  it('убирает из PIN всё, кроме цифр', async () => {
    const { flow, api } = setup()
    await flow.init()
    await flow.identify('1-2 3x4')
    expect(api.identify).toHaveBeenCalledWith(EVENT_ID, '1234')
    await flow.identify('12345')
    expect(flow.pinInput).toBe('1234')
  })

  it('PIN из QR-кода подставляется сам и сразу убирается из адреса', async () => {
    const { flow, api, clearHash } = setup({}, { hash: '#pin=4321' })
    await flow.init()
    expect(clearHash).toHaveBeenCalledOnce()
    expect(api.identify).toHaveBeenCalledWith(EVENT_ID, '4321')
    expect(flow.step).toBe('entry')
  })

  it('неверный PIN из QR-кода оставляет на экране PIN с сообщением', async () => {
    const { flow, api } = setup({}, { hash: '#pin=4321' })
    api.identify.mockRejectedValueOnce(apiError('pin_not_found', 404))
    await flow.init()
    expect(flow.step).toBe('identify')
    expect(flow.pinIsError).toBe(true)
    expect(flow.pinMessage).toContain('4321')
  })

  it('PIN не найден', async () => {
    const { flow, api } = setup()
    api.identify.mockRejectedValueOnce(apiError('pin_not_found', 404))
    await enter(flow, '1111')
    expect(flow.step).toBe('identify')
    expect(flow.pinIsError).toBe(true)
    expect(flow.pinMessage).toMatch(/1111 не найден/)
    expect(flow.pinBusy).toBe(false)
  })

  it('повторный ввод запрещён — показываем причину с сервера', async () => {
    const { flow, api } = setup()
    api.identify.mockRejectedValueOnce(apiError('update_not_allowed', 403, 'Повторный ввод результатов запрещён.'))
    await enter(flow)
    expect(flow.pinMessage).toBe('Повторный ввод результатов запрещён.')
  })

  it('нет связи при проверке PIN', async () => {
    const { flow, api } = setup()
    api.identify.mockRejectedValueOnce(networkError())
    await enter(flow)
    expect(flow.pinIsError).toBe(true)
    expect(flow.pinMessage).toMatch(/Нет связи/)
  })

  it('ввод закрыли, пока участник набирал PIN', async () => {
    const { flow, api } = setup()
    api.identify.mockRejectedValueOnce(apiError('entry_closed', 403))
    await enter(flow)
    expect(flow.step).toBe('closed')
  })

  it('«Не вы?» возвращает к PIN, а черновик остаётся на телефоне', async () => {
    const { flow, store } = setup()
    await enter(flow)
    flow.toggleTile(0)
    flow.notMe()
    expect(flow.step).toBe('identify')
    expect(flow.who).toBeNull()
    expect(store.data.has(draftKey(EVENT_ID, '1234'))).toBe(true)
  })

  it('уже вводивший видит свои результаты с сервера', async () => {
    const { flow, api, config } = setup()
    const results = emptyResults(config.routes_num)
    results[2] = { top: 2, zone: 0 }
    api.identify.mockResolvedValueOnce(makePayload(config, {
      participant: makeParticipant({ is_entered_result: true }), results,
    }))
    await enter(flow)
    expect(flow.alreadyEntered).toBe(true)
    expect(flow.results[2].top).toBe(2)
  })
})

describe('отметки и черновик', () => {
  it('нажатие на плитку переключает нет → flash → redpoint → нет', async () => {
    const { flow } = setup()
    await enter(flow)
    const tops = []
    for (let i = 0; i < 3; i++) {
      flow.toggleTile(4)
      tops.push(flow.results[4].top)
    }
    expect(tops).toEqual([1, 2, 0])
  })

  it('каждая отметка сразу попадает в черновик', async () => {
    const { flow, store } = setup()
    await enter(flow)
    flow.toggleTile(1)
    const saved = JSON.parse(store.data.get(draftKey(EVENT_ID, '1234'))!)
    expect(saved.v[1]).toEqual({ top: 1, zone: 0 })
    expect(flow.draftSavedAt).toBe(1_700_000_000_000)
  })

  it('черновик возвращается после перезагрузки страницы', async () => {
    const first = setup()
    await enter(first.flow)
    first.flow.toggleTile(0)
    first.flow.toggleTile(3)
    first.flow.toggleTile(3)

    const second = setup({}, { store: first.store })
    await enter(second.flow)
    expect(second.flow.results[0].top).toBe(1)
    expect(second.flow.results[3].top).toBe(2)
    expect(second.flow.restoredAt).toBe(1_700_000_000_000)
  })

  it('«Начать заново» сбрасывает черновик до результатов с сервера', async () => {
    const first = setup()
    await enter(first.flow)
    first.flow.toggleTile(0)
    const second = setup({}, { store: first.store })
    await enter(second.flow)
    second.flow.dropDraft()
    expect(second.flow.results[0].top).toBe(0)
    expect(second.flow.restoredAt).toBeNull()
    expect(second.store.data.has(draftKey(EVENT_ID, '1234'))).toBe(false)
  })

  it('черновик от прежнего числа трасс не подхватывается', async () => {
    const first = setup({ routes_num: 5 })
    await enter(first.flow)
    first.flow.toggleTile(0)
    const second = setup({ routes_num: 10 }, { store: first.store })
    await enter(second.flow)
    expect(second.flow.results).toHaveLength(10)
    expect(second.flow.restoredAt).toBeNull()
  })

  it('работает, даже если браузер не даёт сохранить черновик', async () => {
    const store = memoryStore()
    store.set = () => false
    const { flow } = setup({}, { store })
    await enter(flow)
    flow.toggleTile(0)
    expect(flow.storageOk).toBe(false)
    expect(flow.results[0].top).toBe(1)
  })
})

describe('французская система', () => {
  const french = { score_type: 'FR' }

  it('зона позже топа блокирует отправку', async () => {
    const { flow, api } = setup(french)
    await enter(flow)
    flow.changeAttempt(2, 'top', 1)
    flow.changeAttempt(2, 'zone', 1)
    expect(flow.results[2]).toEqual({ top: 1, zone: 2 })
    expect(flow.invalidRoutes).toEqual([2])
    flow.requestSubmit()
    expect(api.submit).not.toHaveBeenCalled()
    flow.changeAttempt(2, 'zone', -1)
    expect(flow.invalidRoutes).toEqual([])
    flow.requestSubmit()
    await flushPromises()
    expect(api.submit).toHaveBeenCalledWith(EVENT_ID, '1234', expect.any(Array), true)
  })
})

describe('отправка', () => {
  it('успешная отправка: черновик удаляется, участник запоминается, показывается место', async () => {
    const { flow, api, store } = setup({ groups: ['Новички', 'Спорт'] })
    await flow.init()
    const sportsWoman = makeParticipant({ group_index: 1, group: 'Спорт' })
    api.identify.mockResolvedValueOnce(makePayload(makeConfig({ groups: ['Новички', 'Спорт'] }), { participant: sportsWoman }))
    api.submit.mockImplementationOnce(async (_id, _pin, results) => makePayload(makeConfig(), {
      participant: { ...sportsWoman, is_entered_result: true }, results, standing: { place: 3, of: 9 },
    }))
    await flow.identify('1234')
    flow.toggleTile(0)
    flow.requestSubmit()
    await flushPromises()

    expect(api.submit).toHaveBeenCalledWith(EVENT_ID, '1234', expect.arrayContaining([{ top: 1, zone: 0 }]), false)
    expect(flow.step).toBe('done')
    expect(flow.standing).toEqual({ place: 3, of: 9 })
    expect(store.data.has(draftKey(EVENT_ID, '1234'))).toBe(false)
    expect(loadRememberedParticipant(store, EVENT_ID)).toMatchObject({ last_name: 'Зайцева', group_index: 1 })
  })

  it('все «нет» — тоже результат', async () => {
    const { flow, api } = setup()
    await enter(flow)
    flow.requestSubmit()
    await flushPromises()
    expect(api.submit).toHaveBeenCalledOnce()
    expect(flow.step).toBe('done')
  })

  it('с проверкой перед отправкой сначала показывает сводку и ничего не шлёт', async () => {
    const { flow, api } = setup({ is_check_result_before_enter: true })
    await enter(flow)
    flow.toggleTile(0)
    flow.requestSubmit()
    expect(flow.sheetOpen).toBe(true)
    expect(api.submit).not.toHaveBeenCalled()
    flow.closeSheet()
    expect(flow.sheetOpen).toBe(false)
    flow.requestSubmit()
    await flow.send()
    expect(api.submit).toHaveBeenCalledOnce()
    expect(flow.sheetOpen).toBe(false)
    expect(flow.step).toBe('done')
  })

  it('нет связи: результаты остаются в черновике, повторная отправка проходит', async () => {
    const { flow, api, store } = setup()
    await enter(flow)
    flow.toggleTile(0)
    api.submit.mockRejectedValueOnce(networkError())
    flow.requestSubmit()
    await flushPromises()

    expect(flow.step).toBe('entry')
    expect(flow.sending).toBe(false)
    expect(flow.sendError?.isNetwork).toBe(true)
    expect(flow.sendErrorText).toMatch(/сохранены на телефоне/)
    expect(store.data.has(draftKey(EVENT_ID, '1234'))).toBe(true)

    flow.requestSubmit()
    await flushPromises()
    expect(flow.step).toBe('done')
    expect(flow.sendError).toBeNull()
  })

  it('отказ сервера показывает его сообщение', async () => {
    const { flow, api } = setup()
    await enter(flow)
    api.submit.mockRejectedValueOnce(apiError('invalid_results', 400, 'Зона позже топа на трассах: 3.', { routes: [3] }))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.sendErrorText).toBe('Зона позже топа на трассах: 3.')
    expect(flow.step).toBe('entry')
  })

  it('ввод закрыли во время отправки: черновик остаётся', async () => {
    const { flow, api, store } = setup()
    await enter(flow)
    flow.toggleTile(0)
    api.submit.mockRejectedValueOnce(apiError('entry_closed', 403))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.step).toBe('closed')
    expect(store.data.has(draftKey(EVENT_ID, '1234'))).toBe(true)
  })

  it('двойное нажатие не шлёт результаты дважды', async () => {
    const { flow, api } = setup()
    await enter(flow)
    flow.requestSubmit()
    flow.requestSubmit()
    await flushPromises()
    expect(api.submit).toHaveBeenCalledOnce()
  })

  it('«Исправить» возвращает к отметкам с теми же результатами', async () => {
    const { flow } = setup()
    await enter(flow)
    flow.toggleTile(1)
    flow.requestSubmit()
    await flushPromises()
    flow.edit()
    expect(flow.step).toBe('entry')
    expect(flow.results[1].top).toBe(1)
  })
})

describe('ввод без регистрации', () => {
  const config = {
    is_without_registration: true,
    registration_fields: ['gender', 'city', 'birth_year'],
    required_fields: ['birth_year'],
    groups: ['Новички', 'Спорт'],
    sets: [{ index: 0, name: 'Утро', is_full: false }, { index: 1, name: 'Вечер', is_full: false }],
  }

  it('пока анкета не заполнена, ничего не отправляет и говорит, чего не хватает', async () => {
    const { flow, api, scrollToError } = setup(config)
    await flow.init()
    flow.requestSubmit()
    expect(api.submitWithoutRegistration).not.toHaveBeenCalled()
    expect(scrollToError).toHaveBeenCalledOnce()
    expect(flow.showFieldErrors).toBe(true)
    expect(flow.toast).toBe('Заполните фамилию, имя, пол, группу, сет, год рождения.')
    vi.advanceTimersByTime(3000)
    expect(flow.toast).toBe('')
  })

  it('отправляет анкету с индексами группы и сета и только нужными полями', async () => {
    const { flow, api } = setup(config)
    await flow.init()
    flow.setField('last_name', ' Маркова ')
    flow.setField('first_name', 'Мария')
    flow.setField('gender', 'FEMALE')
    flow.setField('group_index', 1)
    flow.setField('set_index', 0)
    flow.setField('birth_year', '1995')
    flow.setField('team', 'не запрашивается событием')
    flow.toggleTile(0)
    flow.requestSubmit()
    await flushPromises()

    expect(api.submitWithoutRegistration).toHaveBeenCalledWith(EVENT_ID, {
      last_name: 'Маркова', first_name: 'Мария', gender: 'FEMALE', group_index: 1, set_index: 0, birth_year: 1995,
    }, expect.any(Array), false)
    expect(flow.step).toBe('done')
    expect(flow.standing).toEqual({ place: 1, of: 1 })
  })

  it('черновик хранит и анкету, и отметки', async () => {
    const first = setup(config)
    await first.flow.init()
    first.flow.setField('last_name', 'Маркова')
    first.flow.setField('group_index', 1)
    first.flow.toggleTile(2)

    const second = setup(config, { store: first.store })
    await second.flow.init()
    expect(second.flow.form.last_name).toBe('Маркова')
    expect(second.flow.form.group_index).toBe(1)
    expect(second.flow.results[2].top).toBe(1)
    expect(second.flow.restoredAt).not.toBeNull()
  })

  it('ошибки полей от сервера подсвечиваются', async () => {
    const { flow, api, scrollToError } = setup({ ...config, required_fields: [] })
    await flow.init()
    for (const [name, value] of [['last_name', 'Маркова'], ['first_name', 'Мария'], ['gender', 'FEMALE']] as const) {
      flow.setField(name, value)
    }
    flow.setField('group_index', 0)
    flow.setField('set_index', 0)
    api.submitWithoutRegistration.mockRejectedValueOnce(
      apiError('invalid_fields', 400, 'Проверьте заполнение анкеты.', { fields: { birth_year: ['Введите целое число.'] } }))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.fieldErrors).toEqual({ birth_year: ['Введите целое число.'] })
    expect(scrollToError).toHaveBeenCalledOnce()
    expect(flow.showFieldErrors).toBe(true)
    expect(flow.sendErrorText).toMatch(/Проверьте анкету/)
    expect(flow.step).toBe('entry')
  })

  it('«мест нет» и другие отказы сервера показываются как есть', async () => {
    const { flow, api } = setup({ ...config, required_fields: [] })
    await flow.init()
    for (const [name, value] of [['last_name', 'Маркова'], ['first_name', 'Мария'], ['gender', 'FEMALE']] as const) {
      flow.setField(name, value)
    }
    flow.setField('group_index', 0)
    flow.setField('set_index', 0)
    api.submitWithoutRegistration.mockRejectedValueOnce(apiError('set_full', 400, 'В выбранном сете нет мест.'))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.sendErrorText).toBe('В выбранном сете нет мест.')
  })
})

describe('повторный ввод запрещён', () => {
  const lockedPayload = (config: EntryConfig, overrides = {}) => makePayload(config, {
    participant: makeParticipant({ is_entered_result: true, group: 'Спорт', group_index: 1 }),
    results: [{ top: 1, zone: 0 }, { top: 0, zone: 0 }, { top: 2, zone: 0 }, ...emptyResults(7)],
    standing: { place: 2, of: 5 },
    locked: true,
    ...overrides,
  })

  it('PIN уже вводившего открывает не ошибку, а его результаты только для просмотра', async () => {
    const { flow, api, config } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config))
    await enter(flow)
    expect(flow.step).toBe('locked')
    expect(flow.pinIsError).toBe(false)
    expect(flow.pinMessage).toBe('')
    expect(flow.standing).toEqual({ place: 2, of: 5 })
    expect(flow.results.map((r) => r.top).slice(0, 3)).toEqual([1, 0, 2])
    expect(flow.who?.last_name).toBe('Зайцева')
  })

  it('черновик не создаётся и не подхватывается, отметки менять нельзя', async () => {
    const { flow, api, config, store } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config))
    await enter(flow)
    flow.toggleTile(1)
    expect(flow.restoredAt).toBeNull()
    expect(flow.step).toBe('locked')
    expect(store.data.has(draftKey(EVENT_ID, '1234'))).toBe(true) // toggleTile по-прежнему пишет, но экран его не показывает
  })

  it('место не показывается, пока результаты скрыты', async () => {
    const { flow, api, config } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config, { standing: null }))
    await enter(flow)
    expect(flow.step).toBe('locked')
    expect(flow.standing).toBeNull()
  })

  it('«Не вы?» возвращает к PIN и убирает место', async () => {
    const { flow, api, config } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config))
    await enter(flow)
    flow.notMe()
    expect(flow.step).toBe('identify')
    expect(flow.standing).toBeNull()
    expect(flow.pinInput).toBe('')
  })

  it('пока участник ничего не вносил, обычная форма, но с предупреждением, что отправить можно один раз', async () => {
    const { flow } = setup({ is_update_result_allowed: false })
    await enter(flow)
    expect(flow.step).toBe('entry')
    expect(flow.updateAllowed).toBe(false)
  })

  it('разрешённый повторный ввод: updateAllowed включён', async () => {
    const { flow } = setup()
    await flow.init()
    expect(flow.updateAllowed).toBe(true)
  })

  it('отказ сервера при отправке по PIN: понятное сообщение с именем', async () => {
    const { flow, api } = setup({ is_update_result_allowed: false })
    await enter(flow)
    flow.toggleTile(0)
    api.submit.mockRejectedValueOnce(apiError('update_not_allowed', 403, 'Повторный ввод результатов запрещён.'))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.step).toBe('entry')
    expect(flow.sendErrorText).toBe(
      'Зайцева Юлия уже вносила результаты. Повторный ввод на этом событии закрыт: исправить может только организатор.')
  })

  it('без регистрации: сервер находит участника по имени и отказывает, сообщение с родом', async () => {
    const { flow, api } = setup({
      is_without_registration: true, is_update_result_allowed: false,
      registration_fields: ['gender'], groups: [], sets: [],
    })
    await flow.init()
    flow.setField('last_name', 'Зайцев')
    flow.setField('first_name', 'Егор')
    flow.setField('gender', 'MALE')
    flow.toggleTile(0)
    api.submitWithoutRegistration.mockRejectedValueOnce(apiError('update_not_allowed', 403))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.sendErrorText).toBe(
      'Зайцев Егор уже вносил результаты. Повторный ввод на этом событии закрыт: исправить может только организатор.')
    expect(flow.sendErrorText).not.toContain('сохранены')
  })

  it('нет связи: результаты остались в браузере, ничего не потеряется', async () => {
    const { flow, api } = setup()
    await enter(flow)
    flow.toggleTile(0)
    api.submit.mockRejectedValueOnce(networkError())
    flow.requestSubmit()
    await flushPromises()
    expect(flow.sendErrorText).toBe('Нет связи с сервером. Результаты сохранены на телефоне, ничего не потеряется.')
  })
})

describe('запоминание участника', () => {
  it('после отправки запись содержит id и сет: по ним страница события берёт статус оплаты и место', async () => {
    const { flow, api, store, config } = setup()
    await flow.init()
    const woman = makeParticipant({ id: 41, set_index: 2, set: 'Вечер', group_index: 1, group: 'Спорт' })
    api.identify.mockResolvedValueOnce(makePayload(config, { participant: woman }))
    await flow.identify('1234')
    flow.toggleTile(0)
    flow.requestSubmit()
    await flushPromises()
    expect(loadRememberedParticipant(store, EVENT_ID)).toEqual({
      id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 0, set_index: 0,
    })
  })

  it('экран ввода пишет в общую запись страницы, а не только в браузер', async () => {
    const store = memoryStore()
    const remembered = createRememberedMe(store, EVENT_ID)
    const config = makeConfig()
    const api = fakeApi(config)
    const flow = useEntryFlow({ eventId: EVENT_ID, api, store, remembered, readHash: () => '', clearHash: () => {} })
    await flow.init()
    await flow.identify('1234')
    flow.toggleTile(0)
    flow.requestSubmit()
    await flushPromises()
    expect(remembered.me.value?.last_name).toBe('Зайцева')
  })
})

describe('ensureInit', () => {
  it('запускает экран один раз: возврат на вкладку не сбрасывает ни PIN, ни отметки', async () => {
    const { flow, api } = setup()
    await flow.ensureInit()
    await flow.identify('1234')
    flow.toggleTile(0)
    await flow.ensureInit()
    expect(api.getConfig).toHaveBeenCalledTimes(1)
    expect(flow.step).toBe('entry')
    expect(flow.results[0].top).toBe(1)
  })
})

describe('повторный ввод запрещён', () => {
  const lockedPayload = (config: EntryConfig, overrides = {}) => makePayload(config, {
    participant: makeParticipant({ is_entered_result: true, group: 'Спорт', group_index: 1 }),
    results: [{ top: 1, zone: 0 }, { top: 0, zone: 0 }, { top: 2, zone: 0 }, ...emptyResults(7)],
    standing: { place: 2, of: 5 },
    locked: true,
    ...overrides,
  })

  it('PIN уже вводившего открывает не ошибку, а его результаты только для просмотра', async () => {
    const { flow, api, config } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config))
    await enter(flow)
    expect(flow.step).toBe('locked')
    expect(flow.pinIsError).toBe(false)
    expect(flow.pinMessage).toBe('')
    expect(flow.standing).toEqual({ place: 2, of: 5 })
    expect(flow.results.map((r) => r.top).slice(0, 3)).toEqual([1, 0, 2])
    expect(flow.who?.last_name).toBe('Зайцева')
  })

  it('место не показывается, пока результаты скрыты', async () => {
    const { flow, api, config } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config, { standing: null }))
    await enter(flow)
    expect(flow.step).toBe('locked')
    expect(flow.standing).toBeNull()
  })

  it('«Не вы?» возвращает к PIN и убирает место', async () => {
    const { flow, api, config } = setup({ is_update_result_allowed: false })
    api.identify.mockResolvedValueOnce(lockedPayload(config))
    await enter(flow)
    flow.notMe()
    expect(flow.step).toBe('identify')
    expect(flow.standing).toBeNull()
    expect(flow.pinInput).toBe('')
  })

  it('пока участник ничего не вносил, обычная форма, но отправить можно один раз', async () => {
    const { flow } = setup({ is_update_result_allowed: false })
    await enter(flow)
    expect(flow.step).toBe('entry')
    expect(flow.updateAllowed).toBe(false)
  })

  it('разрешённый повторный ввод: updateAllowed включён', async () => {
    const { flow } = setup()
    await flow.init()
    expect(flow.updateAllowed).toBe(true)
  })

  it('отказ сервера при отправке по PIN: понятное сообщение с именем', async () => {
    const { flow, api } = setup({ is_update_result_allowed: false })
    await enter(flow)
    flow.toggleTile(0)
    api.submit.mockRejectedValueOnce(apiError('update_not_allowed', 403, 'Повторный ввод результатов запрещён.'))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.step).toBe('entry')
    expect(flow.sendErrorText).toBe(
      'Зайцева Юлия уже вносила результаты. Повторный ввод на этом событии закрыт: исправить может только организатор.')
  })

  it('без регистрации: сервер находит участника по имени и отказывает, сообщение с родом', async () => {
    const { flow, api } = setup({
      is_without_registration: true, is_update_result_allowed: false,
      registration_fields: ['gender'], groups: [], sets: [],
    })
    await flow.init()
    flow.setField('last_name', 'Зайцев')
    flow.setField('first_name', 'Егор')
    flow.setField('gender', 'MALE')
    flow.toggleTile(0)
    api.submitWithoutRegistration.mockRejectedValueOnce(apiError('update_not_allowed', 403))
    flow.requestSubmit()
    await flushPromises()
    expect(flow.sendErrorText).toBe(
      'Зайцев Егор уже вносил результаты. Повторный ввод на этом событии закрыт: исправить может только организатор.')
    expect(flow.sendErrorText).not.toContain('сохранены')
  })

  it('нет связи: результаты остались в браузере, ничего не потеряется', async () => {
    const { flow, api } = setup()
    await enter(flow)
    flow.toggleTile(0)
    api.submit.mockRejectedValueOnce(networkError())
    flow.requestSubmit()
    await flushPromises()
    expect(flow.sendErrorText).toBe('Нет связи с сервером. Результаты сохранены на телефоне, ничего не потеряется.')
  })
})

describe('запоминание участника', () => {
  it('после отправки запись содержит id и сет: по ним страница события берёт статус оплаты и место', async () => {
    const { flow, store } = setup()
    await flow.init()
    await flow.identify('1234')
    flow.toggleTile(0)
    flow.requestSubmit()
    await flushPromises()
    expect(loadRememberedParticipant(store, EVENT_ID)).toEqual({
      id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 0, set_index: 0,
    })
  })

  it('экран ввода пишет в общую запись страницы', async () => {
    const store = memoryStore()
    const remembered = createRememberedMe(store, EVENT_ID)
    const api = fakeApi(makeConfig())
    const flow = useEntryFlow({ eventId: EVENT_ID, api, store, remembered, readHash: () => '', clearHash: () => {} })
    await flow.init()
    await flow.identify('1234')
    flow.toggleTile(0)
    flow.requestSubmit()
    await flushPromises()
    expect(remembered.me.value?.last_name).toBe('Зайцева')
  })
})

describe('ensureInit', () => {
  it('запускает экран один раз: возврат на вкладку не сбрасывает ни PIN, ни отметки', async () => {
    const { flow, api } = setup()
    await flow.ensureInit()
    await flow.identify('1234')
    flow.toggleTile(0)
    await flow.ensureInit()
    expect(api.getConfig).toHaveBeenCalledTimes(1)
    expect(flow.step).toBe('entry')
    expect(flow.results[0].top).toBe(1)
  })
})
