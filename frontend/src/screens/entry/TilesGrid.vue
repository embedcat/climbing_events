<script setup lang="ts">
import type { RouteResult } from '../../domain/results'

defineProps<{ results: RouteResult[] }>()
defineEmits<{ toggle: [index: number] }>()

const LABELS = ['—', 'flash', 'redpoint']
const SPOKEN = ['нет', 'flash', 'redpoint']
</script>

<template>
  <p class="re-how">
    Нажимайте на трассу:
    <span class="re-mini">—</span>→<span class="re-mini is-fl">FL</span>→<span class="re-mini is-rp">RP</span>→<span class="re-mini">—</span>
  </p>
  <div class="re-tiles">
    <button
      v-for="(result, index) in results"
      :key="index"
      type="button"
      class="re-tile"
      :class="{ 'is-fl': result.top === 1, 'is-rp': result.top === 2 }"
      :aria-label="`Трасса ${index + 1}: ${SPOKEN[result.top]}`"
      @click="$emit('toggle', index)"
    >
      <span class="re-tn">{{ index + 1 }}</span>
      <span class="re-tl">{{ LABELS[result.top] }}</span>
    </button>
  </div>
</template>
