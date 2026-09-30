<script setup lang="ts">
import { computed } from 'vue'
import type { MatrixParticipant } from '../../api/matrix'
import type { AttemptKind } from '../../domain/results'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow }>()

const route = computed(() => props.flow.phone.route)
const numbers = computed(() => Array.from({ length: props.flow.routes }, (_, i) => i))
const badPids = computed(() => new Set(props.flow.invalid.filter((c) => c.r === route.value).map((c) => c.pid)))

const TOPS: Array<[number, string, string]> = [[0, '—', 'нет'], [1, 'FL', 'flash'], [2, 'RP', 'redpoint']]
const ATTEMPTS: Array<[AttemptKind, string]> = [['top', 'Топ'], ['zone', 'Зона']]

const value = (p: MatrixParticipant) => props.flow.valueAt(p, route.value)
</script>

<template>
  <section class="re-ph-route">
    <div class="re-ph-routenav">
      <button type="button" class="re-btn" :disabled="route === 0" aria-label="Предыдущая трасса" @click="flow.setPhoneRoute(route - 1)">←</button>
      <label class="re-ph-routepick">
        <span class="re-sr-only">Трасса</span>
        <select :value="route" @change="flow.setPhoneRoute(Number(($event.target as HTMLSelectElement).value))">
          <option v-for="n in numbers" :key="n" :value="n">Трасса {{ n + 1 }}</option>
        </select>
      </label>
      <button
        type="button" class="re-btn" :disabled="route >= flow.routes - 1" aria-label="Следующая трасса"
        @click="flow.setPhoneRoute(route + 1)"
      >→</button>
    </div>

    <ul class="re-ph-list">
      <li v-for="p in flow.rows" :key="p.id" class="re-ph-route-row" :class="{ 'is-dirty': flow.isDirty(p.id, route), 'is-bad': badPids.has(p.id) }">
        <span class="re-ph-name">
          <b>{{ p.last_name }} {{ p.first_name }}</b>
          <small>PIN {{ p.pin }}<template v-if="!p.is_entered_result && !flow.rowDirty(p.id)"> · нет результата</template></small>
        </span>

        <div v-if="!flow.french" class="re-ph-three" role="group" :aria-label="`${p.last_name}, трасса ${route + 1}`">
          <button
            v-for="[top, label, name] in TOPS" :key="top" type="button" :class="{ 'is-fl': top === 1, 'is-rp': top === 2 }"
            :aria-pressed="value(p).top === top" :aria-label="name" @click="flow.setTop(p, route, top)"
          >{{ label }}</button>
        </div>

        <div v-else class="re-ph-steppers">
          <div
            v-for="[kind, label] in ATTEMPTS" :key="kind" class="re-stepper"
            :class="[`is-${kind === 'top' ? 'top' : 'zone'}`, { 'is-on': value(p)[kind] > 0 }]"
          >
            <button type="button" :aria-label="`${p.last_name}, ${label}: на попытку меньше`" @click="flow.stepCell(p, route, kind, -1)">−</button>
            <output>{{ value(p)[kind] > 0 ? value(p)[kind] : '—' }}</output>
            <button type="button" :aria-label="`${p.last_name}, ${label}: на попытку больше`" @click="flow.stepCell(p, route, kind, 1)">+</button>
          </div>
        </div>
      </li>
      <li v-if="!flow.rows.length" class="re-ph-empty">Под этот фильтр никто не попал. Выберите другой сет или группу.</li>
    </ul>

    <div class="re-ph-nav">
      <button type="button" class="re-btn" :disabled="route === 0" @click="flow.setPhoneRoute(route - 1)">Предыдущая</button>
      <button type="button" class="re-btn is-primary" :disabled="route >= flow.routes - 1" @click="flow.setPhoneRoute(route + 1)">Следующая трасса</button>
    </div>
  </section>
</template>
