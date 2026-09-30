<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { plural } from '../../domain/format'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow }>()
const sendButton = ref<HTMLButtonElement | null>(null)

const who = computed(() => props.flow.currentWho)
const meta = computed(() => {
  const w = who.value
  if (!w) return ''
  const parts = [w.group, w.gender === 'FEMALE' ? 'Ж' : 'М']
  if (w.set) parts.push(`сет ${w.set_index + 1}`)
  return parts.filter(Boolean).join(' · ')
})

const flash = computed(() => props.flow.results.flatMap((r, i) => (r.top === 1 ? [i + 1] : [])))
const redpoint = computed(() => props.flow.results.flatMap((r, i) => (r.top === 2 ? [i + 1] : [])))
const none = computed(() => props.flow.results.length - flash.value.length - redpoint.value.length)
const frenchRows = computed(() =>
  props.flow.results.flatMap((r, i) => (r.top > 0 || r.zone > 0 ? [{ number: i + 1, top: r.top, zone: r.zone }] : [])))

const attempt = (n: number) => (n ? `${n}-я попытка` : '—')

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.flow.closeSheet()
}

onMounted(() => {
  sendButton.value?.focus({ preventScroll: true })
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="re-sheet-host">
    <div class="re-sheet-bg" @click="flow.closeSheet()" />
    <div class="re-sheet" role="dialog" aria-modal="true" aria-labelledby="re-sheet-title">
      <div class="re-grabber" />
      <h3 id="re-sheet-title">Проверьте перед отправкой</h3>
      <p v-if="who" class="re-muted re-small">{{ who.last_name }} {{ who.first_name }} · {{ meta }}</p>

      <template v-if="!flow.french">
        <div class="re-ck">
          <span class="re-ck-k is-fl">Flash</span>
          <div class="re-ck-v">
            <span v-for="n in flash" :key="n" class="re-num">{{ n }}</span>
            <span v-if="!flash.length" class="re-muted">нет</span>
          </div>
        </div>
        <div class="re-ck">
          <span class="re-ck-k is-rp">Redpoint</span>
          <div class="re-ck-v">
            <span v-for="n in redpoint" :key="n" class="re-num">{{ n }}</span>
            <span v-if="!redpoint.length" class="re-muted">нет</span>
          </div>
        </div>
        <p class="re-muted re-small">Без пролаза: {{ none }} {{ plural(none, 'трасса', 'трассы', 'трасс') }}.</p>
      </template>
      <template v-else>
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

      <div class="re-sheet-actions">
        <button type="button" class="re-btn" @click="flow.closeSheet()">Изменить</button>
        <button ref="sendButton" type="button" class="re-btn is-primary" @click="flow.send()">Всё верно, отправить</button>
      </div>
    </div>
  </div>
</template>
