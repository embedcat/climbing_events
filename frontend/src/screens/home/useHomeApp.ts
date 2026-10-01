// Главная: каталог событий с поиском и вкладками «Предстоящие» / «Прошедшие», «Вы участвуете» по записям браузера.
// Первую страницу каталога Django кладёт в HTML, поэтому экран не мигает загрузкой.
import { reactive } from 'vue'
import { asApiError } from '../../api/http'
import type { CatalogPeriod, SiteApi, SiteCatalog, SiteEventCard } from '../../api/site'
import { listRememberedEvents } from '../../domain/remember'
import type { KeyValueStore } from '../../domain/storage'
import { participationRow, type ParticipationRow } from '../../domain/siteEvents'

export type HomeStatus = 'loading' | 'ready' | 'error'

export interface HomeAppDeps {
  api: SiteApi
  store: KeyValueStore
  /** первая страница каталога из HTML; без неё экран запросит её сам */
  initial?: SiteCatalog | null
  /** пауза после последнего нажатия, прежде чем искать */
  debounceMs?: number
}

export function useHomeApp(deps: HomeAppDeps) {
  const { api, store, initial = null, debounceMs = 250 } = deps

  const state = reactive({
    query: '',
    when: 'upcoming' as CatalogPeriod,
    cards: (initial?.results ?? []) as SiteEventCard[],
    counts: initial?.counts ?? { upcoming: 0, past: 0 },
    hasMore: initial?.has_more ?? false,
    status: (initial ? 'ready' : 'loading') as HomeStatus,
    /** идёт запрос нового списка: старый остаётся на экране, чтобы поиск не мигал */
    busy: false,
    loadingMore: false,
    errorMessage: '',
    rows: [] as ParticipationRow[],
  })

  // ответ на устаревший запрос (поиск ушёл дальше) не должен затирать свежий
  let seq = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  async function load(): Promise<void> {
    const mine = ++seq
    clearTimeout(timer)
    state.busy = true
    try {
      const catalog = await api.events({ query: state.query, when: state.when, offset: 0 })
      if (mine !== seq) return
      state.cards = catalog.results
      state.counts = catalog.counts
      state.hasMore = catalog.has_more
      state.status = 'ready'
      state.errorMessage = ''
    } catch (error) {
      if (mine !== seq) return
      state.status = 'error'
      state.errorMessage = asApiError(error).message
    } finally {
      if (mine === seq) state.busy = false
    }
  }

  async function loadMore(): Promise<void> {
    if (state.loadingMore || !state.hasMore) return
    const mine = seq
    state.loadingMore = true
    try {
      const catalog = await api.events({ query: state.query, when: state.when, offset: state.cards.length })
      if (mine !== seq) return
      state.cards = [...state.cards, ...catalog.results]
      state.hasMore = catalog.has_more
    } catch (error) {
      if (mine === seq) state.errorMessage = asApiError(error).message
    } finally {
      state.loadingMore = false
    }
  }

  /** «Вы участвуете»: события, о которых помнит браузер. Не критично, поэтому ошибки молча пропускаем. */
  async function loadParticipations(): Promise<void> {
    const remembered = listRememberedEvents(store)
    if (!remembered.length) return
    try {
      const items = await api.participations(remembered.map((r) => ({ eventId: r.eventId, participantId: r.who.id })))
      state.rows = items.map((item) => participationRow(item, remembered.find((r) => r.eventId === item.event.id)?.who ?? null))
    } catch {
      state.rows = []
    }
  }

  async function init(): Promise<void> {
    await Promise.all([state.status === 'loading' ? load() : Promise.resolve(), loadParticipations()])
  }

  function setWhen(when: CatalogPeriod): void {
    if (state.when === when) return
    state.when = when
    void load()
  }

  /** Поиск стартует после паузы в наборе, пустой запрос возвращает весь список. */
  function setQuery(query: string): void {
    state.query = query
    clearTimeout(timer)
    timer = setTimeout(() => { void load() }, debounceMs)
  }

  function dispose(): void {
    clearTimeout(timer)
    seq += 1
  }

  return Object.assign(state, { init, load, loadMore, setWhen, setQuery, dispose })
}

export type HomeApp = ReturnType<typeof useHomeApp>
