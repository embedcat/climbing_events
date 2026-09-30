<script setup lang="ts">
import { computed } from 'vue'
import type { MatrixParticipant } from '../../api/matrix'
import type { AttemptKind, RouteResult } from '../../domain/results'
import FrenchList from '../entry/FrenchList.vue'
import TilesGrid from '../entry/TilesGrid.vue'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow }>()

const person = computed(() => props.flow.phoneParticipant)
const results = computed<RouteResult[]>(() =>
  person.value ? Array.from({ length: props.flow.routes }, (_, r) => props.flow.valueAt(person.value!, r)) : [])
const invalid = computed(() => props.flow.invalid.filter((c) => c.pid === person.value?.id).map((c) => c.r))
const isLast = computed(() => props.flow.rows[props.flow.rows.length - 1]?.id === person.value?.id)

function meta(p: MatrixParticipant): string {
  const { event } = props.flow
  const parts = [p.pin !== null ? `PIN ${p.pin}` : '']
  if (event!.groups.length > 1) parts.push(event!.groups[p.group_index] ?? '')
  parts.push(p.gender === 'FEMALE' ? 'Ж' : 'М')
  if (event!.sets.length > 1) parts.push(`сет ${p.set_index + 1}`)
  return parts.filter(Boolean).join(' · ')
}

const status = (p: MatrixParticipant) => props.flow.rowDirty(p.id) ? 'не сохранено' : p.is_entered_result ? 'внесён' : 'нет результата'
</script>

<template>
  <section v-if="person" class="re-ph-edit">
    <div class="re-who">
      <div>
        <div class="re-who-name">{{ person.last_name }} {{ person.first_name }}</div>
        <div class="re-who-meta">{{ meta(person) }}</div>
      </div>
      <button type="button" class="re-linkbtn" @click="flow.phoneClose()">К списку</button>
    </div>
    <div v-if="!person.is_entered_result && !flow.rowDirty(person.id)" class="re-banner">
      Результат ещё не внесён. Если все «нет», всё равно нажмите «Сохранить»: участник будет считаться внёсшим результат.
    </div>

    <FrenchList
      v-if="flow.french" :results="results" :invalid="invalid"
      @step="(index: number, kind: AttemptKind, delta: number) => flow.stepCell(person!, index, kind, delta)"
    />
    <TilesGrid v-else :results="results" @toggle="(index: number) => flow.cycleCell(person!, index)" />

    <div class="re-ph-nav">
      <button type="button" class="re-btn" @click="flow.phoneClose()">К списку</button>
      <button type="button" class="re-btn is-primary" @click="flow.phoneNext()">{{ isLast ? 'Это последний' : 'Следующий' }}</button>
    </div>
  </section>

  <ul v-else class="re-ph-list">
    <li v-for="p in flow.rows" :key="p.id">
      <button type="button" class="re-ph-row" @click="flow.phoneOpen(p.id)">
        <span class="re-ph-name">
          <b>{{ p.last_name }} {{ p.first_name }}</b>
          <small>{{ meta(p) }}</small>
        </span>
        <span class="re-ph-state" :class="{ 'is-missing': !p.is_entered_result && !flow.rowDirty(p.id), 'is-dirty': flow.rowDirty(p.id) }">
          {{ status(p) }}
        </span>
      </button>
    </li>
    <li v-if="!flow.rows.length" class="re-ph-empty">Под этот фильтр никто не попал. Выберите другой сет или группу.</li>
  </ul>
</template>
