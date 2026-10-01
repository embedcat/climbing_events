<script setup lang="ts">
// Вкладка «Результаты». Если организатор скрыл результаты или их ещё никто не внёс, объясняем это вместо пустой таблицы.
import { computed } from 'vue'
import ResultsScreen from '../results/ResultsScreen.vue'
import ClosedScreen from './ClosedScreen.vue'
import TabAction from './TabAction.vue'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const editUrl = (participantId: number): string => `/e/${props.app.eventId}/matrix/#p=${participantId}`

const empty = computed(() => (props.app.stage === 'done'
  ? { title: 'Результатов нет', lines: ['Участники не внесли результаты.'] }
  : {
    title: 'Результатов пока нет',
    lines: [`Они появятся ${props.app.page!.date_short}, как только участники начнут вносить результаты. Пока событие идёт, таблица обновляется сама.`],
  }))
</script>

<template>
  <div v-if="!app.resultsOpen" class="re-fill">
    <main class="re-main is-narrow">
      <ClosedScreen
        icon="lock" title="Результаты пока скрыты"
        :lines="['Организатор ещё не открыл результаты. Они появятся на этой вкладке, как только он их откроет.']"
      />
    </main>
    <TabAction tab="results" :app="app" narrow />
  </div>

  <ResultsScreen v-else :flow="app.results" :edit-url="editUrl">
    <template #empty>
      <ClosedScreen icon="clock" :title="empty.title" :lines="empty.lines" />
    </template>
    <template #empty-action>
      <TabAction tab="results" :app="app" narrow />
    </template>
  </ResultsScreen>
</template>
