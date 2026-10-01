<script setup lang="ts">
// «Участники»: поиск себя по фамилии, фильтры по полу, группе и сету. На телефоне список, на компьютере таблица.
import { computed } from 'vue'
import type { Person } from '../../api/event'
import { plural } from '../../domain/format'
import { cityLine, genderLetter, personMeta, personName } from '../../domain/people'
import PersonSheet from './PersonSheet.vue'
import TabAction from './TabAction.vue'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const page = computed(() => props.app.page!)
const flow = computed(() => props.app.people)
const f = computed(() => flow.value.filters)
const withSets = computed(() => page.value.sets.length > 0)
const withGroups = computed(() => page.value.groups.length > 0)

const GENDERS = [['all', 'Все'], ['MALE', 'М'], ['FEMALE', 'Ж']] as const
const people = (n: number) => `${n} ${plural(n, 'участник', 'участника', 'участников')}`

const inGender = computed(() => flow.value.people.filter((p) => f.value.gender === 'all' || p.gender === f.value.gender))
const chips = computed(() => [
  { index: -1, name: 'Все группы', count: inGender.value.length },
  ...page.value.groups.map((name, index) => ({ index, name, count: inGender.value.filter((p) => p.group_index === index).length })),
])
const setCards = computed(() => page.value.sets.map((set) => {
  const count = flow.value.people.filter((p) => p.set_index === set.index).length
  const limited = set.capacity > 0 && !page.value.is_without_registration
  return { set, text: limited ? `${count} из ${set.capacity}` : `${count} чел.` }
}))

const head = computed(() => {
  const all = flow.value.people
  const list = flow.value.filtered
  if (flow.value.active) return { title: `Найдено ${list.length}`, side: `из ${all.length}` }
  return { title: people(all.length), side: `М ${flow.value.males} · Ж ${all.length - flow.value.males}` }
})
const cities = computed(() => (flow.value.active ? '' : cityLine(flow.value.people)))

/** Колонки таблицы на компьютере: только то, что событие собирает при регистрации. */
const columns = computed(() => {
  const fields = page.value.registration.fields
  const cols: Array<{ key: string; label: string; width: string; num?: boolean }> = [
    { key: 'name', label: 'Участник', width: 'minmax(0, 1.7fr)' },
  ]
  if (fields.includes('birth_year')) cols.push({ key: 'year', label: 'Год', width: '52px', num: true })
  if (fields.includes('grade')) cols.push({ key: 'grade', label: 'Разряд', width: '74px' })
  if (fields.includes('city')) cols.push({ key: 'city', label: 'Город', width: 'minmax(0, 1fr)' })
  if (fields.includes('team')) cols.push({ key: 'team', label: 'Команда', width: 'minmax(0, 1fr)' })
  cols.push({ key: 'group', label: withGroups.value ? 'Группа' : 'Пол', width: 'minmax(0, 1.1fr)' })
  if (withSets.value) cols.push({ key: 'set', label: 'Сет', width: '40px', num: true })
  return cols
})
const gridStyle = computed(() => ({ '--pcols': columns.value.map((c) => c.width).join(' ') }))

const groupLine = (p: Person) => [props.app.groupName(p.group_index), genderLetter(p.gender)].filter(Boolean).join(' · ')
const cell = (p: Person, key: string): string => ({
  year: p.birth_year ? String(p.birth_year) : '—',
  grade: p.grade || '—',
  city: p.city || '—',
  team: p.team || '—',
  group: groupLine(p),
  set: String(p.set_index + 1),
} as Record<string, string>)[key]

const emptyText = computed(() => (page.value.is_without_registration
  ? 'Регистрация на это событие не нужна, поэтому список пока пуст. Участники появятся здесь, когда начнут вносить результаты.'
  : 'Пока никто не зарегистрировался.'))
</script>

<template>
  <div class="re-fill">
    <main class="re-main">
      <p v-if="flow.status === 'loading' || flow.status === 'idle'" class="re-loading" role="status">Загружаю…</p>

      <section v-else-if="flow.status === 'error'" class="re-banner" role="alert">
        <span>{{ flow.errorMessage }}</span>
        <button type="button" class="re-linkbtn" @click="flow.load()">Повторить</button>
      </section>

      <section v-else-if="!flow.people.length" class="re-none"><p>{{ emptyText }}</p></section>

      <template v-else>
        <div class="re-ptools">
          <label class="re-search" for="re-q">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></svg>
            <span class="re-sr-only">Поиск по фамилии</span>
            <input
              id="re-q" type="search" placeholder="Найти себя по фамилии" autocomplete="off" enterkeyhint="search"
              :value="f.q" @input="flow.setQuery(($event.target as HTMLInputElement).value)"
            >
          </label>
          <div class="re-gsel">
            <div class="re-seg" role="group" aria-label="Пол">
              <button
                v-for="[value, label] in GENDERS" :key="value" type="button" :aria-pressed="f.gender === value"
                @click="flow.setGender(value)"
              >{{ label }}</button>
            </div>
            <div v-if="withGroups" class="re-chips" role="group" aria-label="Группа">
              <button
                v-for="chip in chips" :key="chip.index" type="button" :aria-pressed="f.group === chip.index"
                @click="flow.setGroup(chip.index)"
              >{{ chip.name }}<span class="re-cnt">{{ chip.count }}</span></button>
            </div>
          </div>
        </div>

        <div v-if="withSets" class="re-setcards" role="group" aria-label="Сет">
          <button
            v-for="card in setCards" :key="card.set.index" type="button" class="re-setcard"
            :aria-pressed="f.set === card.set.index" @click="flow.toggleSet(card.set.index)"
          >
            <b>Сет {{ card.set.index + 1 }} <em>{{ card.set.name }}</em></b>
            <span>{{ card.text }}</span>
          </button>
        </div>

        <div class="re-block">
          <div class="re-plist-head">
            <h2>{{ head.title }}</h2>
            <span>{{ head.side }}</span>
          </div>

          <div v-if="!flow.filtered.length" class="re-none">
            <p>Никого не нашли. {{ f.q.trim() ? 'Проверьте фамилию или снимите фильтры.' : 'Снимите фильтры.' }}</p>
            <button type="button" class="re-linkbtn" @click="flow.clearFilters()">Показать всех</button>
            <p v-if="app.regOpen && !app.me">Нет в списке — значит, вы ещё не зарегистрированы.</p>
          </div>

          <template v-else>
            <!-- на компьютере строка раскладывается в колонки таблицы, на телефоне — имя, строка данных и группа справа -->
            <div class="re-plist-cols" :style="gridStyle" aria-hidden="true">
              <span v-for="column in columns" :key="column.key">{{ column.label }}</span>
            </div>
            <ul class="re-plist">
              <li v-for="p in flow.filtered" :key="p.id">
                <button
                  type="button" class="re-prow" :class="{ 'is-me': app.isMe(p.id) }" :style="gridStyle" :data-id="p.id"
                  @click="flow.openPerson(p.id)"
                >
                  <span class="re-pr-main">
                    <span class="re-pr-name">{{ personName(p) }}<span v-if="app.isMe(p.id)" class="re-tag">вы</span></span>
                    <span class="re-pr-meta">{{ personMeta(p) }}</span>
                  </span>
                  <span class="re-pr-side">
                    <b>{{ groupLine(p) }}</b>
                    <span v-if="withSets">сет {{ p.set_index + 1 }}</span>
                  </span>
                  <span
                    v-for="column in columns.slice(1)" :key="column.key" class="re-pc" :class="{ 'is-num': column.num }"
                  >{{ cell(p, column.key) }}</span>
                </button>
              </li>
            </ul>
            <p v-if="cities" class="re-hint">Города: {{ cities }}</p>
          </template>
        </div>
      </template>
    </main>
    <TabAction tab="people" :app="app" />
    <PersonSheet v-if="flow.sheet" :app="app" :person="flow.sheet" />
  </div>
</template>
