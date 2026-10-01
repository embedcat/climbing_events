// Адреса страницы события: все они отдают один и тот же HTML, а экран выбирает Vue. Переходы между вкладками не
// перезагружают страницу, а адрес и кнопка «назад» остаются как у обычных страниц.
import { ref } from 'vue'

export type Screen = 'info' | 'enter' | 'people' | 'results' | 'reg' | 'regdone' | 'pay' | 'paydone'
export type Tab = 'info' | 'enter' | 'people' | 'results'

/** Вкладка, которая подсвечивается на экране: анкета и оплата открываются с «Инфо». */
export const TAB_OF: Record<Screen, Tab> = {
  info: 'info', enter: 'enter', people: 'people', results: 'results',
  reg: 'info', regdone: 'info', pay: 'info', paydone: 'info',
}

export const TABS: Array<{ tab: Tab; label: string }> = [
  { tab: 'info', label: 'Инфо' },
  { tab: 'enter', label: 'Ввод' },
  { tab: 'people', label: 'Участники' },
  { tab: 'results', label: 'Результаты' },
]

const PATHS: Record<Screen, string> = {
  info: '', enter: 'enter/', people: 'participants/', results: 'results/',
  reg: 'registration/', regdone: 'registration/', pay: 'pay/', paydone: 'pay/done/',
}

export const eventPath = (eventId: number, screen: Screen): string => `/e/${eventId}/${PATHS[screen]}`

/** Экран по адресу страницы; неизвестный адрес — «Инфо». */
export function parseScreen(eventId: number, pathname: string): Screen {
  const rest = pathname.replace(new RegExp(`^/e/${eventId}/?`), '').replace(/\/+$/, '')
  switch (rest) {
    case 'enter': return 'enter'
    case 'participants': return 'people'
    case 'results': return 'results'
    case 'registration': return 'reg'
    case 'pay': return 'pay'
    case 'pay/done': return 'paydone'
    default: return 'info'
  }
}

const queryString = (query?: Record<string, string | number>): string => {
  const entries = Object.entries(query ?? {})
  return entries.length ? `?${entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')}` : ''
}

export interface GoOptions {
  /** заменить запись в истории, а не добавить новую */
  replace?: boolean
  query?: Record<string, string | number>
}

export function createRouter(eventId: number, win: Window = window) {
  const screen = ref<Screen>(parseScreen(eventId, win.location.pathname))
  const search = ref(win.location.search)

  const href = (next: Screen, query?: Record<string, string | number>): string =>
    eventPath(eventId, next) + queryString(query)

  function go(next: Screen, options: GoOptions = {}): void {
    const url = href(next, options.query)
    const state = { screen: next }
    if (options.replace) win.history.replaceState(state, '', url)
    else win.history.pushState(state, '', url)
    screen.value = next
    search.value = win.location.search
  }

  function onPopState(): void {
    const stored = (win.history.state as { screen?: Screen } | null)?.screen
    screen.value = stored ?? parseScreen(eventId, win.location.pathname)
    search.value = win.location.search
  }
  win.addEventListener('popstate', onPopState)

  return {
    screen, search, go, href,
    /** Параметр адреса, например номер участника на экране оплаты. */
    param: (name: string): string | null => new URLSearchParams(search.value).get(name),
    dispose: () => win.removeEventListener('popstate', onPopState),
  }
}

export type Router = ReturnType<typeof createRouter>
