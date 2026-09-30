<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import LiveLine from './LiveLine.vue'
import MeBar from './MeBar.vue'
import ParticipantSheet from './ParticipantSheet.vue'
import ResultsTable from './ResultsTable.vue'
import TableSwitch from './TableSwitch.vue'
import type { ResultsFlow } from './useResultsFlow'

const props = defineProps<{ flow: ResultsFlow; editUrl: (participantId: number) => string }>()

const root = ref<HTMLElement | null>(null)

/** Экран занимает остаток окна: таблица прокручивается внутри, а шапка и плашка «Вы» остаются на месте. */
function measure(): void {
  const el = root.value
  if (el) el.style.setProperty('--re-top', `${Math.round(el.getBoundingClientRect().top + window.scrollY + 8)}px`)
}

const legend = computed(() => {
  const p = props.flow.payload
  if (!p) return []
  if (props.flow.french) {
    return [{ cls: 'k-top', text: 'топ' }, { cls: 'k-zone', text: 'только зона' }, { cls: '', text: 'в ячейке: попытка топа / зоны' }]
  }
  const items = [{ cls: 'k-fl', text: 'flash' }, { cls: 'k-rp', text: 'redpoint' }]
  if (p.display.best_routes_num) items.push({ cls: 'k-fl nc', text: 'не в зачёте' })
  return items
})

const onVisible = () => { if (!document.hidden) props.flow.wake() }

onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
  document.addEventListener('visibilitychange', onVisible)
  void props.flow.init()
})
onUnmounted(() => {
  window.removeEventListener('resize', measure)
  document.removeEventListener('visibilitychange', onVisible)
  props.flow.dispose()
})
</script>

<template>
  <div ref="root" class="re-screen re-results">
    <p v-if="flow.status === 'loading'" class="re-muted re-pad" role="status">Загружаю…</p>

    <section v-else-if="flow.status === 'fatal'" class="re-banner re-pad" role="alert">
      <span>{{ flow.fatalMessage }}</span>
      <button type="button" class="re-linkbtn" @click="flow.init()">Повторить</button>
    </section>

    <section v-else-if="flow.status === 'closed'" class="re-banner re-pad">Просмотр результатов закрыт</section>

    <template v-else-if="flow.payload">
      <main class="re-res-main">
        <LiveLine :flow="flow" />
        <TableSwitch :flow="flow" />
        <div class="re-legend">
          <span v-for="item in legend" :key="item.text"><i v-if="item.cls" class="re-lg" :class="item.cls" />{{ item.text }}</span>
        </div>
        <ResultsTable :flow="flow" />
      </main>
      <MeBar :flow="flow" />
    </template>

    <ParticipantSheet v-if="flow.sheet" :flow="flow" :edit-url="editUrl" />
    <div v-if="flow.toast" class="re-toast" role="status">{{ flow.toast }}</div>
  </div>
</template>
