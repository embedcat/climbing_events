// Оплата взноса: ЮMoney (промокод и переход на страницу оплаты) или СБП (ссылка банку и QR-код).
import { computed, reactive, ref } from 'vue'
import type { EventApi, PayInfo } from '../../api/event'
import { asApiError } from '../../api/http'

export type PayStatus = 'idle' | 'loading' | 'ready' | 'paid' | 'unavailable' | 'error'
export type PromoState = 'idle' | 'checking' | 'ok' | 'bad'

export interface PayDeps {
  eventId: number
  api: EventApi
  /** перейти по ссылке (приложение банка); в тестах подменяется */
  openLink?: (url: string) => void
  /** отправить форму на страницу оплаты ЮMoney; в тестах подменяется */
  submitForm?: (action: string, fields: Record<string, string>) => void
  /** участник ушёл платить: страница запоминает, что платёж проверяется */
  onStarted?: (participantId: number) => void
}

export const formatMoney = (value: number): string => value.toLocaleString('ru-RU')

function postForm(action: string, fields: Record<string, string>): void {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = action
  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = name
    input.value = value
    form.appendChild(input)
  }
  document.body.appendChild(form)
  form.submit()
}

export function usePay(deps: PayDeps) {
  const { eventId, api } = deps
  const openLink = deps.openLink ?? ((url: string) => { window.location.assign(url) })
  const submitForm = deps.submitForm ?? postForm

  const participantId = ref<number | null>(null)
  const status = ref<PayStatus>('idle')
  const errorMessage = ref('')
  const info = ref<Exclude<PayInfo, { type: 'paid' }> | null>(null)
  const sending = ref(false)

  const promo = reactive({
    code: '',
    state: 'idle' as PromoState,
    price: null as number | null,
    id: null as number | null,
    message: '',
  })

  const baseAmount = computed(() => info.value?.amount ?? null)
  /** К оплате: с промокодом это новая цена, а не скидка. */
  const amount = computed(() => (promo.state === 'ok' && promo.price !== null ? promo.price : baseAmount.value))

  function resetPromo(): void {
    Object.assign(promo, { code: '', state: 'idle', price: null, id: null, message: '' })
  }

  async function load(id: number): Promise<void> {
    participantId.value = id
    status.value = 'loading'
    info.value = null
    resetPromo()
    try {
      const payload = await api.getPay(eventId, id)
      if (payload.type === 'paid') {
        status.value = 'paid'
        return
      }
      info.value = payload
      status.value = 'ready'
    } catch (e) {
      const error = asApiError(e)
      if (error.code === 'pay_unavailable') {
        status.value = 'unavailable'
      } else {
        errorMessage.value = error.code === 'participant_not_found'
          ? 'Не нашли участника. Откройте оплату из списка участников или по ссылке из письма.'
          : error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : error.message
        status.value = 'error'
      }
    }
  }

  async function applyPromo(): Promise<void> {
    const code = promo.code.trim()
    if (!code) {
      Object.assign(promo, { state: 'bad', price: null, id: null, message: 'Введите промокод.' })
      return
    }
    promo.state = 'checking'
    try {
      const result = await api.checkPromo(eventId, code)
      if (result.valid && typeof result.price === 'number') {
        const was = baseAmount.value
        Object.assign(promo, {
          state: 'ok', price: result.price, id: result.promocode_id ?? null,
          message: `Промокод применён: ${formatMoney(result.price)} ₽${was !== null ? ` вместо ${formatMoney(was)} ₽` : ''}.`,
        })
      } else {
        Object.assign(promo, { state: 'bad', price: null, id: null, message: 'Такого промокода нет. Проверьте, как он написан.' })
      }
    } catch (e) {
      const error = asApiError(e)
      Object.assign(promo, {
        state: 'bad', price: null, id: null,
        message: error.isNetwork ? 'Нет связи с сервером. Попробуйте ещё раз.' : error.message,
      })
    }
  }

  /** ЮMoney: переходим на страницу оплаты формой, как требует сервис. СБП: открываем приложение банка. */
  function start(): void {
    const current = info.value
    if (!current || participantId.value === null || sending.value) return
    if (current.type === 'sbp') {
      openLink(current.link)
      return
    }
    sending.value = true
    // со страницы ЮMoney можно вернуться кнопкой «назад»: кнопка не должна остаться недоступной
    setTimeout(() => { sending.value = false }, 5000)
    deps.onStarted?.(participantId.value)
    const label = promo.state === 'ok' && promo.id !== null ? `${current.label}_c${promo.id}` : current.label
    submitForm(current.action, {
      receiver: current.receiver,
      label,
      'quickpay-form': 'shop',
      sum: String(amount.value ?? current.amount),
      'need-fio': 'false',
      'need-email': 'false',
      'need-phone': 'false',
      'need-address': 'false',
      paymentType: 'AC',
      successURL: current.success_url,
    })
  }

  return reactive({
    participantId, status, errorMessage, info, sending, promo, amount, baseAmount, load, applyPromo, start, resetPromo,
  })
}

export type PayFlow = ReturnType<typeof usePay>
