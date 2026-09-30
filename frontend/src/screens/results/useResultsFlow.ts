// Логика экрана результатов: загрузка, автообновление, выбор таблицы, «это я», подсветка сдвигов.
// Компоненты только рисуют состояние, которое отсюда отдаётся.
import { computed, reactive, ref } from 'vue'
import type { Gender } from '../../api/entry'
import { asApiError } from '../../api/http'
import type { ResultRow, ResultsApi, ResultsPayload, ResultsTable } from '../../api/results'
import { loadRememberedParticipant, rememberParticipant } from '../../domain/remember'
import type { KeyValueStore } from '../../domain/storage'
import {
  allRows, changeMessage, diffResults, findRemembered, findRow, findTable, formatAgo,
  type ResultsDiff,
} from '../../domain/standings'

export type Status = 'loading' | 'ready' | 'closed' | 'fatal'

/** Пока событие идёт, открытая таблица обновляется раз в 30 секунд. */
export const LIVE_INTERVAL_MS = 30_000
/** Монитор события на экране зала (`?autorefresh`) обновляется чаще и всегда. */
export const MONITOR_INTERVAL_MS = 10_000
/** Сколько подсвечиваем сдвиги мест после обновления. */
export const HIGHLIGHT_MS = 12_000
const CLOCK_TICK_MS = 5_000

export interface ResultsFlowDeps {
  eventId: number
  api: ResultsApi
  store: KeyValueStore
  /** location.search: `?autorefresh&m` и `?autorefresh&f` — ссылки монитора события для зала */
  search?: string
  isHidden?: () => boolean
  now?: () => number
}

export function useResultsFlow(deps: ResultsFlowDeps) {
  const { eventId, api, store } = deps
  const now = deps.now ?? Date.now
  const isHidden = deps.isHidden ?? (() => typeof document !== 'undefined' && document.hidden)
  const params = new URLSearchParams(deps.search ?? '')
  const monitor = params.has('autorefresh')

  const status = ref<Status>('loading')
  const fatalMessage = ref('')
  const payload = ref<ResultsPayload | null>(null)
  let lastJson = ''

  const gender = ref<Gender>('MALE')
  const groupIndex = ref(0)
  const sheetId = ref<number | null>(null)
  /** Запомненный на телефоне участник; строку в таблице ищем по имени, потому что id могут смениться. */
  const remembered = ref(loadRememberedParticipant(store, eventId))
  const meRowVisible = ref(true)
  /** Просьба прокрутить таблицу к строке; seq нужен, чтобы повторная просьба тоже срабатывала. */
  const focusRow = ref<{ id: number; seq: number } | null>(null)

  const refreshing = ref(false)
  const refreshFailed = ref(false)
  const lastUpdate = ref(now())
  const clock = ref(now())

  const deltas = reactive(new Map<number, number>())
  const changed = reactive(new Set<number>())
  const toast = ref('')
  let toastTimer: ReturnType<typeof setTimeout> | undefined
  let highlightTimer: ReturnType<typeof setTimeout> | undefined
  let tickTimer: ReturnType<typeof setInterval> | undefined
  let focusSeq = 0

  // ---- производные ----

  const table = computed<ResultsTable | null>(() =>
    payload.value ? findTable(payload.value, gender.value, groupIndex.value) : null)
  const isLive = computed(() => payload.value?.event.is_live ?? false)
  const french = computed(() => payload.value?.event.score_type === 'FR')
  const pollInterval = computed(() => (monitor ? MONITOR_INTERVAL_MS : isLive.value ? LIVE_INTERVAL_MS : 0))
  const agoText = computed(() => formatAgo(Math.max(0, (clock.value - lastUpdate.value) / 1000)))

  const meId = computed(() => (payload.value ? findRemembered(payload.value, remembered.value) : null))
  const me = computed(() => (payload.value && meId.value !== null ? findRow(payload.value, meId.value) : null))
  const meInCurrentTable = computed(() => me.value?.table === table.value)
  const sheet = computed(() => (payload.value && sheetId.value !== null ? findRow(payload.value, sheetId.value) : null))

  /** Сколько участников в каждой группе выбранного пола: подписи на чипах. */
  const groupCounts = computed(() => {
    const p = payload.value
    if (!p) return []
    return p.tables.filter((t) => t.gender === gender.value).map((t) => allRows(t).length)
  })
  const hasGroups = computed(() => (payload.value?.groups.length ?? 0) > 1)
  const myGroupIndex = computed(() => (me.value && me.value.table.gender === gender.value ? me.value.table.group_index : -1))

  // ---- загрузка и обновление ----

  function showToast(message: string): void {
    toast.value = message
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toast.value = '' }, 3200)
  }

  function clearHighlights(): void {
    deltas.clear()
    changed.clear()
  }

  function applyDiff(diff: ResultsDiff): void {
    deltas.clear()
    changed.clear()
    diff.deltas.forEach((value, id) => deltas.set(id, value))
    diff.changed.forEach((id) => changed.add(id))
    clearTimeout(highlightTimer)
    highlightTimer = setTimeout(clearHighlights, HIGHLIGHT_MS)
    const message = changeMessage(diff.events, (e) => e.gender === gender.value && e.groupIndex === groupIndex.value)
    if (message) showToast(message)
  }

  /** Первый показ: пол из ссылки монитора (`&m`, `&f`), иначе группа запомненного участника, иначе первая непустая таблица. */
  function chooseInitialTable(next: ResultsPayload): void {
    const fromLink: Gender | null = params.has('f') ? 'FEMALE' : params.has('m') ? 'MALE' : null
    if (fromLink) {
      gender.value = fromLink
      groupIndex.value = 0
      return
    }
    const mine = findRemembered(next, remembered.value)
    const found = mine !== null ? findRow(next, mine) : null
    if (found) {
      gender.value = found.table.gender
      groupIndex.value = found.table.group_index
      return
    }
    const firstNonEmpty = next.tables.find((t) => allRows(t).length > 0)
    gender.value = firstNonEmpty?.gender ?? 'MALE'
    groupIndex.value = firstNonEmpty?.group_index ?? 0
  }

  function apply(next: ResultsPayload): void {
    const json = JSON.stringify(next)
    const first = payload.value === null
    if (!first && json !== lastJson) applyDiff(diffResults(payload.value!, next))
    if (json !== lastJson) payload.value = next
    lastJson = json
    if (first) chooseInitialTable(next)
    // группы могли измениться в настройках события
    const groups = Math.max(next.groups.length, 1)
    if (groupIndex.value >= groups) groupIndex.value = 0
    lastUpdate.value = now()
    clock.value = lastUpdate.value
    refreshFailed.value = false
  }

  async function refresh(): Promise<void> {
    if (refreshing.value) return
    refreshing.value = true
    try {
      apply(await api.getResults(eventId))
      if (status.value === 'loading') status.value = 'ready'
    } catch (e) {
      const error = asApiError(e)
      if (error.code === 'results_closed') {
        status.value = 'closed'
      } else if (payload.value) {
        refreshFailed.value = true
      } else {
        fatalMessage.value = error.status === 404 ? 'Событие не найдено или не опубликовано.'
          : error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : error.message
        status.value = 'fatal'
      }
    } finally {
      refreshing.value = false
    }
  }

  /** Обновляем сами, если экран на виду, карточка участника не открыта и подошёл срок. */
  function tick(): void {
    clock.value = now()
    const interval = pollInterval.value
    if (!interval || isHidden() || sheetId.value !== null) return
    if (clock.value - lastUpdate.value >= interval) void refresh()
  }

  async function init(): Promise<void> {
    status.value = 'loading'
    await refresh()
    if (tickTimer === undefined) tickTimer = setInterval(tick, CLOCK_TICK_MS)
  }

  /** Вкладка снова на виду: если данные успели устареть, обновляем сразу, не дожидаясь таймера. */
  function wake(): void {
    tick()
  }

  function dispose(): void {
    clearInterval(tickTimer)
    clearTimeout(toastTimer)
    clearTimeout(highlightTimer)
    tickTimer = undefined
  }

  // ---- выбор и карточка ----

  function selectGender(value: Gender): void {
    gender.value = value
  }

  function selectGroup(index: number): void {
    groupIndex.value = index
  }

  function openPerson(id: number): void {
    sheetId.value = id
  }

  function closeSheet(): void {
    sheetId.value = null
    wake()
  }

  function rememberPerson(row: ResultRow): void {
    const who = {
      first_name: row.first_name,
      last_name: row.last_name,
      gender: row.gender,
      group_index: payload.value ? findRow(payload.value, row.id)?.table.group_index ?? 0 : 0,
    }
    rememberParticipant(store, eventId, who)
    remembered.value = who
    sheetId.value = null
    showToast('Запомнили. В следующий раз сразу откроется ваша группа.')
  }

  /** Показать запомненного участника: открыть его группу и прокрутить к строке. */
  function goToMe(): void {
    const found = me.value
    if (!found) return
    gender.value = found.table.gender
    groupIndex.value = found.table.group_index
    focusRow.value = { id: found.row.id, seq: ++focusSeq }
  }

  return reactive({
    status, fatalMessage, payload, table, isLive, french, monitor, agoText, refreshing, refreshFailed, lastUpdate,
    gender, groupIndex, groupCounts, hasGroups, myGroupIndex,
    sheetId, sheet, meId, me, meInCurrentTable, meRowVisible, focusRow,
    deltas, changed, toast,
    init, refresh, wake, dispose, selectGender, selectGroup, openPerson, closeSheet, rememberPerson, goToMe,
    setMeRowVisible: (visible: boolean) => { meRowVisible.value = visible },
    showToast,
  })
}

export type ResultsFlow = ReturnType<typeof useResultsFlow>
