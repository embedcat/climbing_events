import { describe, expect, it, vi } from 'vitest'
import type { EventPage } from '../../api/event'
import { createRememberedMe } from '../../domain/remember'
import { memoryStore } from '../../domain/storage'
import { apiError, fakeEventApi, makePage, makeRegistered } from './testing'
import { isValidBirthYear, useRegistration } from './useRegistration'

function setup(pageOverrides: Partial<EventPage> = {}) {
  const page = makePage(pageOverrides)
  const api = fakeEventApi(page)
  const store = memoryStore()
  const remembered = createRememberedMe(store, 7)
  const toast = vi.fn()
  const onRegistered = vi.fn()
  const onStale = vi.fn()
  const flow = useRegistration({
    eventId: 7, api, page: () => page, remembered, toast, onRegistered, onStale, year: () => 2026, scrollToError: () => {},
  })
  return { flow, api, store, remembered, toast, onRegistered, onStale, page }
}

/** Заполняет всё, что требует событие по умолчанию из makePage. */
function fill(flow: ReturnType<typeof setup>['flow'], overrides: Record<string, unknown> = {}) {
  flow.setField('last_name', 'Зайцева')
  flow.setField('first_name', 'Юлия')
  flow.setField('gender', 'FEMALE')
  flow.setField('birth_year', '1996')
  flow.setField('group_index', 1)
  flow.setField('set_index', 2)
  for (const [key, value] of Object.entries(overrides)) flow.setField(key as 'city', value as string)
}

describe('год рождения', () => {
  it('четыре цифры, не раньше 1930 и не позже текущего года', () => {
    expect(isValidBirthYear('1996', 2026)).toBe(true)
    expect(isValidBirthYear(' 2026 ', 2026)).toBe(true)
    for (const bad of ['', '96', '19960', '2027', '1929', 'abcd']) expect(isValidBirthYear(bad, 2026)).toBe(false)
  })
})

describe('проверка анкеты на телефоне', () => {
  it('пустая анкета: перечень того, что заполнить', () => {
    const { flow } = setup()
    expect(flow.missing).toEqual(['фамилию', 'имя', 'пол', 'группу', 'сет', 'год рождения'])
  })

  it('год рождения обязателен по настройке события и должен быть годом', () => {
    const { flow } = setup()
    fill(flow, { birth_year: '' })
    expect(flow.missing).toEqual(['год рождения'])
    flow.setField('birth_year', '199')
    expect(flow.badBirthYear).toBe(true)
    expect(flow.missing).toEqual(['год рождения'])
    flow.setField('birth_year', '1996')
    expect(flow.missing).toEqual([])
  })

  it('необязательный год рождения можно не указывать, но неверный не пропускаем', () => {
    const { flow } = setup({ registration: { ...makePage().registration, required_fields: [] } })
    fill(flow, { birth_year: '' })
    expect(flow.missing).toEqual([])
    flow.setField('birth_year', '19')
    expect(flow.missing).toEqual(['год рождения'])
  })

  it('тип участия нужен, если у события есть типы регистрации', () => {
    const { flow } = setup({
      registration: { ...makePage().registration, reg_types: [{ index: 0, name: 'Участник', price: 1500 }, { index: 1, name: '+ футболка', price: 2000 }] },
    })
    fill(flow)
    expect(flow.missing).toEqual(['тип участия'])
    flow.setField('reg_type_index', 1)
    expect(flow.missing).toEqual([])
  })

  it('событие без групп и сетов их не требует', () => {
    const { flow } = setup({ groups: [], sets: [] })
    flow.setField('last_name', 'Зайцева')
    flow.setField('first_name', 'Юлия')
    flow.setField('gender', 'FEMALE')
    flow.setField('birth_year', '1996')
    expect(flow.missing).toEqual([])
  })

  it('отправка с пустыми полями: подсказка, подсветка и ни одного запроса', async () => {
    const { flow, api, toast } = setup()
    expect(await flow.submit()).toBe(false)
    expect(flow.showErrors).toBe(true)
    expect(toast).toHaveBeenCalledWith('Заполните фамилию, имя, пол, группу, сет, год рождения.')
    expect(api.register).not.toHaveBeenCalled()
  })
})

describe('отправка', () => {
  it('отправляет только поля, которые просит событие, и запоминает участника', async () => {
    const { flow, api, remembered, onRegistered } = setup()
    fill(flow, { city: ' Москва ', email: 'yulia@example.com' })
    expect(await flow.submit()).toBe(true)

    expect(api.register).toHaveBeenCalledWith(7, {
      last_name: 'Зайцева', first_name: 'Юлия', gender: 'FEMALE', group_index: 1, set_index: 2,
      birth_year: 1996, city: 'Москва', email: 'yulia@example.com', grade: 'BR',
    })
    expect(flow.result?.pin).toBe(8335)
    expect(flow.result?.email).toBe('yulia@example.com')
    expect(remembered.me.value).toEqual({
      id: 1, first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1, set_index: 2,
    })
    expect(onRegistered).toHaveBeenCalledOnce()
  })

  it('тип регистрации уходит индексом', async () => {
    const { flow, api } = setup({
      registration: { ...makePage().registration, reg_types: [{ index: 0, name: 'А', price: null }, { index: 1, name: 'Б', price: null }] },
    })
    fill(flow, { reg_type_index: 1 })
    await flow.submit()
    expect(api.register.mock.calls[0][1].reg_type_index).toBe(1)
  })

  it('пока идёт запрос, повторная отправка игнорируется', async () => {
    const { flow, api } = setup()
    fill(flow)
    const first = flow.submit()
    expect(flow.sending).toBe(true)
    expect(await flow.submit()).toBe(false)
    await first
    expect(api.register).toHaveBeenCalledOnce()
    expect(flow.sending).toBe(false)
  })

  it('после успеха анкета очищена: «назад» с экрана «готово» не вернёт заполненную форму', async () => {
    const { flow } = setup()
    fill(flow, { city: 'Москва' })
    await flow.submit()
    expect(flow.result).not.toBeNull()
    expect(flow.form.last_name).toBe('')
    expect(flow.form.set_index).toBe(-1)
    expect(flow.form.city).toBe('Москва')
    expect(flow.showErrors).toBe(false)
  })

  it('«ещё одного»: город и команда остаются, остальное и результат сбрасываются', async () => {
    const { flow } = setup()
    fill(flow, { city: 'Москва', team: 'Магнезия' })
    await flow.submit()
    flow.registerAnother()
    expect(flow.result).toBeNull()
    expect(flow.form.last_name).toBe('')
    expect(flow.form.set_index).toBe(-1)
    expect(flow.form.city).toBe('Москва')
    expect(flow.form.team).toBe('Магнезия')
    expect(flow.form.grade).toBe('BR')
  })
})

describe('ошибки сервера объясняем по-человечески', () => {
  async function failWith(code: string, status: number, body: Record<string, unknown> = {}) {
    const ctx = setup()
    fill(ctx.flow)
    ctx.api.register.mockRejectedValueOnce(apiError(code, status, 'текст сервера', body))
    expect(await ctx.flow.submit()).toBe(false)
    expect(ctx.onRegistered).not.toHaveBeenCalled()
    expect(ctx.remembered.me.value).toBeNull()
    return ctx
  }

  it('такой участник уже есть: имя и фамилия для поиска в списке', async () => {
    const { flow } = await failWith('duplicate', 409)
    expect(flow.formError).toEqual({ kind: 'duplicate', name: 'Зайцева Юлия', last: 'Зайцева' })
  })

  it('младше допустимого: самый поздний подходящий год рождения', async () => {
    const { flow } = await failWith('too_young', 400, { min_age: 14 })
    expect(flow.formError).toEqual({ kind: 'too_young', year: 2012 })
  })

  it('сет заполнился: выбор сбрасывается, данные страницы обновляются', async () => {
    const { flow, onStale } = await failWith('set_full', 400)
    expect(flow.formError).toEqual({ kind: 'set_full', setNumber: 3 })
    expect(flow.form.set_index).toBe(-1)
    expect(onStale).toHaveBeenCalledOnce()
  })

  it('выбор другого сета убирает сообщение про заполненный', async () => {
    const { flow } = await failWith('set_full', 400)
    flow.setField('set_index', 0)
    expect(flow.formError).toBeNull()
  })

  it('регистрация закрыта', async () => {
    const { flow, onStale } = await failWith('registration_closed', 403)
    expect(flow.formError).toEqual({ kind: 'closed' })
    expect(onStale).toHaveBeenCalled()
  })

  it('поля, которые не понравились серверу, подсвечиваются', async () => {
    const { flow } = await failWith('invalid_fields', 400, { fields: { email: ['Введите правильный адрес.'] } })
    expect(flow.fieldErrors.email).toEqual(['Введите правильный адрес.'])
    expect(flow.showErrors).toBe(true)
  })

  it('нет связи: сообщение, анкета остаётся заполненной', async () => {
    const { flow } = await failWith('network', 0)
    expect(flow.formError).toEqual({ kind: 'other', message: 'текст сервера' })
    expect(flow.form.last_name).toBe('Зайцева')
  })

  it('после ошибки можно отправить ещё раз', async () => {
    const { flow, api } = await failWith('duplicate', 409)
    api.register.mockResolvedValueOnce(makeRegistered())
    expect(await flow.submit()).toBe(true)
    expect(flow.formError).toBeNull()
  })
})
