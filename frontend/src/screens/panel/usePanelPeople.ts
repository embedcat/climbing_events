// «Участники» панели: таблица для организатора с PIN, группой, сетом, оплатой и признаком «внёс результат».
// Данные те же, что у публичной вкладки: ответ API для организатора дополнен PIN, контактами и оплатой.
import { computed, reactive, ref } from 'vue'
import type { EventApi, EventPage, Person } from '../../api/event'
import { asApiError } from '../../api/http'
import { byName, matchesPanelQuery } from '../../domain/people'

export type PanelPeopleStatus = 'loading' | 'ready' | 'error'

export interface PanelPeopleDeps {
  eventId: number
  api: EventApi
}

export function usePanelPeople(deps: PanelPeopleDeps) {
  const { eventId, api } = deps

  const status = ref<PanelPeopleStatus>('loading')
  const errorMessage = ref('')
  const page = ref<EventPage | null>(null)
  const people = ref<Person[]>([])
  const query = ref('')
  const sheetId = ref<number | null>(null)

  const rows = computed(() => people.value.filter((p) => matchesPanelQuery(p, query.value)).sort(byName))
  const sheet = computed(() => people.value.find((p) => p.id === sheetId.value) ?? null)
  const withPay = computed(() => page.value?.pay.is_allowed ?? false)
  const withSets = computed(() => (page.value?.sets.length ?? 0) > 0)

  /** Колонки таблицы на компьютере: оплата и сет только если они есть у события. */
  const columns = computed(() => {
    const cols = [
      { key: 'name', label: 'Участник', width: 'minmax(0, 1.8fr)' },
      { key: 'pin', label: 'PIN', width: '70px' },
      { key: 'group', label: page.value?.groups.length ? 'Группа' : 'Пол', width: 'minmax(0, 1fr)' },
    ]
    if (withSets.value) cols.push({ key: 'set', label: 'Сет', width: '40px' })
    if (withPay.value) cols.push({ key: 'pay', label: 'Оплата', width: '100px' })
    cols.push({ key: 'result', label: 'Результат', width: '80px' })
    return cols
  })

  async function load(): Promise<void> {
    if (status.value !== 'ready') status.value = 'loading'
    try {
      const [loadedPage, payload] = await Promise.all([api.getPage(eventId), api.getPeople(eventId)])
      page.value = loadedPage
      people.value = payload.participants
      status.value = 'ready'
      errorMessage.value = ''
    } catch (error) {
      const failed = asApiError(error)
      errorMessage.value = failed.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : failed.message
      if (status.value !== 'ready') status.value = 'error'
    }
  }

  const groupName = (index: number): string => page.value?.groups[index] ?? ''
  const setName = (index: number): string => page.value?.sets[index]?.name ?? ''

  return reactive({
    eventId, status, errorMessage, page, people, query, rows, sheet, sheetId, columns, withPay, withSets,
    load, groupName, setName,
    setQuery: (value: string) => { query.value = value },
    openPerson: (id: number) => { sheetId.value = id },
    closeSheet: () => { sheetId.value = null },
  })
}

export type PanelPeopleApp = ReturnType<typeof usePanelPeople>
