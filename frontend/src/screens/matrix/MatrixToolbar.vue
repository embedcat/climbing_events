<script setup lang="ts">
import type { Direction } from '../../domain/matrix'
import FilterBar from './FilterBar.vue'
import SearchBox from './SearchBox.vue'
import type { MatrixFlow } from './useMatrixFlow'

defineProps<{ flow: MatrixFlow }>()

const DIRECTIONS: Array<[Direction, string, string]> = [
  ['right', '→ по участнику', 'Удобно переносить карточку участника'],
  ['down', '↓ по трассе', 'Удобно переносить протокол трассы'],
]
</script>

<template>
  <section class="re-mx-toolbar" aria-label="Фильтры">
    <FilterBar :flow="flow" />
    <div class="re-mx-filters">
      <SearchBox :flow="flow" />
      <div class="re-mx-field">
        <span id="re-l-dir" class="re-mx-label">Курсор после ввода</span>
        <div class="re-mx-seg" role="group" aria-labelledby="re-l-dir">
          <button
            v-for="[value, label, title] in DIRECTIONS" :key="value" type="button" :title="title"
            :aria-pressed="flow.direction === value" @click="flow.setDirection(value)"
          >{{ label }}</button>
        </div>
      </div>
    </div>
  </section>
</template>
