<script setup lang="ts">
// Вкладка «Ввод»: PIN или анкета, плитки трасс, отправка. Закрытый ввод объясняет страница события.
import { computed, onMounted } from 'vue'
import ClosedScreen from '../event/ClosedScreen.vue'
import ActionBar from './ActionBar.vue'
import CheckSheet from './CheckSheet.vue'
import DoneCard from './DoneCard.vue'
import EntryForm from './EntryForm.vue'
import LockedCard from './LockedCard.vue'
import PinStep from './PinStep.vue'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow; canSeeResults: boolean; resultsHref: string }>()
defineEmits<{ results: [event: MouseEvent] }>()

onMounted(() => { void props.flow.ensureInit() })

/** Нижняя панель нужна, когда есть что нажать: отправить, исправить или посмотреть результаты. */
const showAction = computed(() => {
  const { step } = props.flow
  if (step === 'entry') return true
  if (step === 'done') return props.flow.updateAllowed || props.canSeeResults
  return step === 'locked' && props.canSeeResults
})
</script>

<template>
  <div class="re-fill re-entry">
    <main class="re-main is-narrow">
      <p v-if="flow.step === 'loading'" class="re-muted" role="status">Загружаю…</p>

      <section v-else-if="flow.step === 'fatal'" class="re-banner" role="alert">
        <span>{{ flow.fatalMessage }}</span>
        <button type="button" class="re-linkbtn" @click="flow.init()">Повторить</button>
      </section>

      <ClosedScreen
        v-else-if="flow.step === 'closed'" icon="lock" title="Ввод результатов закрыт"
        :lines="['Организатор закрыл ввод.', 'Не успели внести результат или нашли ошибку — подойдите к организатору: он внесёт результат по вашей карточке.']"
      />

      <PinStep v-else-if="flow.step === 'identify'" :flow="flow" />
      <EntryForm v-else-if="flow.step === 'entry'" :flow="flow" />
      <LockedCard v-else-if="flow.step === 'locked'" :flow="flow" />
      <DoneCard v-else-if="flow.step === 'done'" :flow="flow" />
    </main>

    <ActionBar
      v-if="showAction" :flow="flow" :can-see-results="canSeeResults" :results-href="resultsHref"
      @results="$emit('results', $event)"
    />
    <CheckSheet v-if="flow.sheetOpen" :flow="flow" />
    <div v-if="flow.toast" class="re-toast" role="status">{{ flow.toast }}</div>
  </div>
</template>
