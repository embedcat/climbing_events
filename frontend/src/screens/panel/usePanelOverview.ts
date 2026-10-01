// «Обзор» панели события: переключатели дня события, числа, чек-лист, ссылки для зала и служебные действия.
// Переключатели меняются сразу, а на сервер уходят по очереди: быстрые нажатия не обгоняют друг друга.
import { computed, reactive, ref } from 'vue'
import { isRemoved, type PanelAction, type PanelApi, type PanelFlag, type PanelOverview } from '../../api/panel'
import { asApiError } from '../../api/http'
import { ACTION_INFO, ACTION_ORDER, checklistProgress, checklistRows, hallLinks } from '../../domain/panel'

export type PanelStatus = 'loading' | 'ready' | 'error'

export interface PanelOverviewDeps {
  eventId: number
  api: PanelApi
  /** тестовые данные доступны только суперпользователю (сервер проверяет это сам) */
  isSuperuser?: boolean
  /** переход на другую страницу: после удаления события */
  navigate?: (url: string) => void
  copy?: (text: string) => Promise<void>
  origin?: string
}

const TOAST_MS = 4000

export function usePanelOverview(deps: PanelOverviewDeps) {
  const { eventId, api, isSuperuser = false } = deps
  const navigate = deps.navigate ?? ((url: string) => window.location.assign(url))
  const copy = deps.copy ?? ((text: string) => navigator.clipboard.writeText(text))
  const origin = deps.origin ?? window.location.origin

  const overview = ref<PanelOverview | null>(null)
  const status = ref<PanelStatus>('loading')
  const errorMessage = ref('')
  const toast = ref('')
  const confirm = ref<PanelAction | null>(null)
  const acting = ref(false)
  /** значения переключателей, которые уже показаны, но сервер ещё не подтвердил */
  const desired = reactive<Partial<Record<PanelFlag, boolean>>>({})
  const saving = ref(0)

  let chain: Promise<void> = Promise.resolve()
  let toastTimer: ReturnType<typeof setTimeout> | undefined

  function showToast(text: string): void {
    toast.value = text
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => { toast.value = '' }, TOAST_MS)
  }

  async function load(): Promise<void> {
    status.value = overview.value ? 'ready' : 'loading'
    try {
      overview.value = await api.overview(eventId)
      status.value = 'ready'
      errorMessage.value = ''
    } catch (error) {
      errorMessage.value = asApiError(error).message
      if (!overview.value) status.value = 'error'
    }
  }

  const flags = computed<Record<PanelFlag, boolean>>(() => {
    const base = overview.value?.flags ?? { is_published: false, is_registration_open: false, is_enter_result_allowed: false, is_results_allowed: false }
    return { ...base, ...desired }
  })

  async function send(flag: PanelFlag, value: boolean): Promise<void> {
    saving.value += 1
    try {
      const fresh = await api.setFlags(eventId, { [flag]: value })
      // подтверждено; если за это время переключили ещё раз, остаётся новое значение
      if (desired[flag] === value) delete desired[flag]
      overview.value = fresh
    } catch (error) {
      delete desired[flag]
      showToast(asApiError(error).message)
    } finally {
      saving.value -= 1
    }
  }

  function toggle(flag: PanelFlag): Promise<void> {
    if (!overview.value) return Promise.resolve()
    const next = !flags.value[flag]
    desired[flag] = next
    chain = chain.then(() => send(flag, next))
    return chain
  }

  const progress = computed(() => checklistProgress(overview.value?.checklist ?? []))
  const checklist = computed(() => checklistRows(overview.value?.checklist ?? [], eventId))
  const links = computed(() => hallLinks(eventId, origin))
  const percent = computed(() => {
    const o = overview.value
    return o && o.participants_count ? Math.round((o.entered_count / o.participants_count) * 100) : 0
  })

  /** Служебные действия: завершённое событие очищать нельзя, тестовые данные только суперпользователю. */
  const actions = computed(() => ACTION_ORDER
    .filter((action) => action !== 'mock_data' || isSuperuser)
    .map((action) => ({ action, ...ACTION_INFO[action], disabled: action === 'clear_event' && Boolean(overview.value?.is_expired) })))

  function ask(action: PanelAction): void {
    confirm.value = action
  }

  function cancel(): void {
    if (!acting.value) confirm.value = null
  }

  async function run(): Promise<void> {
    const action = confirm.value
    if (!action || acting.value) return
    acting.value = true
    try {
      const result = await api.runAction(eventId, action)
      confirm.value = null
      if (isRemoved(result)) {
        navigate(result.redirect)
        return
      }
      overview.value = result
      showToast(ACTION_INFO[action].done)
    } catch (error) {
      confirm.value = null
      showToast(asApiError(error).message)
    } finally {
      acting.value = false
    }
  }

  async function copyLink(url: string, label: string): Promise<void> {
    try {
      await copy(url)
      showToast(`Ссылка скопирована (${label})`)
    } catch {
      showToast('Не удалось скопировать ссылку')
    }
  }

  function dispose(): void {
    clearTimeout(toastTimer)
  }

  return reactive({
    eventId, overview, status, errorMessage, toast, confirm, acting, flags, saving, progress, checklist, links, percent,
    actions, load, toggle, ask, cancel, run, copyLink, showToast, dispose,
  })
}

export type PanelOverviewApp = ReturnType<typeof usePanelOverview>
