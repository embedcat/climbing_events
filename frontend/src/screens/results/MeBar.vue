<script setup lang="ts">
import { computed } from 'vue'
import { formatScore, genderLabel } from '../../domain/standings'
import type { ResultsFlow } from './useResultsFlow'

const props = defineProps<{ flow: ResultsFlow }>()

const found = computed(() => props.flow.me)
/** Плашка нужна, когда своей строки не видно: она уехала за край, или открыта чужая таблица. */
const visible = computed(() => !!found.value && (!props.flow.meInCurrentTable || !props.flow.meRowVisible))

const row = computed(() => found.value?.row)
const where = computed(() => {
  const t = found.value?.table
  return t ? [t.group, genderLabel(t.gender)].filter(Boolean).join(', ') : ''
})
const delta = computed(() => (row.value ? props.flow.deltas.get(row.value.id) : undefined))
</script>

<template>
  <button v-if="visible && row" type="button" class="re-me-bar" @click="flow.goToMe()">
    <template v-if="row.place !== null">
      <span class="re-mb-pl">{{ row.place }}</span>
      <span class="re-mb-t">
        <b>Вы: {{ row.place }} место из {{ found!.table.ranked.length }}</b>
        <span>{{ flow.meInCurrentTable ? 'Показать мою строку' : `${where}. Открыть` }}</span>
      </span>
      <span class="re-mb-sc">
        {{ formatScore(row, flow.payload!.event.score_type) }}
        <span v-if="delta" class="re-delta" :class="delta > 0 ? 'is-up' : 'is-down'">{{ delta > 0 ? '▲' : '▼' }}{{ Math.abs(delta) }}</span>
      </span>
    </template>
    <template v-else>
      <span class="re-mb-pl">?</span>
      <span class="re-mb-t"><b>Вы ещё не ввели результат</b><span>{{ where }}</span></span>
      <span />
    </template>
  </button>
</template>
