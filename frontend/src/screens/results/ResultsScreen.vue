<script setup lang="ts">
// Вкладка «Результаты»: одна таблица на группу. Пока результатов нет, вместо таблицы из одних «ещё не ввели»
// страница события подставляет объяснение (слот empty).
import { computed, onMounted, onUnmounted } from 'vue'
import LiveLine from './LiveLine.vue'
import MeBar from './MeBar.vue'
import ParticipantSheet from './ParticipantSheet.vue'
import ResultsTable from './ResultsTable.vue'
import TableSwitch from './TableSwitch.vue'
import type { ResultsFlow } from './useResultsFlow'

const props = defineProps<{ flow: ResultsFlow; editUrl: (participantId: number) => string }>()

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

/** Результат не ввёл никто: таблица состояла бы из одних «ещё не ввели». */
const noResults = computed(() => !!props.flow.payload && props.flow.payload.tables.every((t) => t.ranked.length === 0))

const onVisible = () => { if (!document.hidden) props.flow.wake() }

onMounted(() => {
  document.addEventListener('visibilitychange', onVisible)
  // вернулись на вкладку: данные уже есть, опрос запускаем заново
  if (props.flow.payload) props.flow.resume()
  else void props.flow.init()
})
onUnmounted(() => {
  document.removeEventListener('visibilitychange', onVisible)
  props.flow.dispose()
})
</script>

<template>
  <div class="re-fill re-results">
    <main class="re-main re-res-main" :class="{ 'is-narrow': noResults }">
      <p v-if="flow.status === 'loading'" class="re-muted" role="status">Загружаю…</p>

      <section v-else-if="flow.status === 'fatal'" class="re-banner" role="alert">
        <span>{{ flow.fatalMessage }}</span>
        <button type="button" class="re-linkbtn" @click="flow.init()">Повторить</button>
      </section>

      <section v-else-if="flow.status === 'closed'" class="re-banner">Просмотр результатов закрыт</section>

      <slot v-else-if="noResults" name="empty" />

      <template v-else-if="flow.payload">
        <LiveLine :flow="flow" />
        <TableSwitch :flow="flow" />
        <div class="re-legend">
          <span v-for="item in legend" :key="item.text"><i v-if="item.cls" class="re-lg" :class="item.cls" />{{ item.text }}</span>
        </div>
        <ResultsTable :flow="flow" />
      </template>
    </main>

    <slot v-if="noResults" name="empty-action" />
    <MeBar v-else-if="flow.payload" :flow="flow" />

    <ParticipantSheet v-if="flow.sheet" :flow="flow" :edit-url="editUrl" />
    <div v-if="flow.toast" class="re-toast" role="status">{{ flow.toast }}</div>
  </div>
</template>
