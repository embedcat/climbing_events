// Страница события для участника: шапка с вкладками, данные события, «Вы» и переходы между экранами.
// Экраны ввода, результатов, участников, регистрации и оплаты живут в своих потоках; здесь они собраны вместе.
import { computed, reactive, ref, watch } from 'vue'
import type { EntryApi, Standing } from '../../api/entry'
import type { EventApi, EventPage, MePayload } from '../../api/event'
import { asApiError } from '../../api/http'
import type { ResultsApi } from '../../api/results'
import { plural } from '../../domain/format'
import { createRememberedMe, type RememberedParticipant } from '../../domain/remember'
import type { KeyValueStore } from '../../domain/storage'
import { useEntryFlow } from '../entry/useEntryFlow'
import { useResultsFlow } from '../results/useResultsFlow'
import { createRouter, TABS, TAB_OF, type GoOptions, type Screen, type Tab } from './router'
import { usePay } from './usePay'
import { usePeople } from './usePeople'
import { useRegistration } from './useRegistration'

export type Status = 'loading' | 'ready' | 'fatal'
export type PayStatus = 'paid' | 'pending' | 'due'

/** Запомненный участник со всем, что про него известно: запись в браузере плюс ответ сервера. */
export interface MeView {
  id: number | null
  reg_type_index: number
  first_name: string
  last_name: string
  gender: string
  group_index: number
  set_index: number | null
  entered: boolean
  paid: boolean
  standing: Standing | null
  /** сервер уже ответил про этого участника: до этого место и оплату не показываем */
  loaded: boolean
}

export interface EventAppDeps {
  eventId: number
  api: EventApi
  entryApi: EntryApi
  resultsApi: ResultsApi
  store: KeyValueStore
  /** адрес управления событием: ссылка для организатора в шапке */
  manageUrl?: string
  win?: Window
  now?: () => number
}

/** Данные страницы живут недолго: этап события меняет организатор, а участники регистрируются. */
const PAGE_MAX_AGE_MS = 10_000
/** Платёж ЮMoney подтверждается за несколько минут: столько ждём подтверждения на экране «Платёж отправлен». */
const PAY_POLL_MS = 5_000
const PAY_POLL_LIMIT_MS = 3 * 60_000
/** «Проверяем платёж» держим, пока не пришло подтверждение, но не вечно. */
const PAY_PENDING_TTL_MS = 6 * 60 * 60_000

/** Заголовок окна у экранов, которые не вкладки. */
const SCREEN_TITLES: Partial<Record<Screen, string>> = {
  reg: 'Регистрация', regdone: 'Вы зарегистрированы', pay: 'Оплата', paydone: 'Оплата',
}

const payKey = (eventId: number): string => `rockevents-pay:v1:${eventId}`

export function useEventApp(deps: EventAppDeps) {
  const { eventId, api, store } = deps
  const win = deps.win ?? window
  const now = deps.now ?? Date.now

  const remembered = createRememberedMe(store, eventId)
  const router = createRouter(eventId, win)

  const status = ref<Status>('loading')
  const fatalMessage = ref('')
  const page = ref<EventPage | null>(null)
  let pageLoadedAt = 0

  const meInfo = ref<MePayload | null>(null)
  const poster = ref(false)
  const toast = ref('')
  let toastTimer: ReturnType<typeof setTimeout> | undefined

  function showToast(message: string): void {
    toast.value = message
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toast.value = '' }, 3000)
  }

  // ---- данные события ----

  async function loadPage(): Promise<void> {
    try {
      page.value = await api.getPage(eventId)
      pageLoadedAt = now()
      status.value = 'ready'
    } catch (e) {
      if (page.value) return
      const error = asApiError(e)
      fatalMessage.value = error.status === 404 ? 'Событие не найдено или не опубликовано.'
        : error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : error.message
      status.value = 'fatal'
    }
  }

  /** Обновляем данные страницы, если они успели устареть. */
  function refreshPage(maxAgeMs = PAGE_MAX_AGE_MS): void {
    if (page.value && now() - pageLoadedAt >= maxAgeMs) void loadPage()
  }

  // ---- «Вы» ----

  const sameName = (a: { last_name: string; first_name: string }, b: { last_name: string; first_name: string }) =>
    a.last_name.trim().toLowerCase() === b.last_name.trim().toLowerCase()
    && a.first_name.trim().toLowerCase() === b.first_name.trim().toLowerCase()

  let meSeq = 0

  /** Статус оплаты и место запомненного участника. Записи, сделанные до страницы события, id не хранят: ищем по имени. */
  async function refreshMe(): Promise<void> {
    const seq = ++meSeq
    const record = remembered.me.value
    if (!record) {
      meInfo.value = null
      return
    }
    try {
      if (record.id === undefined) {
        const found = (await api.getPeople(eventId)).participants
          .find((p) => p.gender === record.gender && sameName(p, record))
        if (!found) {
          remembered.forget()
          return
        }
        // запись дополнилась id: наблюдатель ниже запросит данные участника
        remembered.remember({ ...record, id: found.id, set_index: found.set_index })
        return
      }
      const info = await api.getMe(eventId, record.id)
      if (seq === meSeq) meInfo.value = info
    } catch (e) {
      if (seq === meSeq && asApiError(e).code === 'participant_not_found') {
        remembered.forget()
        meInfo.value = null
      }
    }
  }

  // запомнили другого участника (например, второго ребёнка): данные прежнего больше не подходят
  watch(() => remembered.me.value?.id, () => {
    meInfo.value = null
    void refreshMe()
  })

  const me = computed<MeView | null>(() => {
    const record: RememberedParticipant | null = remembered.me.value
    if (!record) return null
    const loaded = meInfo.value !== null && (record.id === undefined || meInfo.value.participant.id === record.id)
    const info = loaded ? meInfo.value : null
    return {
      id: record.id ?? info?.participant.id ?? null,
      reg_type_index: info?.participant.reg_type_index ?? 0,
      first_name: record.first_name,
      last_name: record.last_name,
      gender: record.gender,
      group_index: info?.participant.group_index ?? record.group_index,
      set_index: info?.participant.set_index ?? record.set_index ?? null,
      entered: info?.participant.is_entered_result ?? false,
      paid: info?.paid ?? false,
      standing: info?.standing ?? null,
      loaded,
    }
  })

  const isMe = (personId: number): boolean => me.value?.id === personId

  function forgetMe(): void {
    remembered.forget()
    meInfo.value = null
  }

  // ---- оплата ----

  const pendingRecord = ref<{ id: number; at: number } | null>(readPending())

  function readPending(): { id: number; at: number } | null {
    try {
      const value = JSON.parse(store.get(payKey(eventId)) ?? 'null')
      return value && typeof value.id === 'number' && typeof value.at === 'number' ? value : null
    } catch {
      return null
    }
  }

  function markPayStarted(participantId: number): void {
    pendingRecord.value = { id: participantId, at: now() }
    store.set(payKey(eventId), JSON.stringify(pendingRecord.value))
  }

  /** Оплачен, платёж проверяется (ушли на страницу ЮMoney, подтверждения ещё нет) или не оплачен. */
  const payStatus = computed<PayStatus>(() => {
    const current = me.value
    if (current?.paid) return 'paid'
    const record = pendingRecord.value
    return current && record && record.id === current.id && now() - record.at < PAY_PENDING_TTL_MS ? 'pending' : 'due'
  })

  watch(() => (meInfo.value ? { id: meInfo.value.participant.id, paid: meInfo.value.paid } : null), (current, previous) => {
    if (!current?.paid) return
    pendingRecord.value = null
    store.remove(payKey(eventId))
    // подтверждение пришло, пока участник смотрел на страницу: тот же участник, раньше был не оплачен
    if (previous && previous.id === current.id && !previous.paid) {
      showToast(page.value?.pay.type === 'sbp' ? 'Организатор подтвердил оплату взноса.' : 'ЮMoney подтвердил оплату взноса.')
    }
  })

  let payPoll: ReturnType<typeof setInterval> | undefined
  function stopPayPoll(): void {
    clearInterval(payPoll)
    payPoll = undefined
  }
  /** Вернулись со страницы оплаты: ждём подтверждения платежа, пока оно не придёт. */
  function startPayPoll(): void {
    stopPayPoll()
    const until = now() + PAY_POLL_LIMIT_MS
    payPoll = setInterval(() => {
      if (me.value?.paid || now() > until) stopPayPoll()
      else void refreshMe()
    }, PAY_POLL_MS)
  }

  // ---- потоки экранов ----

  const people = usePeople({ eventId, api })
  const registration = useRegistration({
    eventId,
    api,
    page: () => page.value,
    remembered,
    toast: showToast,
    onRegistered: () => {
      router.go('regdone')
      void loadPage()
    },
    onStale: () => { void loadPage() },
  })
  const pay = usePay({ eventId, api, onStarted: markPayStarted })
  const entry = useEntryFlow({ eventId, api: deps.entryApi, store, remembered })
  const results = useResultsFlow({ eventId, api: deps.resultsApi, store, remembered, search: win.location.search })

  // ---- экран ----

  const screen = computed<Screen>(() => {
    const current = router.screen.value
    const p = page.value
    if (!p) return current
    if (current === 'regdone' && !registration.result) return 'reg'
    if ((current === 'pay' || current === 'paydone') && !p.pay.is_allowed) return 'info'
    return current
  })
  const tab = computed<Tab>(() => TAB_OF[screen.value])

  function go(next: Screen, options?: GoOptions): void {
    if (next === router.screen.value && !options?.query) return
    router.go(next, options)
  }

  /** Клик по ссылке-вкладке: переходим без перезагрузки, а «открыть в новой вкладке» оставляем браузеру. */
  function navigate(event: MouseEvent, next: Screen, options?: GoOptions): void {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    go(next, options)
  }

  function onScreen(current: Screen): void {
    if (current === 'info') {
      refreshPage()
      void refreshMe()
    } else if (current === 'people') {
      void people.load()
      refreshPage()
    } else if (current === 'reg') {
      // свободные места нужны свежие: сет мог заполниться
      refreshPage(0)
    } else if (current === 'paydone') {
      const id = me.value?.id
      if (id != null && !me.value?.paid) markPayStarted(id)
      void refreshMe()
      startPayPoll()
    } else {
      refreshPage()
    }
    if (current !== 'paydone') stopPayPoll()
    if (typeof document !== 'undefined' && page.value) {
      const label = SCREEN_TITLES[current] ?? TABS.find((t) => t.tab === current)?.label
      document.title = current === 'info' || !label ? page.value.title : `${label} — ${page.value.title}`
    }
  }

  watch(screen, onScreen)

  // событие без регистрации: анкета не нужна, всё в форме ввода результатов
  watch([screen, page], () => {
    if (screen.value === 'reg' && page.value?.is_without_registration) router.go('enter', { replace: true })
  })

  async function init(): Promise<void> {
    status.value = 'loading'
    await loadPage()
    if (!page.value) return
    onScreen(screen.value)
    if (!['info', 'paydone'].includes(screen.value) && remembered.me.value) void refreshMe()
  }

  // ---- производные для экранов ----

  const stage = computed(() => page.value?.stage ?? 'reg')
  const started = computed(() => ['live', 'over', 'done'].includes(stage.value))
  const resultsOpen = computed(() => page.value?.is_results_allowed ?? false)
  /** Регистрация открыта и на неё нужно регистрироваться заранее. */
  const regOpen = computed(() => stage.value === 'reg' && (page.value?.registration.is_open ?? false))
  const canManage = computed(() => page.value?.can_manage ?? false)

  const pluralPlaces = (n: number): string => `${n} ${plural(n, 'место', 'места', 'мест')}`
  /** «свободно 5 мест» при лимите, иначе «до 3 октября, 23:59». */
  const freeText = computed(() => {
    const registration_ = page.value?.registration
    if (!registration_) return ''
    if (registration_.free_places !== null) return `свободно ${pluralPlaces(registration_.free_places)}`
    return registration_.until ? `до ${registration_.until}` : ''
  })

  /** Взнос участника: у типов регистрации своя цена. */
  function priceOf(regTypeIndex: number): number | null {
    const p = page.value
    if (!p || !p.pay.is_allowed) return null
    return p.registration.reg_types.find((t) => t.index === regTypeIndex)?.price ?? p.pay.price
  }

  const groupName = (index: number): string => page.value?.groups[index] ?? ''
  const setName = (index: number | null): string => (index === null ? '' : page.value?.sets[index]?.name ?? '')

  /** «Спорт · Ж · сет 3, 16:00»: что про участника показываем в карточках. */
  function meta(p: { gender: string; group_index: number; set_index: number | null }): string {
    const parts = [groupName(p.group_index), p.gender === 'FEMALE' ? 'Ж' : 'М']
    const set = setName(p.set_index)
    if (set && p.set_index !== null) parts.push(`сет ${p.set_index + 1}, ${set}`)
    return parts.filter(Boolean).join(' · ')
  }

  function dispose(): void {
    router.dispose()
    results.dispose()
    stopPayPoll()
    clearTimeout(toastTimer)
  }

  return reactive({
    eventId, status, fatalMessage, page, screen, tab, me, meInfo, payStatus, poster, toast,
    stage, started, resultsOpen, regOpen, canManage, freeText, manageUrl: deps.manageUrl ?? '',
    people, registration, pay, entry, results, router,
    init, go, navigate, priceOf, loadPage, refreshPage, refreshMe, forgetMe, isMe, markPayStarted, showToast, groupName, setName, meta, dispose,
    rememberPerson: (who: RememberedParticipant) => remembered.remember(who),
    openPoster: () => { poster.value = true },
    closePoster: () => { poster.value = false },
  })
}

export type EventApp = ReturnType<typeof useEventApp>
