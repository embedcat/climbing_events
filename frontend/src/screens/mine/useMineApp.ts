// Кабинет организатора «Мои события»: его события с числами, фильтр по этапу и, для суперпользователя, переключатель
// «Мои / Все события сайта». Первый список Django кладёт в HTML.
import { computed, reactive, ref } from 'vue'
import { asApiError } from '../../api/http'
import type { MyEventCard, MyEvents, MyEventsScope, SiteApi } from '../../api/site'
import { matchesFilter, MINE_FILTERS, type MineFilter } from '../../domain/siteEvents'

export type MineStatus = 'loading' | 'ready' | 'error'

export interface MineAppDeps {
  api: SiteApi
  /** список из HTML; без него экран запросит его сам */
  initial?: MyEvents | null
}

export function useMineApp(deps: MineAppDeps) {
  const { api, initial = null } = deps

  const scope = ref<MyEventsScope>(initial?.scope ?? 'mine')
  const isSuperuser = ref(initial?.is_superuser ?? false)
  const filter = ref<MineFilter>('all')
  const cards = ref<MyEventCard[]>(initial?.results ?? [])
  const status = ref<MineStatus>(initial ? 'ready' : 'loading')
  const errorMessage = ref('')
  const busy = ref(false)

  // ответ на устаревший запрос (режим уже переключили) не должен затирать свежий
  let seq = 0

  const visible = computed(() => cards.value.filter((card) => matchesFilter(card, filter.value)))
  const counts = computed(() => Object.fromEntries(
    MINE_FILTERS.map(({ value }) => [value, cards.value.filter((card) => matchesFilter(card, value)).length]),
  ) as Record<MineFilter, number>)

  async function load(): Promise<void> {
    const mine = ++seq
    busy.value = true
    try {
      const data = await api.myEvents(scope.value)
      if (mine !== seq) return
      cards.value = data.results
      isSuperuser.value = data.is_superuser
      status.value = 'ready'
      errorMessage.value = ''
    } catch (error) {
      if (mine !== seq) return
      status.value = 'error'
      errorMessage.value = asApiError(error).message
    } finally {
      if (mine === seq) busy.value = false
    }
  }

  async function init(): Promise<void> {
    if (status.value === 'loading') await load()
  }

  function setScope(next: MyEventsScope): void {
    if (scope.value === next) return
    scope.value = next
    void load()
  }

  function setFilter(next: MineFilter): void {
    filter.value = next
  }

  return reactive({
    scope, isSuperuser, filter, cards, status, errorMessage, busy, visible, counts,
    init, load, setScope, setFilter,
  })
}

export type MineApp = ReturnType<typeof useMineApp>
