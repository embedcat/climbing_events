// Регистрация участника: анкета, проверка на телефоне, отправка и понятные ошибки сервера.
import { computed, nextTick, reactive, ref } from 'vue'
import type { RegistrationPayload } from '../../api/entry'
import type { EventApi, EventPage, RegistrationResult } from '../../api/event'
import { asApiError } from '../../api/http'
import type { RememberedMe } from '../../domain/remember'
import {
  emptyForm, missingFields, toRegistrationPayload, type RegistrationConfig, type RegistrationForm,
} from '../entry/registration'

export interface RegistrationFormEx extends RegistrationForm {
  /** -1 — не выбран; поле есть только у событий с типами регистрации */
  reg_type_index: number
}

export type FormError =
  | { kind: 'duplicate'; name: string; last: string }
  | { kind: 'too_young'; year: number }
  | { kind: 'set_full'; setNumber: number }
  | { kind: 'closed' }
  | { kind: 'not_needed' }
  | { kind: 'other'; message: string }

export interface Registered extends RegistrationResult {
  /** email из анкеты: на него ушло письмо */
  email: string
}

export interface RegistrationDeps {
  eventId: number
  api: EventApi
  page: () => EventPage | null
  remembered: RememberedMe
  /** участник зарегистрирован: страница показывает экран с PIN и обновляет свободные места */
  onRegistered?: () => void
  /** сервер сказал, что сет заполнился или регистрация закрыта: данные страницы устарели */
  onStale?: () => void
  toast?: (message: string) => void
  year?: () => number
  /** прокрутить к первому неверно заполненному полю */
  scrollToError?: () => void
}

export const newForm = (keep: Partial<Pick<RegistrationForm, 'city' | 'team'>> = {}): RegistrationFormEx => ({
  ...emptyForm(), grade: 'BR', reg_type_index: -1, ...keep,
})

/** Год рождения как в анкете: четыре цифры, не раньше 1930 и не позже текущего. */
export function isValidBirthYear(value: string, thisYear: number): boolean {
  if (!/^\d{4}$/.test(value.trim())) return false
  const year = Number(value)
  return year >= 1930 && year <= thisYear
}

export function useRegistration(deps: RegistrationDeps) {
  const { eventId, api, remembered } = deps
  const year = deps.year ?? (() => new Date().getFullYear())
  const scrollToError = deps.scrollToError ?? (() => {
    void nextTick(() => document.querySelector('.re-fld.is-invalid')?.scrollIntoView?.({ behavior: 'smooth', block: 'center' }))
  })

  const form = reactive<RegistrationFormEx>(newForm())
  const showErrors = ref(false)
  const formError = ref<FormError | null>(null)
  const fieldErrors = ref<Record<string, string[]>>({})
  const sending = ref(false)
  const result = ref<Registered | null>(null)

  /** Настройки события для анкеты; без загруженной страницы пустые. */
  const config = computed<RegistrationConfig & { reg_types: number }>(() => {
    const page = deps.page()
    return {
      registration_fields: page?.registration.fields ?? [],
      required_fields: page?.registration.required_fields ?? [],
      groups: page?.groups ?? [],
      sets: page?.sets ?? [],
      reg_types: page?.registration.reg_types.length ?? 0,
    }
  })

  const badBirthYear = computed(() => {
    const value = form.birth_year.trim()
    return config.value.registration_fields.includes('birth_year') && value !== '' && !isValidBirthYear(value, year())
  })

  /** Что ещё надо заполнить, в винительном падеже. */
  const missing = computed(() => {
    const list = missingFields(config.value, form)
    if (badBirthYear.value && !list.includes('год рождения')) list.push('год рождения')
    if (config.value.reg_types && form.reg_type_index < 0) list.push('тип участия')
    return list
  })

  const setFull = (index: number): boolean => deps.page()?.sets.find((s) => s.index === index)?.is_full ?? false

  function setField<K extends keyof RegistrationFormEx>(name: K, value: RegistrationFormEx[K]): void {
    form[name] = value
    if (name === 'set_index' && formError.value?.kind === 'set_full') formError.value = null
  }

  /** Новая анкета; для «Зарегистрировать ещё одного»: город и команда остаются, родители записывают детей подряд. */
  function reset(keep: Partial<Pick<RegistrationForm, 'city' | 'team'>> = {}): void {
    Object.assign(form, newForm(keep))
    showErrors.value = false
    formError.value = null
    fieldErrors.value = {}
    result.value = null
  }

  function registerAnother(): void {
    reset({ city: form.city, team: form.team })
  }

  function explain(error: ReturnType<typeof asApiError>): void {
    const last = form.last_name.trim()
    const first = form.first_name.trim()
    switch (error.code) {
      case 'duplicate':
        formError.value = { kind: 'duplicate', name: `${last} ${first}`, last }
        break
      case 'too_young': {
        const minAge = Number(error.body.min_age) || deps.page()?.registration.min_age || 0
        formError.value = { kind: 'too_young', year: year() - minAge }
        break
      }
      case 'set_full':
        formError.value = { kind: 'set_full', setNumber: form.set_index + 1 }
        form.set_index = -1
        deps.onStale?.()
        break
      case 'registration_closed':
        formError.value = { kind: 'closed' }
        deps.onStale?.()
        break
      case 'registration_not_needed':
        formError.value = { kind: 'not_needed' }
        deps.onStale?.()
        break
      case 'invalid_fields':
        fieldErrors.value = (error.body.fields ?? {}) as Record<string, string[]>
        showErrors.value = true
        formError.value = { kind: 'other', message: 'Проверьте анкету: одно из полей заполнено неверно.' }
        scrollToError()
        break
      default:
        formError.value = { kind: 'other', message: error.message }
    }
  }

  async function submit(): Promise<boolean> {
    if (sending.value) return false
    if (missing.value.length) {
      showErrors.value = true
      formError.value = null
      deps.toast?.(`Заполните ${missing.value.join(', ')}.`)
      scrollToError()
      return false
    }
    sending.value = true
    formError.value = null
    try {
      const payload: RegistrationPayload = toRegistrationPayload(config.value, form)
      if (config.value.reg_types) payload.reg_type_index = form.reg_type_index
      const registered = await api.register(eventId, payload)
      result.value = { ...registered, email: form.email.trim() }
      remembered.remember(registered.participant)
      // кнопка «назад» с экрана «готово» не должна вернуть заполненную анкету: второй раз она не пройдёт
      Object.assign(form, newForm({ city: form.city, team: form.team }))
      showErrors.value = false
      deps.onRegistered?.()
      return true
    } catch (e) {
      explain(asApiError(e))
      return false
    } finally {
      sending.value = false
    }
  }

  return reactive({
    form, showErrors, formError, fieldErrors, sending, result, missing, badBirthYear, config,
    setFull, setField, reset, registerAnother, submit,
  })
}

export type RegistrationFlow = ReturnType<typeof useRegistration>
