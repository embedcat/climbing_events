<script setup lang="ts">
import { onMounted } from 'vue'
import ActionBar from './ActionBar.vue'
import CheckSheet from './CheckSheet.vue'
import DoneCard from './DoneCard.vue'
import EntryForm from './EntryForm.vue'
import PinStep from './PinStep.vue'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow; resultsUrl: string }>()

onMounted(() => props.flow.init())
</script>

<template>
  <div class="re-screen re-entry">
    <main class="re-main">
      <p v-if="flow.step === 'loading'" class="re-muted" role="status">Загружаю…</p>

      <section v-else-if="flow.step === 'fatal'" class="re-banner" role="alert">
        <span>{{ flow.fatalMessage }}</span>
        <button type="button" class="re-linkbtn" @click="flow.init()">Повторить</button>
      </section>

      <section v-else-if="flow.step === 'closed'" class="re-banner">
        <span>Ввод результатов закрыт</span>
        <a class="re-linkbtn" :href="resultsUrl">Смотреть результаты</a>
      </section>

      <PinStep v-else-if="flow.step === 'identify'" :flow="flow" />
      <EntryForm v-else-if="flow.step === 'entry'" :flow="flow" />
      <DoneCard v-else-if="flow.step === 'done'" :flow="flow" />
    </main>

    <ActionBar v-if="flow.step === 'entry' || flow.step === 'done'" :flow="flow" :results-url="resultsUrl" />
    <CheckSheet v-if="flow.sheetOpen" :flow="flow" />
    <div v-if="flow.toast" class="re-toast" role="status">{{ flow.toast }}</div>
  </div>
</template>
