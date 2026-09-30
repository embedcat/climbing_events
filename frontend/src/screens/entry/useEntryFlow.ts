// Логика экрана ввода результатов участником: кто вводит, что отмечено, черновик, отправка.
// Компоненты только рисуют состояние, которое отсюда отдаётся.
import { computed, nextTick, reactive, ref } from 'vue'
import {
  isFrench,
  type EntryApi, type EntryConfig, type EntryPayload, type PublicParticipant, type Standing,
} from '../../api/entry'
import { asApiError } from '../../api/http'
import { clearDraft, draftKey, loadDraft, saveDraft } from '../../domain/draft'
import { readPinFromHash } from '../../domain/link'
import { rememberParticipant } from '../../domain/remember'
import {
  cloneResults, cycleTile, emptyResults, invalidFrenchRoutes, stepAttempt, summarize,
  type AttemptKind, type RouteResult,
} from '../../domain/results'
import type { KeyValueStore } from '../../domain/storage'
import {
  emptyForm, missingFields, pickForm, toRegistrationPayload, type RegistrationForm,
} from './registration'

export type Step = 'loading' | 'fatal' | 'closed' | 'identify' | 'entry' | 'done'

export interface FlowDeps {
  eventId: number
  api: EntryApi
  store: KeyValueStore
  /** location.hash страницы; подменяется в тестах */
  readHash?: () => string
  /** убрать PIN из адресной строки */
  clearHash?: () => void
  /** прокрутить к первому неверно заполненному полю анкеты */
  scrollToError?: () => void
  now?: () => number
}

export function useEntryFlow(deps: FlowDeps) {
  const { eventId, api, store } = deps
  const now = deps.now ?? Date.now
  const readHash = deps.readHash ?? (() => window.location.hash)
  const clearHash = deps.clearHash ?? (() => {
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
  })
  const scrollToError = deps.scrollToError ?? (() => {
    void nextTick(() => document.querySelector('.re-fld.is-invalid')
      ?.scrollIntoView?.({ behavior: 'smooth', block: 'center' }))
  })

  const step = ref<Step>('loading')
  const config = ref<EntryConfig | null>(null)
  const fatalMessage = ref('')

  // кто вводит
  const pinInput = ref('')
  const pin = ref('')
  const pinBusy = ref(false)
  const pinMessage = ref('')
  const pinIsError = ref(false)
  const who = ref<PublicParticipant | null>(null)
  const form = reactive<RegistrationForm>(emptyForm())
  const showFieldErrors = ref(false)
  const fieldErrors = ref<Record<string, string[]>>({})

  // результаты и черновик
  const results = ref<RouteResult[]>([])
  const serverResults = ref<RouteResult[]>([])
  const restoredAt = ref<number | null>(null)
  const draftSavedAt = ref<number | null>(null)
  const storageOk = ref(true)

  // отправка
  const sending = ref(false)
  const sendError = ref<ReturnType<typeof asApiError> | null>(null)
  const sheetOpen = ref(false)
  const submitted = ref<PublicParticipant | null>(null)
  const standing = ref<Standing | null>(null)

  const toast = ref('')
  let toastTimer: ReturnType<typeof setTimeout> | undefined

  const french = computed(() => (config.value ? isFrench(config.value) : false))
  const withoutRegistration = computed(() => config.value?.is_without_registration ?? false)
  const invalidRoutes = computed(() => (french.value ? invalidFrenchRoutes(results.value) : []))
  const summary = computed(() => summarize(results.value, french.value))
  const missing = computed(() => (config.value && withoutRegistration.value ? missingFields(config.value, form) : []))
  const alreadyEntered = computed(() => who.value?.is_entered_result ?? false)

  /** Что показываем про вводящего: из ответа сервера по PIN или из анкеты. */
  const currentWho = computed(() => {
    const c = config.value
    if (!c) return null
    if (who.value) return who.value
    return {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      gender: form.gender || 'MALE',
      group_index: Math.max(form.group_index, 0),
      group: form.group_index >= 0 ? c.groups[form.group_index] ?? '' : '',
      set_index: Math.max(form.set_index, 0),
      set: form.set_index >= 0 ? c.sets[form.set_index]?.name ?? '' : '',
      is_entered_result: false,
    } satisfies PublicParticipant
  })

  const sendErrorText = computed(() => {
    const error = sendError.value
    if (!error) return ''
    if (error.code === 'invalid_fields') return 'Проверьте анкету: одно из полей заполнено неверно.'
    const saved = ' Результаты сохранены на телефоне, ничего не потеряется.'
    return error.isNetwork || error.status >= 500 || error.code === 'unknown' ? error.message + saved : error.message
  })

  function showToast(message: string): void {
    toast.value = message
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toast.value = '' }, 2600)
  }

  // ---- черновик ----

  const currentDraftKey = () => draftKey(eventId, withoutRegistration.value ? 'wo' : pin.value)

  function persist(): void {
    const ok = saveDraft(store, currentDraftKey(), {
      results: results.value,
      fields: withoutRegistration.value ? { ...form } : null,
      savedAt: now(),
    })
    storageOk.value = ok
    if (ok) draftSavedAt.value = now()
  }

  /** Результаты с сервера, а если на телефоне остался черновик, то он. quiet — не показывать плашку про черновик. */
  function applyDraft(quiet: boolean): void {
    const c = config.value!
    results.value = cloneResults(serverResults.value)
    restoredAt.value = null
    draftSavedAt.value = null
    const draft = loadDraft(store, currentDraftKey(), c.routes_num, french.value, c.max_attempts)
    if (!draft) return
    results.value = draft.results
    if (withoutRegistration.value && draft.fields) Object.assign(form, pickForm(draft.fields))
    draftSavedAt.value = draft.savedAt
    if (!quiet) restoredAt.value = draft.savedAt
  }

  function openEntry(quiet: boolean): void {
    step.value = 'entry'
    sendError.value = null
    sheetOpen.value = false
    showFieldErrors.value = false
    fieldErrors.value = {}
    standing.value = null
    applyDraft(quiet)
  }

  // ---- запуск и вход по PIN ----

  async function identify(value: string): Promise<void> {
    const digits = value.replace(/\D/g, '').slice(0, 4)
    pinInput.value = digits
    pinIsError.value = false
    pinMessage.value = ''
    if (digits.length < 4) return
    pinBusy.value = true
    pinMessage.value = 'Ищу участника…'
    try {
      const payload = await api.identify(eventId, digits)
      pin.value = digits
      who.value = payload.participant
      serverResults.value = cloneResults(payload.results)
      pinMessage.value = ''
      openEntry(false)
    } catch (e) {
      const error = asApiError(e)
      if (error.code === 'entry_closed') {
        step.value = 'closed'
        return
      }
      pinIsError.value = true
      pinMessage.value = error.code === 'pin_not_found'
        ? `Участник с PIN ${digits} не найден. Проверьте карточку или спросите организатора.`
        : error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и введите PIN ещё раз.' : error.message
    } finally {
      pinBusy.value = false
    }
  }

  async function init(): Promise<void> {
    step.value = 'loading'
    fatalMessage.value = ''
    try {
      config.value = await api.getConfig(eventId)
    } catch (e) {
      const error = asApiError(e)
      fatalMessage.value = error.status === 404 ? 'Событие не найдено или не опубликовано.'
        : error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : error.message
      step.value = 'fatal'
      return
    }
    const c = config.value
    if (!c.is_enter_result_allowed) {
      step.value = 'closed'
      return
    }
    if (c.is_without_registration) {
      serverResults.value = emptyResults(c.routes_num)
      openEntry(false)
      return
    }
    step.value = 'identify'
    const hashPin = readPinFromHash(readHash())
    if (hashPin) {
      clearHash()
      await identify(hashPin)
    }
  }

  function notMe(): void {
    who.value = null
    pin.value = ''
    pinInput.value = ''
    pinMessage.value = ''
    pinIsError.value = false
    sheetOpen.value = false
    step.value = 'identify'
  }

  // ---- отметки ----

  function toggleTile(index: number): void {
    results.value[index] = cycleTile(results.value[index])
    persist()
  }

  function changeAttempt(index: number, kind: AttemptKind, delta: number): void {
    results.value[index] = stepAttempt(results.value[index], kind, delta, config.value!.max_attempts)
    persist()
  }

  function setField<K extends keyof RegistrationForm>(name: K, value: RegistrationForm[K]): void {
    form[name] = value
    persist()
  }

  function dropDraft(): void {
    clearDraft(store, currentDraftKey())
    results.value = cloneResults(serverResults.value)
    restoredAt.value = null
    draftSavedAt.value = null
  }

  // ---- отправка ----

  async function send(): Promise<void> {
    const c = config.value
    if (!c || sending.value) return
    sheetOpen.value = false
    sending.value = true
    sendError.value = null
    try {
      const payload: EntryPayload = withoutRegistration.value
        ? await api.submitWithoutRegistration(eventId, toRegistrationPayload(c, form), results.value, french.value)
        : await api.submit(eventId, pin.value, results.value, french.value)
      clearDraft(store, currentDraftKey())
      serverResults.value = cloneResults(payload.results)
      submitted.value = payload.participant
      standing.value = payload.standing ?? null
      rememberParticipant(store, eventId, payload.participant)
      restoredAt.value = null
      draftSavedAt.value = null
      step.value = 'done'
    } catch (e) {
      const error = asApiError(e)
      if (error.code === 'entry_closed') {
        step.value = 'closed'
        return
      }
      if (error.code === 'invalid_fields') {
        fieldErrors.value = (error.body.fields ?? {}) as Record<string, string[]>
        showFieldErrors.value = true
        scrollToError()
      }
      sendError.value = error
    } finally {
      sending.value = false
    }
  }

  /** Кнопка «Отправить»: проверяем на телефоне, при включённой проверке показываем сводку, иначе сразу шлём. */
  function requestSubmit(): void {
    const c = config.value
    if (!c || sending.value || invalidRoutes.value.length) return
    if (missing.value.length) {
      showFieldErrors.value = true
      showToast(`Заполните ${missing.value.join(', ')}.`)
      scrollToError()
      return
    }
    if (c.is_check_result_before_enter) {
      sheetOpen.value = true
      return
    }
    void send()
  }

  /** «Исправить» на экране после отправки. */
  function edit(): void {
    step.value = 'entry'
    sendError.value = null
    sheetOpen.value = false
  }

  // reactive разворачивает ref'ы: компоненты читают flow.step, а не flow.step.value
  return reactive({
    step, config, fatalMessage, french, withoutRegistration,
    pinInput, pin, pinBusy, pinMessage, pinIsError, who, form, showFieldErrors, fieldErrors,
    results, restoredAt, draftSavedAt, storageOk, alreadyEntered,
    sending, sendError, sendErrorText, sheetOpen, submitted, standing, currentWho,
    invalidRoutes, summary, missing, toast,
    init, identify, notMe, toggleTile, changeAttempt, setField, dropDraft, requestSubmit, send, edit,
    closeSheet: () => { sheetOpen.value = false },
    showToast,
  })
}

export type EntryFlow = ReturnType<typeof useEntryFlow>
