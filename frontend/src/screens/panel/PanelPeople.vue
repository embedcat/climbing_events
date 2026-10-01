<script setup lang="ts">
// «Участники» панели: таблица для организатора. Строка открывает карточку с контактами, оплатой и ссылкой на правку анкеты.
import { computed, onMounted, onUnmounted } from 'vue'
import type { Person } from '../../api/event'
import { plural } from '../../domain/format'
import { genderLetter, personName } from '../../domain/people'
import { matrixUrl } from '../../domain/siteEvents'
import type { PanelPeopleApp } from './usePanelPeople'

const props = defineProps<{ app: PanelPeopleApp, csrfToken: string }>()

onMounted(() => { void props.app.load() })

const gridStyle = computed(() => ({ '--p-cols': props.app.columns.map((c) => c.width).join(' ') }))
const groupLine = (p: Person): string => [props.app.groupName(p.group_index), genderLetter(p.gender)].filter(Boolean).join(' · ')
const metaLine = (p: Person): string => [groupLine(p), props.app.withSets ? `сет ${p.set_index + 1}` : ''].filter(Boolean).join(' · ')
const hint = computed(() => {
  const n = props.app.people.length
  const shown = props.app.rows.length
  const total = `${n} ${plural(n, 'участник', 'участника', 'участников')}`
  return shown === n ? `${total}. Строка открывает карточку: контакты, оплата, правка анкеты.` : `Найдено ${shown} из ${total}.`
})

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.app.closeSheet()
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="re-screen re-panel">
    <div class="re-p-tools">
      <label class="re-p-search" for="re-p-q">
        <span class="re-sr-only">Поиск участника</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></svg>
        <input
          id="re-p-q" type="search" placeholder="Фамилия или PIN" autocomplete="off" enterkeyhint="search"
          :value="app.query" @input="app.setQuery(($event.target as HTMLInputElement).value)"
        >
      </label>
      <form method="post" :action="`/e/${app.eventId}/admin_protocols`">
        <input type="hidden" name="csrfmiddlewaretoken" :value="csrfToken">
        <button type="submit" name="export_startlist" value="1" class="re-p-btn">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11M7 11l5 5 5-5M5 20h14" /></svg>Стартовый список
        </button>
      </form>
    </div>

    <p v-if="app.status === 'loading'" class="re-p-loading" role="status">Загружаю…</p>
    <div v-else-if="app.status === 'error'" class="re-p-err" role="alert">
      <span>{{ app.errorMessage }}</span>
      <button type="button" class="re-p-btn" @click="app.load()">Повторить</button>
    </div>
    <div v-else-if="!app.people.length" class="re-p-none">Пока никто не зарегистрировался.</div>

    <template v-else>
      <p class="re-p-hint">{{ hint }}</p>
      <div v-if="!app.rows.length" class="re-p-none">Никого не нашли. Проверьте фамилию или PIN.</div>
      <template v-else>
        <div class="re-p-cols" :style="gridStyle" aria-hidden="true">
          <span v-for="column in app.columns" :key="column.key">{{ column.label }}</span>
        </div>
        <ul class="re-p-list">
          <li v-for="p in app.rows" :key="p.id">
            <button type="button" class="re-p-row" :style="gridStyle" :data-id="p.id" @click="app.openPerson(p.id)">
              <span>
                <span class="re-p-name">{{ personName(p) }}</span>
                <span class="re-p-meta">{{ metaLine(p) }}</span>
              </span>
              <span class="re-p-side">
                <span class="re-p-pin">{{ p.pin ?? '—' }}</span>
                <span v-if="app.withPay" class="re-p-pill" :class="p.paid ? 'is-ok' : 'is-due'">{{ p.paid ? 'оплачен' : 'не оплачен' }}</span>
              </span>
              <span class="re-p-cell re-p-pin">{{ p.pin ?? '—' }}</span>
              <span class="re-p-cell">{{ groupLine(p) }}</span>
              <span v-if="app.withSets" class="re-p-cell">{{ p.set_index + 1 }}</span>
              <span v-if="app.withPay" class="re-p-cell">
                <span class="re-p-pill" :class="p.paid ? 'is-ok' : 'is-due'">{{ p.paid ? 'оплачен' : 'не оплачен' }}</span>
              </span>
              <span class="re-p-cell" :class="{ 're-p-ok': p.entered }">{{ p.entered ? 'внесён' : '—' }}</span>
            </button>
          </li>
        </ul>
      </template>
    </template>

    <div v-if="app.sheet" class="re-sheet-host">
      <div class="re-sheet-bg" @click="app.closeSheet()" />
      <div class="re-sheet re-p-sheet" role="dialog" aria-modal="true" aria-labelledby="re-p-person">
        <div class="re-grabber" />
        <h3 id="re-p-person">{{ personName(app.sheet) }}</h3>
        <div class="re-p-kv"><span>{{ app.page?.groups.length ? 'Группа' : 'Зачёт' }}</span><b>{{ groupLine(app.sheet) }}</b></div>
        <div v-if="app.withSets" class="re-p-kv"><span>Сет</span><b>{{ app.sheet.set_index + 1 }}, {{ app.setName(app.sheet.set_index) }}</b></div>
        <div class="re-p-kv"><span>PIN</span><b>{{ app.sheet.pin ?? '—' }}</b></div>
        <div v-if="app.sheet.phone" class="re-p-kv"><span>Телефон</span><b>{{ app.sheet.phone }}</b></div>
        <div v-if="app.sheet.email" class="re-p-kv"><span>Email</span><b>{{ app.sheet.email }}</b></div>
        <div v-if="app.withPay" class="re-p-kv">
          <span>Взнос</span>
          <span class="re-p-pill" :class="app.sheet.paid ? 'is-ok' : 'is-due'">{{ app.sheet.paid ? 'оплачен' : 'не оплачен' }}</span>
        </div>
        <div class="re-p-kv"><span>Результат</span><b>{{ app.sheet.entered ? 'внесён' : 'не внесён' }}</b></div>
        <div class="re-p-sheet-links">
          <a :href="`/e/${app.eventId}/p/${app.sheet.id}/`">Править анкету</a>
          <a :href="`${matrixUrl(app.eventId)}#p=${app.sheet.id}`">Результаты в матрице</a>
        </div>
        <div class="re-sheet-actions is-one">
          <button type="button" class="re-btn" @click="app.closeSheet()">Закрыть</button>
        </div>
      </div>
    </div>
  </div>
</template>
