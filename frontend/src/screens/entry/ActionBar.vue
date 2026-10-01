<script setup lang="ts">
import { computed } from 'vue'
import { plural } from '../../domain/format'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow; canSeeResults: boolean; resultsHref: string }>()
defineEmits<{ results: [event: MouseEvent] }>()

const total = computed(() => props.flow.results.length)
const summary = computed(() => props.flow.summary)
const submitLabel = computed(() => {
  if (props.flow.sending) return 'Отправляю…'
  return props.flow.sendError ? 'Отправить ещё раз' : 'Отправить'
})
const badRoutes = computed(() => props.flow.invalidRoutes.map((index) => index + 1))
</script>

<template>
  <footer class="re-action is-narrow">
    <template v-if="flow.step === 'done' || flow.step === 'locked'">
      <div v-if="flow.step === 'done' && flow.updateAllowed" class="re-act-row is-two">
        <button type="button" class="re-btn" @click="flow.edit()">Исправить</button>
        <a v-if="canSeeResults" class="re-btn is-primary" :href="resultsHref" @click="$emit('results', $event)">Смотреть результаты</a>
      </div>
      <a
        v-else-if="canSeeResults" class="re-btn is-primary is-wide" :href="resultsHref" @click="$emit('results', $event)"
      >Смотреть результаты</a>
    </template>
    <template v-else>
      <div v-if="flow.sendError" class="re-send-err" role="alert">{{ flow.sendErrorText }}</div>
      <div class="re-act-row">
        <div class="re-sum" aria-live="polite">
          <span v-if="badRoutes.length" class="re-err-text">
            {{ badRoutes.length > 1 ? 'Трассы' : 'Трасса' }} {{ badRoutes.join(', ') }}: зона позже топа.
            Исправьте, чтобы отправить.
          </span>
          <template v-else-if="flow.french">
            <span class="re-s"><b>{{ summary.tops }}</b> {{ plural(summary.tops, 'топ', 'топа', 'топов') }}</span>
            <span class="re-s"><b>{{ summary.zones }}</b> {{ plural(summary.zones, 'зона', 'зоны', 'зон') }}</span>
            <span class="re-of">из {{ total }} трасс</span>
          </template>
          <template v-else>
            <span class="re-s is-fl">FL <b>{{ summary.flash }}</b></span>
            <span class="re-s is-rp">RP <b>{{ summary.redpoint }}</b></span>
            <span class="re-of">отмечено {{ summary.marked }} из {{ total }}</span>
          </template>
        </div>
        <button
          type="button"
          class="re-btn is-primary"
          :disabled="badRoutes.length > 0 || flow.sending"
          @click="flow.requestSubmit()"
        >{{ submitLabel }}</button>
      </div>
    </template>
  </footer>
</template>
