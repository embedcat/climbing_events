import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { rememberKey } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import { apiError, clock, EVENT_ID, makeApp, makeMe, makePage, makePerson } from './testing'

const mine = (extra: Record<string, unknown> = {}) => ({
  id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1, set_index: 2, ...extra,
})
const storeWithMe = (record: Record<string, unknown> = mine()) =>
  memoryStore({ [rememberKey(EVENT_ID)]: JSON.stringify(record) })

beforeEach(() => { clock.now = 1_000_000; vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'setTimeout', 'clearTimeout'] }) })
afterEach(() => { vi.useRealTimers() })

describe('запуск', () => {
  it('грузит страницу и показывает экран из адреса', async () => {
    const { app, api } = makeApp({ path: `/e/${EVENT_ID}/participants/` })
    expect(app.status).toBe('loading')
    await app.init()
    expect(api.getPage).toHaveBeenCalledWith(EVENT_ID)
    expect(app.status).toBe('ready')
    expect(app.screen).toBe('people')
    expect(app.tab).toBe('people')
    expect(api.getPeople).toHaveBeenCalled()
    app.dispose()
  })

  it('событие не найдено или нет связи: понятное сообщение и можно повторить', async () => {
    const { app, api } = makeApp()
    api.getPage.mockRejectedValueOnce(apiError('error', 404))
    await app.init()
    expect(app.status).toBe('fatal')
    expect(app.fatalMessage).toBe('Событие не найдено или не опубликовано.')
    api.getPage.mockRejectedValueOnce(apiError('network', 0))
    await app.init()
    expect(app.fatalMessage).toContain('Нет связи')
    await app.init()
    expect(app.status).toBe('ready')
    app.dispose()
  })

  it('этап и производные: регистрация открыта, места, результаты', async () => {
    const { app } = makeApp()
    await app.init()
    expect(app.stage).toBe('reg')
    expect(app.started).toBe(false)
    expect(app.regOpen).toBe(true)
    expect(app.freeText).toBe('свободно 6 мест')
    app.dispose()
  })

  it('без лимита мест в строке — срок регистрации', async () => {
    const page = makePage()
    page.registration.free_places = null
    const { app } = makeApp({ page })
    await app.init()
    expect(app.freeText).toBe('до 3 октября, 23:59')
    app.dispose()
  })

  it('идущее событие: начато, регистрация в нижней панели не предлагается', async () => {
    const { app } = makeApp({ page: makePage({ stage: 'live' }) })
    await app.init()
    expect(app.started).toBe(true)
    expect(app.regOpen).toBe(false)
    app.dispose()
  })
})

describe('экраны', () => {
  it('переход меняет адрес и экран; тот же экран второй раз не добавляет записей в историю', async () => {
    const { app } = makeApp()
    await app.init()
    app.go('results')
    expect(window.location.pathname).toBe('/e/7/results/')
    const length = window.history.length
    app.go('results')
    expect(window.history.length).toBe(length)
    app.dispose()
  })

  it('«готово» после регистрации без самой регистрации открывает анкету', async () => {
    const { app } = makeApp({ path: '/e/7/registration/' })
    await app.init()
    app.go('regdone')
    expect(app.screen).toBe('reg')
    app.dispose()
  })

  it('событие без регистрации: анкета ведёт в ввод результатов', async () => {
    const { app } = makeApp({ page: makePage({ is_without_registration: true }), path: '/e/7/registration/' })
    await app.init()
    await flushPromises()
    expect(app.screen).toBe('enter')
    expect(window.location.pathname).toBe('/e/7/enter/')
    app.dispose()
  })

  it('оплата выключена: экраны оплаты открывают «Инфо»', async () => {
    const { app } = makeApp({ path: '/e/7/pay/' })
    await app.init()
    expect(app.screen).toBe('info')
    app.dispose()
  })

  it('заголовок окна: событие, вкладка, анкета', async () => {
    const { app } = makeApp()
    await app.init()
    expect(document.title).toBe('Осенний фестиваль')
    app.go('people')
    await flushPromises()
    expect(document.title).toBe('Участники — Осенний фестиваль')
    app.go('reg')
    await flushPromises()
    expect(document.title).toBe('Регистрация — Осенний фестиваль')
    app.dispose()
  })

  it('данные страницы обновляются при переходе, но не чаще, чем раз в 10 секунд', async () => {
    const { app, api } = makeApp()
    await app.init()
    app.go('people')
    app.go('results')
    await flushPromises()
    expect(api.getPage).toHaveBeenCalledTimes(1)
    clock.now += 11_000
    app.go('info')
    await flushPromises()
    expect(api.getPage).toHaveBeenCalledTimes(2)
    app.dispose()
  })

  it('перед анкетой данные обновляются всегда: сет мог заполниться', async () => {
    const { app, api } = makeApp()
    await app.init()
    app.go('reg')
    await flushPromises()
    expect(api.getPage).toHaveBeenCalledTimes(2)
    app.dispose()
  })
})

describe('карточка «Вы»', () => {
  it('без записи в браузере её нет и запросов за участником нет', async () => {
    const { app, api } = makeApp()
    await app.init()
    expect(app.me).toBeNull()
    expect(api.getMe).not.toHaveBeenCalled()
    app.dispose()
  })

  it('запомненный участник: данные с сервера, группа и сет подписаны', async () => {
    const { app, api } = makeApp({ store: storeWithMe() })
    api.getMe.mockResolvedValue(makeMe({ paid: true }))
    await app.init()
    await flushPromises()
    expect(api.getMe).toHaveBeenCalledWith(EVENT_ID, 1)
    expect(app.me).toMatchObject({ id: 1, paid: true, entered: false })
    expect(app.meta(app.me!)).toBe('Спорт · Ж · сет 3, 16:00')
    expect(app.isMe(1)).toBe(true)
    expect(app.isMe(2)).toBe(false)
    app.dispose()
  })

  it('участника больше нет на сервере: браузер его забывает', async () => {
    const store = storeWithMe()
    const { app, api } = makeApp({ store })
    api.getMe.mockRejectedValue(apiError('participant_not_found', 404))
    await app.init()
    await flushPromises()
    expect(app.me).toBeNull()
    expect(store.get(rememberKey(EVENT_ID))).toBeNull()
    app.dispose()
  })

  it('нет связи: запись остаётся, карточка показывается без места и оплаты', async () => {
    const { app, api } = makeApp({ store: storeWithMe() })
    api.getMe.mockRejectedValue(apiError('network', 0))
    await app.init()
    await flushPromises()
    expect(app.me?.last_name).toBe('Зайцева')
    expect(app.meInfo).toBeNull()
    app.dispose()
  })

  it('старая запись без id: участника находим в списке по имени и дописываем id', async () => {
    const store = storeWithMe({ first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 })
    const { app, api } = makeApp({ store })
    await app.init()
    await flushPromises()
    expect(api.getPeople).toHaveBeenCalled()
    expect(JSON.parse(store.get(rememberKey(EVENT_ID))!)).toMatchObject({ id: 1, set_index: 2 })
    expect(api.getMe).toHaveBeenCalledWith(EVENT_ID, 1)
    app.dispose()
  })

  it('старая запись, а такого участника в списке нет: забываем', async () => {
    const store = storeWithMe({ first_name: 'Нина', last_name: 'Пропавшая', gender: 'FEMALE', group_index: 0 })
    const { app } = makeApp({ store })
    await app.init()
    await flushPromises()
    expect(app.me).toBeNull()
    expect(store.get(rememberKey(EVENT_ID))).toBeNull()
    app.dispose()
  })

  it('«Не вы?» забывает участника и в браузере тоже', async () => {
    const store = storeWithMe()
    const { app } = makeApp({ store })
    await app.init()
    await flushPromises()
    app.forgetMe()
    expect(app.me).toBeNull()
    expect(store.get(rememberKey(EVENT_ID))).toBeNull()
    app.dispose()
  })

  it('«Это я» в списке запоминает и сразу подтягивает данные', async () => {
    const { app, api } = makeApp()
    await app.init()
    app.rememberPerson({ id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1, set_index: 2 })
    await flushPromises()
    expect(api.getMe).toHaveBeenCalledWith(EVENT_ID, 1)
    expect(app.me?.id).toBe(1)
    app.dispose()
  })

  it('запомнили другого участника (второй ребёнок): данные прежнего не подставляются, пока не пришли новые', async () => {
    const { app, api } = makeApp({ store: storeWithMe() })
    api.getMe.mockResolvedValue(makeMe({ paid: true, standing: { place: 1, of: 3 } }))
    await app.init()
    await flushPromises()
    expect(app.me).toMatchObject({ id: 1, loaded: true, paid: true })

    let finish: (value: ReturnType<typeof makeMe>) => void = () => {}
    api.getMe.mockReturnValueOnce(new Promise((resolve) => { finish = resolve }))
    app.rememberPerson({ id: 2, first_name: 'Пётр', last_name: 'Зайцев', gender: 'MALE', group_index: 0, set_index: 0 })
    await flushPromises()
    expect(app.me).toMatchObject({ id: 2, loaded: false, paid: false, standing: null })

    finish(makeMe({ paid: false, participant: { ...makeMe().participant, id: 2, first_name: 'Пётр', gender: 'MALE', group_index: 0 } }))
    await flushPromises()
    expect(app.me).toMatchObject({ id: 2, loaded: true, paid: false })
    expect(app.toast).toBe('')
    app.dispose()
  })

  it('регистрация запоминает зарегистрированного и открывает «готово»', async () => {
    const { app, api } = makeApp({ path: '/e/7/registration/' })
    await app.init()
    const form = app.registration.form
    Object.assign(form, { last_name: 'Зайцева', first_name: 'Юлия', gender: 'FEMALE', birth_year: '1996', group_index: 1, set_index: 2 })
    expect(await app.registration.submit()).toBe(true)
    await flushPromises()
    expect(app.screen).toBe('regdone')
    expect(app.me?.id).toBe(1)
    expect(api.getPage).toHaveBeenCalledTimes(3)
    app.dispose()
  })
})

describe('оплата взноса', () => {
  const payPage = () => makePage({ pay: { is_allowed: true, type: 'yoomoney', price: 1500 } })

  it('не оплачен, платёж ушёл, оплачен', async () => {
    const { app, api, store } = makeApp({ store: storeWithMe(), page: payPage() })
    api.getMe.mockResolvedValue(makeMe({ paid: false }))
    await app.init()
    await flushPromises()
    expect(app.payStatus).toBe('due')

    app.markPayStarted(1)
    expect(app.payStatus).toBe('pending')
    expect(store.get('rockevents-pay:v1:7')).toContain('"id":1')

    api.getMe.mockResolvedValue(makeMe({ paid: true }))
    await app.refreshMe()
    expect(app.payStatus).toBe('paid')
    expect(app.toast).toBe('ЮMoney подтвердил оплату взноса.')
    expect(store.get('rockevents-pay:v1:7')).toBeNull()
    app.dispose()
  })

  it('«проверяем платёж» не вечно: через шесть часов снова «не оплачен»', async () => {
    const store = storeWithMe()
    const first = makeApp({ store, page: payPage() })
    await first.app.init()
    await flushPromises()
    first.app.markPayStarted(1)
    expect(first.app.payStatus).toBe('pending')
    first.app.dispose()

    clock.now += 6 * 60 * 60_000 + 1
    const second = makeApp({ store, page: payPage() })
    await second.app.init()
    await flushPromises()
    expect(second.app.payStatus).toBe('due')
    second.app.dispose()
  })

  it('платёж другого участника не считается платежом этого', async () => {
    const { app, api } = makeApp({ store: storeWithMe(), page: payPage() })
    api.getMe.mockResolvedValue(makeMe())
    await app.init()
    await flushPromises()
    app.markPayStarted(555)
    expect(app.payStatus).toBe('due')
    app.dispose()
  })

  it('«Платёж отправлен»: ждём подтверждения раз в 5 секунд и перестаём, когда оплата пришла', async () => {
    const { app, api } = makeApp({ store: storeWithMe(), page: payPage(), path: '/e/7/pay/done/' })
    api.getMe.mockResolvedValue(makeMe({ paid: false }))
    await app.init()
    await flushPromises()
    expect(app.screen).toBe('paydone')
    expect(app.payStatus).toBe('pending')
    const calls = api.getMe.mock.calls.length

    await vi.advanceTimersByTimeAsync(5_000)
    expect(api.getMe.mock.calls.length).toBe(calls + 1)

    api.getMe.mockResolvedValue(makeMe({ paid: true }))
    await vi.advanceTimersByTimeAsync(5_000)
    expect(app.payStatus).toBe('paid')
    const after = api.getMe.mock.calls.length
    await vi.advanceTimersByTimeAsync(20_000)
    expect(api.getMe.mock.calls.length).toBe(after)
    app.dispose()
  })

  it('цена: у типа регистрации своя, иначе общая', async () => {
    const page = payPage()
    page.registration.reg_types = [{ index: 0, name: 'А', price: 1500 }, { index: 1, name: 'Б', price: 2000 }]
    const { app } = makeApp({ page })
    await app.init()
    expect(app.priceOf(1)).toBe(2000)
    expect(app.priceOf(7)).toBe(1500)
    app.dispose()
  })

  it('без онлайн-оплаты цены нет', async () => {
    const { app } = makeApp()
    await app.init()
    expect(app.priceOf(0)).toBeNull()
    app.dispose()
  })
})

describe('список участников', () => {
  it('загружается при открытии вкладки; «Это я» по участнику из списка', async () => {
    const { app, api } = makeApp({ people: [makePerson('Иванов', 'Иван', { id: 9 })] })
    await app.init()
    app.go('people')
    await flushPromises()
    expect(api.getPeople).toHaveBeenCalledTimes(1)
    expect(app.people.people).toHaveLength(1)
    app.people.openPerson(9)
    expect(app.people.sheet?.last_name).toBe('Иванов')
    app.people.closeSheet()
    expect(app.people.sheet).toBeNull()
    app.dispose()
  })

  it('«Найти в списке» после ошибки регистрации ставит поиск и сбрасывает фильтры', async () => {
    const { app } = makeApp()
    await app.init()
    app.people.setGender('FEMALE')
    app.people.toggleSet(1)
    app.people.search('Зайцева')
    expect(app.people.filters).toEqual({ gender: 'all', group: -1, set: -1, q: 'Зайцева' })
    app.people.toggleSet(1)
    app.people.toggleSet(1)
    expect(app.people.filters.set).toBe(-1)
    app.dispose()
  })

  it('нет связи: ошибка с возможностью повторить, а прежний список остаётся', async () => {
    const { app, api } = makeApp()
    await app.init()
    api.getPeople.mockRejectedValueOnce(apiError('network', 0))
    await app.people.load()
    expect(app.people.status).toBe('error')
    expect(app.people.errorMessage).toContain('Нет связи')
    await app.people.load()
    expect(app.people.status).toBe('ready')
    api.getPeople.mockRejectedValueOnce(apiError('network', 0))
    await app.people.load()
    expect(app.people.status).toBe('ready')
    expect(app.people.people).toHaveLength(4)
    app.dispose()
  })
})
