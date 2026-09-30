<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { plural } from '../../domain/format'
import {
  cellView, flashRedpointTotals, formatScore, frenchTotals, fullName, genderLabel,
} from '../../domain/standings'
import type { ResultsFlow } from './useResultsFlow'

const props = defineProps<{ flow: ResultsFlow; editUrl: (participantId: number) => string }>()

const button = ref<HTMLButtonElement | null>(null)

const found = computed(() => props.flow.sheet!)
const row = computed(() => found.value.row)
const table = computed(() => found.value.table)
const french = computed(() => props.flow.french)
const payload = computed(() => props.flow.payload!)
const isMe = computed(() => row.value.id === props.flow.meId)
const where = computed(() => [table.value.group, genderLabel(table.value.gender)].filter(Boolean).join(', '))

const facts = computed(() => [
  row.value.birth_year ? `${row.value.birth_year} г. р.` : '',
  row.value.grade,
  row.value.city,
  row.value.team ? `«${row.value.team}»` : '',
  row.value.set ? `сет ${row.value.set_index + 1}, ${row.value.set}` : '',
].filter(Boolean).join(' · '))

const hasGrid = computed(() => row.value.place !== null && row.value.results.length > 0)

const summary = computed(() => {
  if (french.value) {
    const t = frenchTotals(row.value.results)
    return `${t.tops} ${plural(t.tops, 'топ', 'топа', 'топов')} за ${t.topAttempts} ${plural(t.topAttempts, 'попытку', 'попытки', 'попыток')}, ` +
      `${t.zones} ${plural(t.zones, 'зона', 'зоны', 'зон')} за ${t.zoneAttempts} ${plural(t.zoneAttempts, 'попытку', 'попытки', 'попыток')}`
  }
  const t = flashRedpointTotals(row.value.results)
  const best = payload.value.display.best_routes_num
  return `Flash ${t.flash} · redpoint ${t.redpoint}` + (best ? `. В зачёт идут ${best} лучших трасс, бледные не считаются.` : '')
})

const cell = (index: number) => cellView(row.value.results[index], french.value, row.value.counted[index] ?? true)
const frenchCell = (index: number) => {
  const r = row.value.results[index]
  return r && (r.top || r.zone) ? `Т${r.top || '–'} З${r.zone || '–'}` : '—'
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.flow.closeSheet()
}
onMounted(() => {
  button.value?.focus({ preventScroll: true })
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="re-sheet-host">
    <div class="re-sheet-bg" @click="flow.closeSheet()" />
    <div class="re-sheet" role="dialog" aria-modal="true" aria-labelledby="re-sheet-title">
      <div class="re-grabber" />
      <h3 id="re-sheet-title">{{ fullName(row) }}</h3>

      <div v-if="row.place !== null" class="re-sh-place">
        <b>{{ row.place }}</b>
        <span class="re-muted">место из {{ table.ranked.length }} · {{ where }} · {{ formatScore(row, payload.event.score_type) }}</span>
      </div>
      <p v-else class="re-muted">Результат ещё не введён · {{ where }}</p>

      <div v-if="facts" class="re-facts">{{ facts }}</div>

      <template v-if="hasGrid">
        <div class="re-rgrid" :class="{ 'is-fr': french }">
          <span
            v-for="(_, index) in row.results" :key="index"
            :class="[cell(index).kind && `k-${cell(index).kind}`, { nc: cell(index).dim }]"
          >
            <template v-if="french"><b>{{ index + 1 }}</b><small>{{ frenchCell(index) }}</small></template>
            <template v-else>{{ index + 1 }}</template>
          </span>
        </div>
        <p class="re-small">{{ summary }}</p>
      </template>

      <p v-if="isMe" class="re-is-me">Это вы. Телефон запомнил, в результатах сразу открывается ваша группа.</p>
      <div class="re-sheet-actions" :class="{ 'is-one': isMe && !payload.event.can_edit }">
        <button ref="button" type="button" class="re-btn" @click="flow.closeSheet()">Закрыть</button>
        <button v-if="!isMe" type="button" class="re-btn is-primary" @click="flow.rememberPerson(row)">Это я, запомнить</button>
        <a v-else-if="payload.event.can_edit" class="re-btn is-primary" :href="editUrl(row.id)">Править результаты</a>
      </div>
      <a v-if="!isMe && payload.event.can_edit" class="re-linkbtn re-edit-link" :href="editUrl(row.id)">Править результаты (организатор)</a>
    </div>
  </div>
</template>
