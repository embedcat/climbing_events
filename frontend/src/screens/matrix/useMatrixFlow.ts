// Состояние экрана массового ввода: строки под фильтром, курсор, черновик, поиск, сохранение.
// Одно состояние на два вида: матрица на ноутбуке и шаги на телефоне. Компоненты только рисуют его.
import { computed, reactive, ref } from 'vue'
import { asApiError, type ApiError } from '../../api/http'
import type { MatrixApi, MatrixParticipant, MatrixPayload } from '../../api/matrix'
import {
  advanceCursor, cellKey, cellValue, defaultFilters, draftStats, draftToChanges, filtersShowing, fixCursor,
  invalidCells, isVisible, restoreDraft, rowHasDraft, searchParticipants, setDraftValue, stepCursor, visibleRows,
  type Cursor, type Direction, type Draft, type Filters,
} from '../../domain/matrix'
import type { KeyAction } from '../../domain/matrixKeys'
import { plural } from '../../domain/format'
import { cycleTile, stepAttempt, type AttemptKind, type RouteResult } from '../../domain/results'
import type { KeyValueStore } from '../../domain/storage'

export type Status = 'loading' | 'ready' | 'fatal' | 'forbidden'
export type PhoneMode = 'participant' | 'route'

const DRAFT_KEY = (eventId: number) => `rockevents-matrix-draft:v1:${eventId}`
const DIRECTION_KEY = 'rockevents-matrix-dir'
const HINT_MS = 4500
const DELTA_MS = 8000

export interface MatrixFlowDeps {
  eventId: number
  api: MatrixApi
  store: KeyValueStore
  /** location.hash: `#p=12` открывает участника с этим id (ссылка из результатов) */
  hash?: string
}

export function useMatrixFlow(deps: MatrixFlowDeps) {
  const { eventId, api, store } = deps

  const status = ref<Status>('loading')
  const fatalMessage = ref('')
  const payload = ref<MatrixPayload | null>(null)

  const filters = reactive<Filters>(defaultFilters())
  const direction = ref<Direction>(store.get(DIRECTION_KEY) === 'down' ? 'down' : 'right')
  const draft: Draft = reactive(new Map()) as Draft
  const cursor = ref<Cursor | null>(null)
  /** Французская система: цифры, набранные в ячейке и ещё не записанные (Enter записывает). */
  const edit = ref<string | null>(null)

  const searchQuery = ref('')
  const searchActive = ref(0)
  /** Просьба перевести фокус в поле поиска; seq нужен, чтобы повторная просьба тоже срабатывала. */
  const searchFocus = ref(0)
  const gridFocus = ref(0)

  const saving = ref(false)
  const saveError = ref<ApiError | null>(null)
  const errorTarget = ref<{ pid: number; r: number } | null>(null)
  const savedMessage = ref('')
  const restoredCount = ref(0)
  const storageOk = ref(true)
  const hint = ref('')
  const flash = ref<{ pid: number; seq: number } | null>(null)
  const deltas = reactive(new Map<number, number>())
  const refreshing = ref(false)

  const phone = reactive({ mode: 'participant' as PhoneMode, pid: null as number | null, route: 0 })

  let hintTimer: ReturnType<typeof setTimeout> | undefined
  let deltaTimer: ReturnType<typeof setTimeout> | undefined
  let flashSeq = 0

  // ---- производные ----

  const event = computed(() => payload.value?.event ?? null)
  const participants = computed<MatrixParticipant[]>(() => payload.value?.participants ?? [])
  const french = computed(() => event.value?.score_type === 'FR')
  const routes = computed(() => event.value?.routes_num ?? 0)
  const hasSets = computed(() => (event.value?.sets.length ?? 0) > 1)
  const hasGroups = computed(() => (event.value?.groups.length ?? 0) > 1)
  const scope = computed(() => visibleRows(participants.value, filters))
  const rows = computed(() => scope.value.rows)
  const missingCount = computed(() => scope.value.missingCount)
  const stats = computed(() => draftStats(draft))
  const invalid = computed(() => invalidCells(draft, french.value))
  const canSave = computed(() => stats.value.cells > 0 && invalid.value.length === 0 && !saving.value)
  const byId = computed(() => new Map(participants.value.map((p) => [p.id, p])))
  const current = computed(() => (cursor.value ? byId.value.get(cursor.value.pid) ?? null : null))

  /** Сколько пролазов на каждой трассе среди показанных строк, с учётом несохранённого. */
  const routeCounts = computed(() => {
    const counts = Array<number>(routes.value).fill(0)
    for (const p of rows.value) {
      for (let r = 0; r < routes.value; r++) {
        const v = cellValue(p, r, draft)
        if (v.top > 0) counts[r]++
      }
    }
    return counts
  })

  const searchResults = computed(() => {
    const shown = new Set(rows.value.map((p) => p.id))
    return searchParticipants(participants.value, searchQuery.value, (p) => shown.has(p.id))
  })

  const phoneParticipant = computed(() => (phone.pid !== null ? byId.value.get(phone.pid) ?? null : null))

  // ---- подсказки и подсветка ----

  function showHint(message: string): void {
    hint.value = message
    clearTimeout(hintTimer)
    if (message) hintTimer = setTimeout(() => { hint.value = '' }, HINT_MS)
  }

  function flashRow(pid: number): void {
    flash.value = { pid, seq: ++flashSeq }
  }

  // ---- черновик ----

  function persist(): void {
    storageOk.value = store.set(DRAFT_KEY(eventId), JSON.stringify([...draft]))
  }

  function touched(): void {
    savedMessage.value = ''
    persist()
  }

  function setValue(p: MatrixParticipant, route: number, value: RouteResult): void {
    setDraftValue(draft, p, route, value, french.value)
    touched()
  }

  const valueAt = (p: MatrixParticipant, route: number): RouteResult => cellValue(p, route, draft)
  const isDirty = (pid: number, route: number): boolean => draft.has(cellKey(pid, route))
  const rowDirty = (pid: number): boolean => rowHasDraft(draft, pid, routes.value)

  /** Нажатие на ячейку без разбора системы: нет → flash → redpoint → нет. */
  function cycleCell(p: MatrixParticipant, route: number): void {
    setValue(p, route, cycleTile(valueAt(p, route)))
  }

  function setTop(p: MatrixParticipant, route: number, top: number): void {
    setValue(p, route, { top, zone: 0 })
  }

  function stepCell(p: MatrixParticipant, route: number, kind: AttemptKind, delta: number): void {
    setValue(p, route, stepAttempt(valueAt(p, route), kind, delta, event.value!.max_attempts))
  }

  /** Французская система: записываем набранное число в текущую ячейку (топ или зона). */
  function setAttempt(p: MatrixParticipant, route: number, sub: 0 | 1, n: number): void {
    const v = { ...valueAt(p, route) }
    if (sub === 0) v.top = n
    else v.zone = n
    if (v.top > 0 && v.zone === 0) v.zone = v.top // как форма: топ без зоны → зона на той же попытке
    setValue(p, route, v)
  }

  function commitEdit(): void {
    if (edit.value === null || !cursor.value || !current.value) return
    const n = edit.value === '' ? 0 : Math.min(parseInt(edit.value, 10), event.value!.max_attempts)
    edit.value = null
    setAttempt(current.value, cursor.value.r, cursor.value.sub, n)
  }

  function cancelEdit(): void {
    edit.value = null
  }

  // ---- курсор ----

  function moveTo(next: Cursor): void {
    cursor.value = next
  }

  function step(dRow: number, dCol: number): void {
    if (!cursor.value || !rows.value.length) return
    moveTo(stepCursor(rows.value, cursor.value, dRow, dCol, routes.value, french.value))
  }

  function advance(): void {
    if (!cursor.value || !rows.value.length) return
    const next = advanceCursor(rows.value, cursor.value, direction.value, routes.value, french.value)
    moveTo(next.cursor)
    if (next.jumpedTo !== null) flashRow(next.jumpedTo)
    if (next.hint) showHint(next.hint)
  }

  function clickCell(pid: number, route: number, sub: 0 | 1): void {
    const p = byId.value.get(pid)
    if (!p) return
    const c = cursor.value
    const onCursor = !!c && c.pid === pid && c.r === route && c.sub === sub
    commitEdit()
    if (onCursor && !french.value) cycleCell(p, route)
    else moveTo({ pid, r: route, sub })
    gridFocus.value++
  }

  function clickParticipant(pid: number): void {
    commitEdit()
    moveTo({ pid, r: 0, sub: 0 })
    gridFocus.value++
  }

  /** К участнику поиском, из ссылки или по кнопке «перейти». Если он отфильтрован, переключаем фильтры. */
  function goTo(p: MatrixParticipant, route = 0, sub: 0 | 1 = 0): void {
    commitEdit()
    if (!isVisible(p, filters)) Object.assign(filters, filtersShowing(p, hasSets.value))
    moveTo({ pid: p.id, r: route, sub })
    flashRow(p.id)
    gridFocus.value++
  }

  function fixAfterFilterChange(): void {
    cursor.value = fixCursor(rows.value, cursor.value, routes.value, french.value)
  }

  function setFilter<K extends keyof Filters>(name: K, value: Filters[K]): void {
    commitEdit()
    filters[name] = value
    fixAfterFilterChange()
  }

  function setDirection(value: Direction): void {
    direction.value = value
    store.set(DIRECTION_KEY, value)
    gridFocus.value++
  }

  // ---- клавиатура ----

  function applyKey(action: KeyAction): void {
    const c = cursor.value
    const p = current.value
    if (action.type === 'search') {
      cancelEdit()
      searchFocus.value++
      return
    }
    if (!c || !p) return
    switch (action.type) {
      case 'move':
        commitEdit()
        step(action.dRow, action.dCol)
        return
      case 'home':
        commitEdit()
        moveTo({ pid: c.pid, r: 0, sub: 0 })
        return
      case 'end':
        commitEdit()
        moveTo({ pid: c.pid, r: routes.value - 1, sub: french.value ? 1 : 0 })
        return
      default:
        break
    }
    if (!french.value) {
      switch (action.type) {
        case 'digit':
          if (action.digit <= 2) {
            setTop(p, c.r, action.digit)
            advance()
          } else {
            showHint('В этой системе: 1 — flash, 2 — redpoint, 0 — нет.')
          }
          return
        case 'backspace':
        case 'delete':
          setTop(p, c.r, 0)
          return
        case 'space':
          cycleCell(p, c.r)
          return
        case 'enter':
          step(1, 0)
          return
        default:
          return
      }
    }
    switch (action.type) {
      case 'digit':
        edit.value = ((edit.value ?? '') + action.digit).replace(/^0+(?=\d)/, '').slice(0, 2)
        return
      case 'backspace':
        if (edit.value !== null) edit.value = edit.value.slice(0, -1)
        else setAttempt(p, c.r, c.sub, 0)
        return
      case 'delete':
        edit.value = null
        setAttempt(p, c.r, c.sub, 0)
        return
      case 'escape':
        cancelEdit()
        return
      case 'enter':
      case 'space':
        commitEdit()
        advance()
        return
      default:
    }
  }

  // ---- поиск ----

  function setSearch(query: string): void {
    searchQuery.value = query
    searchActive.value = 0
  }

  function moveSearch(delta: number): void {
    const last = searchResults.value.length - 1
    searchActive.value = Math.max(0, Math.min(last, searchActive.value + delta))
  }

  function pickSearch(p: MatrixParticipant | undefined = searchResults.value[searchActive.value]): void {
    if (!p) return
    searchQuery.value = ''
    goTo(p)
  }

  // ---- загрузка и сохранение ----

  /** Набор, с которого начинаем: где есть участники без результата, чаще всего идёт ввод. */
  function chooseInitialSet(data: MatrixPayload): number {
    if (data.event.sets.length < 2) return -1
    const firstDraft = [...draft.keys()][0]
    if (firstDraft !== undefined) {
      const p = data.participants.find((x) => x.id === Number(firstDraft.split(':')[0]))
      if (p) return p.set_index
    }
    const missing = new Map<number, number>()
    for (const p of data.participants) if (!p.is_entered_result) missing.set(p.set_index, (missing.get(p.set_index) ?? 0) + 1)
    let best = -1
    let bestCount = 0
    for (const s of data.event.sets) {
      const n = missing.get(s.index) ?? 0
      if (n > bestCount) { best = s.index; bestCount = n }
    }
    return best
  }

  function restoreFromBrowser(data: MatrixPayload): void {
    let raw: unknown = null
    try {
      const text = store.get(DRAFT_KEY(eventId))
      raw = text ? JSON.parse(text) : null
    } catch {
      raw = null
    }
    const restored = restoreDraft(raw, data.participants, data.event.routes_num, data.event.score_type === 'FR', data.event.max_attempts)
    draft.clear()
    restored.forEach((value, key) => draft.set(key, value))
    restoredCount.value = draft.size
    if (draft.size !== (Array.isArray(raw) ? raw.length : 0)) persist()
  }

  function applyDeepLink(hash: string): void {
    const match = /(?:^#|&)p=(\d+)(?:&|$)/.exec(hash)
    const p = match ? byId.value.get(Number(match[1])) : undefined
    if (!p) return
    goTo(p)
    phone.pid = p.id
  }

  async function init(): Promise<void> {
    status.value = 'loading'
    let data: MatrixPayload
    try {
      data = await api.getMatrix(eventId)
    } catch (e) {
      const error = asApiError(e)
      if (error.status === 401 || error.status === 403) {
        status.value = 'forbidden'
      } else {
        fatalMessage.value = error.status === 404 ? 'Событие не найдено.'
          : error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : error.message
        status.value = 'fatal'
      }
      return
    }
    payload.value = data
    restoreFromBrowser(data)
    Object.assign(filters, defaultFilters(), { set: chooseInitialSet(data) })
    cursor.value = fixCursor(rows.value, null, data.event.routes_num, data.event.score_type === 'FR')
    const lastDraft = [...draft.keys()].pop()
    if (lastDraft !== undefined && cursor.value) {
      const [pid, r] = lastDraft.split(':').map(Number)
      if (rows.value.some((p) => p.id === pid)) cursor.value = { pid, r: Math.min(r + 1, data.event.routes_num - 1), sub: 0 }
    }
    status.value = 'ready'
    if (deps.hash) applyDeepLink(deps.hash)
  }

  /** Свежие данные с сервера: участники могли ввести результаты сами. Черновик и курсор сохраняются. */
  async function refresh(): Promise<void> {
    if (refreshing.value || saving.value) return
    refreshing.value = true
    try {
      const data = await api.getMatrix(eventId)
      payload.value = data
      const restored = restoreDraft([...draft], data.participants, data.event.routes_num, french.value, data.event.max_attempts)
      draft.clear()
      restored.forEach((value, key) => draft.set(key, value))
      persist()
      fixAfterFilterChange()
      saveError.value = null
      showHint('Данные обновлены.')
    } catch (e) {
      saveError.value = asApiError(e)
      errorTarget.value = null
    } finally {
      refreshing.value = false
    }
  }

  async function save(): Promise<void> {
    commitEdit()
    if (saving.value || !draft.size) return
    if (invalid.value.length) {
      showHint('Сначала исправьте трассы, где зона позже топа.')
      return
    }
    saving.value = true
    saveError.value = null
    errorTarget.value = null
    const sent = new Map(draft)
    const before = new Map(participants.value.map((p) => [p.id, p.place]))
    try {
      const result = await api.save(eventId, draftToChanges(draft, french.value))
      payload.value = { event: result.event, participants: result.participants }
      // пока шёл запрос, ячейку могли поправить ещё раз: такое изменение остаётся в черновике
      sent.forEach((value, key) => {
        const now = draft.get(key)
        if (now && now.top === value.top && now.zone === value.zone) draft.delete(key)
      })
      persist()
      deltas.clear()
      for (const p of result.participants) {
        const old = before.get(p.id)
        if (old != null && p.place != null && old !== p.place) deltas.set(p.id, old - p.place)
      }
      const { cells, participants: people } = result.saved
      savedMessage.value = `Сохранено ${cells} ${plural(cells, 'результат', 'результата', 'результатов')} у ` +
        `${people} ${plural(people, 'участника', 'участников', 'участников')}. Баллы и места пересчитаны.`
      clearTimeout(deltaTimer)
      deltaTimer = setTimeout(() => deltas.clear(), DELTA_MS)
      restoredCount.value = 0
      fixAfterFilterChange()
    } catch (e) {
      const error = asApiError(e)
      saveError.value = error
      if (error.code === 'invalid_results' && typeof error.body.participant === 'number') {
        const routesList = Array.isArray(error.body.routes) ? (error.body.routes as number[]) : []
        errorTarget.value = { pid: error.body.participant, r: Math.max((routesList[0] ?? 1) - 1, 0) }
      }
    } finally {
      saving.value = false
    }
  }

  function discard(): void {
    edit.value = null
    draft.clear()
    savedMessage.value = ''
    restoredCount.value = 0
    saveError.value = null
    persist()
  }

  /** Перейти к ячейке, на которую пожаловался сервер или проверка «зона позже топа». */
  function goToProblem(): void {
    const target = errorTarget.value ?? invalid.value[0]
    const p = target ? byId.value.get(target.pid) : undefined
    if (p && target) goTo(p, target.r, french.value ? 1 : 0)
  }

  // ---- телефон: шаги ----

  function phoneOpen(pid: number): void {
    phone.pid = pid
  }

  function phoneClose(): void {
    phone.pid = null
  }

  /** Следующий участник по списку под фильтром; на последнем возвращает к списку. */
  function phoneNext(): void {
    const index = rows.value.findIndex((p) => p.id === phone.pid)
    const next = rows.value[index + 1]
    phone.pid = next ? next.id : null
  }

  function setPhoneRoute(route: number): void {
    phone.route = Math.max(0, Math.min(routes.value - 1, route))
  }

  function dispose(): void {
    clearTimeout(hintTimer)
    clearTimeout(deltaTimer)
  }

  return reactive({
    status, fatalMessage, payload, event, participants, french, routes, hasSets, hasGroups,
    filters, direction, draft, cursor, current, edit, rows, missingCount, stats, invalid, canSave, routeCounts,
    searchQuery, searchActive, searchResults, searchFocus, gridFocus,
    saving, saveError, errorTarget, savedMessage, restoredCount, storageOk, hint, flash, deltas, refreshing,
    phone, phoneParticipant,
    init, refresh, save, discard, goToProblem, goTo, valueAt, isDirty, rowDirty,
    setValue, cycleCell, setTop, stepCell, setAttempt, commitEdit, cancelEdit,
    moveTo, step, advance, clickCell, clickParticipant, setFilter, setDirection, applyKey,
    setSearch, moveSearch, pickSearch,
    phoneOpen, phoneClose, phoneNext, setPhoneRoute,
    showHint, dispose,
  })
}

export type MatrixFlow = ReturnType<typeof useMatrixFlow>
