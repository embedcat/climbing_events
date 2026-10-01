<script setup lang="ts">
// Сеты события: время, заполненность при лимите мест и число участников.
import { computed } from 'vue'
import { plural } from '../../domain/format'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const page = computed(() => props.app.page!)
/** Полоса заполненности нужна, пока идёт регистрация и у сета есть лимит мест. */
const withLimit = computed(() => props.app.regOpen && page.value.sets.some((s) => s.capacity > 0))
/** Пока участники нигде не регистрируются, считать в сетах нечего. */
const withCounts = computed(() => !(page.value.is_without_registration && (props.app.stage === 'reg' || props.app.stage === 'reg_closed')))

const rows = computed(() => page.value.sets.map((set) => {
  let right = ''
  let percent: number | null = null
  if (withLimit.value && set.capacity > 0) {
    percent = Math.min(100, Math.round((set.count / set.capacity) * 100))
    right = set.is_full ? 'мест нет' : `свободно ${set.capacity - set.count}`
  } else if (withCounts.value) {
    right = `${set.count} ${plural(set.count, 'участник', 'участника', 'участников')}`
  }
  return { set, right, percent, full: withLimit.value && set.is_full }
}))

const hint = computed(() => {
  if (props.app.regOpen) return 'Сет выбираете при регистрации. Перенести в другой сет может только организатор.'
  const stage = props.app.stage
  if (page.value.is_without_registration && (stage === 'reg' || stage === 'reg_closed' || stage === 'live')) {
    return 'Сет укажете вместе с результатами.'
  }
  return ''
})
</script>

<template>
  <section v-if="page.sets.length" class="re-block">
    <h3 class="re-bh">Сеты</h3>
    <ul class="re-sets">
      <li v-for="row in rows" :key="row.set.index" :class="{ 'is-full': row.full }">
        <span class="sn">Сет {{ row.set.index + 1 }}</span>
        <span class="st">{{ row.set.name }}</span>
        <span v-if="row.percent !== null" class="re-bar" aria-hidden="true"><i :style="{ width: `${row.percent}%` }" /></span>
        <span v-else />
        <span class="sc">{{ row.right }}</span>
      </li>
    </ul>
    <p v-if="hint" class="re-hint">{{ hint }}</p>
  </section>
</template>
