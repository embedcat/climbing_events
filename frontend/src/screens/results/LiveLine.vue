<script setup lang="ts">
import { computed } from 'vue'
import { formatTime } from '../../domain/format'
import type { ResultsFlow } from './useResultsFlow'

const props = defineProps<{ flow: ResultsFlow }>()

const autoUpdating = computed(() => props.flow.isLive || props.flow.monitor)
const finishedText = computed(() =>
  props.flow.payload?.event.is_expired ? 'Итоговые результаты. Соревнование завершено.' : 'Ввод результатов закрыт.')
</script>

<template>
  <div class="re-live">
    <template v-if="autoUpdating">
      <span class="re-live-dot" :class="{ 'is-stale': flow.refreshFailed }" aria-hidden="true" />
      <span v-if="flow.refreshFailed">Нет связи · данные от {{ formatTime(flow.lastUpdate) }}</span>
      <span v-else>{{ flow.isLive ? 'Идёт' : 'Автообновление' }} · {{ flow.agoText }}</span>
      <button type="button" class="re-refresh" :disabled="flow.refreshing" @click="flow.refresh()">Обновить</button>
    </template>
    <span v-else>{{ finishedText }}</span>
  </div>
</template>
