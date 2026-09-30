<script setup lang="ts">
import { computed } from 'vue'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow }>()

const who = computed(() => props.flow.submitted)
const meta = computed(() => {
  const w = who.value
  if (!w) return ''
  const parts = [w.group, w.gender === 'FEMALE' ? 'Ж' : 'М']
  if (w.set) parts.push(`сет ${w.set_index + 1}`)
  return parts.filter(Boolean).join(' · ')
})
const standingLabel = computed(() => {
  const w = who.value
  if (!w) return ''
  const gender = w.gender === 'FEMALE' ? 'женщины' : 'мужчины'
  return w.group ? `Сейчас в группе «${w.group}», ${gender}` : `Сейчас в зачёте: ${gender}`
})
</script>

<template>
  <section v-if="who" class="re-done">
    <svg class="re-done-mark" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="24" r="22" />
      <path d="M14 24.5l7 7 13-14" />
    </svg>
    <h2 class="re-h2">Результаты отправлены</h2>
    <p class="re-muted">{{ who.last_name }} {{ who.first_name }} · {{ meta }}</p>
    <div v-if="flow.standing" class="re-place-card">
      <div class="re-pc-label">{{ standingLabel }}</div>
      <div class="re-pc-row">
        <span class="re-pc-place">{{ flow.standing.place }}</span>
        <span class="re-pc-of">место<br>из {{ flow.standing.of }}</span>
      </div>
    </div>
    <p class="re-muted re-small">Места будут меняться, пока другие участники вводят результаты.</p>
    <p class="re-remember">Мы запомнили вас на этом телефоне: в результатах сразу откроется ваша группа.</p>
  </section>
</template>
