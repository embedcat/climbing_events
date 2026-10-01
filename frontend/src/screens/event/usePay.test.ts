import { describe, expect, it, vi } from 'vitest'
import { apiError, fakeEventApi } from './testing'
import { usePay } from './usePay'

function setup() {
  const api = fakeEventApi()
  const openLink = vi.fn()
  const submitForm = vi.fn()
  const onStarted = vi.fn()
  const flow = usePay({ eventId: 7, api, openLink, submitForm, onStarted })
  return { flow, api, openLink, submitForm, onStarted }
}

describe('загрузка', () => {
  it('ЮMoney: сумма из ответа сервера', async () => {
    const { flow, api } = setup()
    await flow.load(1)
    expect(api.getPay).toHaveBeenCalledWith(7, 1)
    expect(flow.status).toBe('ready')
    expect(flow.amount).toBe(1500)
  })

  it('взнос уже оплачен', async () => {
    const { flow, api } = setup()
    api.getPay.mockResolvedValueOnce({ type: 'paid' })
    await flow.load(1)
    expect(flow.status).toBe('paid')
    expect(flow.info).toBeNull()
  })

  it('оплата недоступна и участник не найден — разные сообщения', async () => {
    const a = setup()
    a.api.getPay.mockRejectedValueOnce(apiError('pay_unavailable', 403))
    await a.flow.load(1)
    expect(a.flow.status).toBe('unavailable')

    const b = setup()
    b.api.getPay.mockRejectedValueOnce(apiError('participant_not_found', 404))
    await b.flow.load(99)
    expect(b.flow.status).toBe('error')
    expect(b.flow.errorMessage).toContain('Не нашли участника')
  })

  it('нет связи', async () => {
    const { flow, api } = setup()
    api.getPay.mockRejectedValueOnce(apiError('network', 0))
    await flow.load(1)
    expect(flow.status).toBe('error')
    expect(flow.errorMessage).toContain('Нет связи')
  })
})

describe('промокод', () => {
  it('новая цена вместо прежней, сообщение с обеими', async () => {
    const { flow, api } = setup()
    await flow.load(1)
    api.checkPromo.mockResolvedValueOnce({ valid: true, price: 1200, promocode_id: 5 })
    flow.promo.code = ' LESNAYA '
    await flow.applyPromo()
    expect(api.checkPromo).toHaveBeenCalledWith(7, 'LESNAYA')
    expect(flow.promo.state).toBe('ok')
    expect(flow.amount).toBe(1200)
    expect(flow.baseAmount).toBe(1500)
    expect(flow.promo.message.replace(/\s/g, ' ')).toBe('Промокод применён: 1 200 ₽ вместо 1 500 ₽.')
  })

  it('неверный промокод возвращает прежнюю цену', async () => {
    const { flow, api } = setup()
    await flow.load(1)
    api.checkPromo.mockResolvedValueOnce({ valid: true, price: 1200, promocode_id: 5 })
    flow.promo.code = 'A'
    await flow.applyPromo()
    api.checkPromo.mockResolvedValueOnce({ valid: false })
    flow.promo.code = 'B'
    await flow.applyPromo()
    expect(flow.promo.state).toBe('bad')
    expect(flow.amount).toBe(1500)
    expect(flow.promo.message).toBe('Такого промокода нет. Проверьте, как он написан.')
  })

  it('пустой промокод не проверяем', async () => {
    const { flow, api } = setup()
    await flow.load(1)
    flow.promo.code = '  '
    await flow.applyPromo()
    expect(api.checkPromo).not.toHaveBeenCalled()
    expect(flow.promo.message).toBe('Введите промокод.')
  })

  it('нет связи при проверке: сообщение, цена прежняя', async () => {
    const { flow, api } = setup()
    await flow.load(1)
    api.checkPromo.mockRejectedValueOnce(apiError('network', 0))
    flow.promo.code = 'A'
    await flow.applyPromo()
    expect(flow.promo.state).toBe('bad')
    expect(flow.promo.message).toContain('Нет связи')
  })

  it('при новой загрузке промокод сбрасывается', async () => {
    const { flow, api } = setup()
    await flow.load(1)
    api.checkPromo.mockResolvedValueOnce({ valid: true, price: 1200, promocode_id: 5 })
    flow.promo.code = 'A'
    await flow.applyPromo()
    await flow.load(1)
    expect(flow.promo.state).toBe('idle')
    expect(flow.amount).toBe(1500)
  })
})

describe('переход к оплате', () => {
  it('ЮMoney: форма с суммой, меткой участника и адресом возврата; страница помнит, что платёж ушёл', async () => {
    const { flow, submitForm, onStarted } = setup()
    await flow.load(1)
    flow.start()
    expect(onStarted).toHaveBeenCalledWith(1)
    const [action, fields] = submitForm.mock.calls[0]
    expect(action).toBe('https://yoomoney.ru/quickpay/confirm.xml')
    expect(fields).toMatchObject({
      receiver: '4100', label: 'e7_p1', sum: '1500', 'quickpay-form': 'shop', paymentType: 'AC',
      successURL: 'http://x/e/7/pay/done/',
    })
  })

  it('с промокодом в метке номер промокода, а в сумме новая цена', async () => {
    const { flow, api, submitForm } = setup()
    await flow.load(1)
    api.checkPromo.mockResolvedValueOnce({ valid: true, price: 1200, promocode_id: 5 })
    flow.promo.code = 'LESNAYA'
    await flow.applyPromo()
    flow.start()
    expect(submitForm.mock.calls[0][1]).toMatchObject({ label: 'e7_p1_c5', sum: '1200' })
  })

  it('СБП: открывает ссылку банка и ничего не отправляет', async () => {
    const { flow, api, openLink, submitForm, onStarted } = setup()
    api.getPay.mockResolvedValueOnce({ type: 'sbp', amount: 1500, link: 'https://qr.nspk.ru/X', qr: 'data:image/svg+xml,x' })
    await flow.load(1)
    flow.start()
    expect(openLink).toHaveBeenCalledWith('https://qr.nspk.ru/X')
    expect(submitForm).not.toHaveBeenCalled()
    expect(onStarted).not.toHaveBeenCalled()
  })

  it('без загруженных данных кнопка ничего не делает', () => {
    const { flow, submitForm } = setup()
    flow.start()
    expect(submitForm).not.toHaveBeenCalled()
  })
})
