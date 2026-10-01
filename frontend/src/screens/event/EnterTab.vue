<script setup lang="ts">
// Вкладка «Ввод». Пока ввод открыт, это форма ввода результатов. Закрытый ввод объясняем, а не пишем одно «закрыт»:
// событие завершено, ввод закрыт организатором или ещё не открыт.
import { computed } from 'vue'
import EntryScreen from '../entry/EntryScreen.vue'
import ClosedScreen from './ClosedScreen.vue'
import TabAction from './TabAction.vue'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const closed = computed(() => {
  const page = props.app.page!
  switch (props.app.stage) {
    case 'over':
      return {
        icon: 'lock' as const,
        title: 'Ввод результатов закрыт',
        lines: ['Организатор закрыл ввод.', 'Не успели внести результат или нашли ошибку — подойдите к организатору: он внесёт результат по вашей карточке.'],
      }
    case 'done':
      return { icon: 'lock' as const, title: 'Соревнование завершено', lines: ['Ввод результатов закрыт. Исправить результат может только организатор.'] }
    default:
      return {
        icon: 'clock' as const,
        title: 'Ввод откроется в день соревнований',
        lines: [page.is_without_registration
          ? `${page.date_short}, после своего сета, откройте эту вкладку: имя, группу и сет укажете вместе с результатами. Регистрироваться заранее не нужно.`
          : `${page.date_short} организатор откроет ввод. После своего сета откройте эту вкладку и введите PIN с карточки участника.`],
      }
  }
})
</script>

<template>
  <EntryScreen
    v-if="app.stage === 'live'" :flow="app.entry" :can-see-results="app.resultsOpen"
    :results-href="app.router.href('results')" @results="app.navigate($event, 'results')"
  />
  <div v-else class="re-fill">
    <main class="re-main is-narrow">
      <ClosedScreen :icon="closed.icon" :title="closed.title" :lines="closed.lines" />
    </main>
    <TabAction tab="enter" :app="app" narrow />
  </div>
</template>
