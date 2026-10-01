<script setup lang="ts">
// Повторный ввод запрещён, а участник уже вносил результат: вместо ошибки на шаге PIN показываем его результат
// и говорим, кто может исправить.
import { computed } from 'vue'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow }>()

const who = computed(() => props.flow.who!)
const gender = computed(() => (who.value.gender === 'FEMALE' ? 'женщины' : 'мужчины'))
const meta = computed(() => {
  const parts = [who.value.group, who.value.gender === 'FEMALE' ? 'Ж' : 'М']
  if (who.value.set) parts.push(`сет ${who.value.set_index + 1}, ${who.value.set}`)
  return parts.filter(Boolean).join(' · ')
})
const standingLabel = computed(() =>
  (who.value.group ? `Сейчас в группе «${who.value.group}», ${gender.value}` : `Сейчас в зачёте: ${gender.value}`))

const LABELS = ['—', 'flash', 'redpoint']
const frenchRows = computed(() => props.flow.results.flatMap((r, i) =>
  (r.top > 0 || r.zone > 0 ? [{ number: i + 1, top: r.top, zone: r.zone }] : [])))
const attempt = (n: number) => (n ? `${n}-я попытка` : '—')
</script>

<template>
  <section class="re-who">
    <div>
      <div class="re-who-name">{{ who.last_name }} {{ who.first_name }}</div>
      <div class="re-who-meta">{{ meta }}</div>
    </div>
    <button type="button" class="re-linkbtn" @click="flow.notMe()">Не вы?</button>
  </section>

  <section class="re-done is-flat">
    <h2 class="re-h2">Вы уже внесли результаты</h2>
    <div v-if="flow.standing" class="re-place-card">
      <div class="re-pc-label">{{ standingLabel }}</div>
      <div class="re-pc-row">
        <span class="re-pc-place">{{ flow.standing.place }}</span>
        <span class="re-pc-of">место<br>из {{ flow.standing.of }}</span>
      </div>
    </div>
  </section>

  <p class="re-locked-note">
    Повторный ввод на этом событии закрыт. Нашли ошибку — подойдите к организатору с карточкой участника: он исправит.
  </p>

  <div class="re-list-head"><h2 class="re-h2">Ваши отметки</h2></div>
  <template v-if="flow.french">
    <table v-if="frenchRows.length" class="re-ck-table">
      <thead><tr><th>Трасса</th><th>Топ</th><th>Зона</th></tr></thead>
      <tbody>
        <tr v-for="row in frenchRows" :key="row.number">
          <td>{{ row.number }}</td><td>{{ attempt(row.top) }}</td><td>{{ attempt(row.zone) }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="re-muted">Ни одной отметки.</p>
  </template>
  <div v-else class="re-tiles">
    <span
      v-for="(result, index) in flow.results" :key="index" class="re-tile is-ro"
      :class="{ 'is-fl': result.top === 1, 'is-rp': result.top === 2 }"
    >
      <span class="re-tn">{{ index + 1 }}</span>
      <span class="re-tl">{{ LABELS[result.top] }}</span>
    </span>
  </div>
</template>
