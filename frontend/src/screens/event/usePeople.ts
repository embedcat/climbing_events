// Вкладка «Участники»: загрузка списка, поиск, фильтры по полу, группе и сету, карточка участника.
import { computed, reactive, ref } from 'vue'
import type { EventApi, Person } from '../../api/event'
import { asApiError } from '../../api/http'
import { emptyFilters, filterPeople, isFiltered, type PeopleFilters } from '../../domain/people'

export type PeopleStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface PeopleDeps {
  eventId: number
  api: EventApi
}

export function usePeople(deps: PeopleDeps) {
  const { eventId, api } = deps

  const status = ref<PeopleStatus>('idle')
  const errorMessage = ref('')
  const people = ref<Person[]>([])
  const canManage = ref(false)
  const filters = reactive<PeopleFilters>(emptyFilters())
  const sheetId = ref<number | null>(null)

  const filtered = computed(() => filterPeople(people.value, filters))
  const active = computed(() => isFiltered(filters))
  const sheet = computed(() => people.value.find((p) => p.id === sheetId.value) ?? null)
  const males = computed(() => people.value.filter((p) => p.gender === 'MALE').length)

  /** Список меняется, пока люди регистрируются, поэтому читаем его при каждом открытии вкладки. Прежний остаётся на виду. */
  async function load(): Promise<void> {
    if (status.value !== 'ready') status.value = 'loading'
    try {
      const payload = await api.getPeople(eventId)
      people.value = payload.participants
      canManage.value = payload.can_manage
      status.value = 'ready'
    } catch (e) {
      const error = asApiError(e)
      errorMessage.value = error.isNetwork ? 'Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.' : error.message
      if (status.value !== 'ready') status.value = 'error'
    }
  }

  function setGender(value: PeopleFilters['gender']): void {
    filters.gender = value
  }

  function setGroup(index: number): void {
    filters.group = index
  }

  /** Повторное нажатие на сет снимает фильтр. */
  function toggleSet(index: number): void {
    filters.set = filters.set === index ? -1 : index
  }

  function setQuery(value: string): void {
    filters.q = value
  }

  function clearFilters(): void {
    Object.assign(filters, emptyFilters())
  }

  /** Поиск по фамилии: «Найти в списке» после ошибки регистрации. */
  function search(query: string): void {
    Object.assign(filters, emptyFilters(), { q: query })
  }

  return reactive({
    status, errorMessage, people, canManage, filters, filtered, active, sheetId, sheet, males,
    load, setGender, setGroup, toggleSet, setQuery, clearFilters, search,
    openPerson: (id: number) => { sheetId.value = id },
    closeSheet: () => { sheetId.value = null },
  })
}

export type PeopleFlow = ReturnType<typeof usePeople>
