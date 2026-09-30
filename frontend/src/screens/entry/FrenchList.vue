<script setup lang="ts">
import type { AttemptKind, RouteResult } from '../../domain/results'

defineProps<{ results: RouteResult[]; invalid: number[] }>()
defineEmits<{ step: [index: number, kind: AttemptKind, delta: number] }>()

const KINDS: Array<{ kind: AttemptKind; name: string }> = [
  { kind: 'top', name: 'топ' },
  { kind: 'zone', name: 'зона' },
]
</script>

<template>
  <p class="re-how">Номер попытки, с которой взяли топ и зону. «—» — не взяли.</p>
  <div class="re-fhead"><span>№</span><span>Топ</span><span>Зона</span></div>
  <div class="re-flist">
    <div
      v-for="(result, index) in results"
      :key="index"
      class="re-frow"
      :class="{ 'is-bad': invalid.includes(index) }"
    >
      <span class="re-rn">{{ index + 1 }}</span>
      <div
        v-for="{ kind, name } in KINDS"
        :key="kind"
        class="re-stepper"
        :class="[`is-${kind}`, { 'is-on': result[kind] > 0 }]"
      >
        <button
          type="button"
          :aria-label="`Трасса ${index + 1}, ${name}: на попытку меньше`"
          @click="$emit('step', index, kind, -1)"
        >−</button>
        <output>{{ result[kind] > 0 ? result[kind] : '—' }}</output>
        <button
          type="button"
          :aria-label="`Трасса ${index + 1}, ${name}: на попытку больше`"
          @click="$emit('step', index, kind, 1)"
        >+</button>
      </div>
      <p v-if="invalid.includes(index)" class="re-err">Зона не может быть позже топа</p>
    </div>
  </div>
</template>
