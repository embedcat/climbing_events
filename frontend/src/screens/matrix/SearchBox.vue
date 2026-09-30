<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { MatrixParticipant } from '../../api/matrix'
import { isVisible } from '../../domain/matrix'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow }>()

const input = ref<HTMLInputElement | null>(null)
const open = ref(false)

const showList = computed(() => open.value && props.flow.searchQuery.trim() !== '')

watch(() => props.flow.searchFocus, () => input.value?.focus())

function meta(p: MatrixParticipant): string {
  const { event } = props.flow
  const parts = [p.pin !== null ? String(p.pin) : '']
  if (event!.sets.length > 1) parts.push(`сет ${p.set_index + 1}`)
  if (event!.groups.length > 1) parts.push(event!.groups[p.group_index] ?? '')
  parts.push(p.gender === 'FEMALE' ? 'Ж' : 'М')
  return parts.filter(Boolean).join(' · ')
}

const hidden = (p: MatrixParticipant) => !isVisible(p, props.flow.filters)

function onKeydown(event: KeyboardEvent): void {
  const { flow } = props
  if (event.key === 'ArrowDown' && flow.searchResults.length) { event.preventDefault(); flow.moveSearch(1) }
  else if (event.key === 'ArrowUp' && flow.searchResults.length) { event.preventDefault(); flow.moveSearch(-1) }
  else if (event.key === 'Enter') { event.preventDefault(); flow.pickSearch(); open.value = false }
  else if (event.key === 'Escape') {
    event.preventDefault()
    flow.setSearch('')
    flow.gridFocus++
  }
}

function pick(p: MatrixParticipant): void {
  props.flow.pickSearch(p)
  open.value = false
}
</script>

<template>
  <div class="re-mx-field">
    <label class="re-mx-label" for="re-search">Найти участника</label>
    <div class="re-mx-search">
      <input
        id="re-search" ref="input" type="text" placeholder="Фамилия или PIN" autocomplete="off" enterkeyhint="go"
        :value="flow.searchQuery" role="combobox" aria-controls="re-search-list" :aria-expanded="showList"
        @input="flow.setSearch(($event.target as HTMLInputElement).value); open = true"
        @focus="open = true" @blur="open = false" @keydown="onKeydown"
      >
      <kbd>/</kbd>
      <div v-if="showList" id="re-search-list" class="re-mx-sr" role="listbox">
        <div v-if="!flow.searchResults.length" class="re-mx-sr-empty">Никого не нашли</div>
        <div
          v-for="(p, index) in flow.searchResults" :key="p.id" class="re-mx-sr-item" role="option"
          :aria-selected="index === flow.searchActive" @mousedown.prevent="pick(p)"
        >
          <span><b>{{ p.last_name }}</b> {{ p.first_name }}</span>
          <span class="re-mx-sr-meta">{{ meta(p) }}<template v-if="hidden(p)"> · <em>вне фильтра, переключу</em></template></span>
        </div>
      </div>
    </div>
  </div>
</template>
