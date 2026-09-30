<script setup lang="ts">
import { computed } from 'vue'
import { formatTime } from '../../domain/format'
import FrenchList from './FrenchList.vue'
import RegistrationFields from './RegistrationFields.vue'
import TilesGrid from './TilesGrid.vue'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow }>()

const draftText = computed(() => {
  if (!props.flow.storageOk) return 'Браузер не даёт сохранить черновик'
  return props.flow.draftSavedAt
    ? `Черновик на телефоне · ${formatTime(props.flow.draftSavedAt)}`
    : 'Черновик сохраняется на телефоне'
})

const whoMeta = computed(() => {
  const who = props.flow.who
  if (!who) return ''
  const parts = [who.group, who.gender === 'FEMALE' ? 'Ж' : 'М']
  if (who.set) parts.push(`сет ${who.set_index + 1}, ${who.set}`)
  return parts.filter(Boolean).join(' · ')
})
</script>

<template>
  <RegistrationFields v-if="flow.withoutRegistration" :flow="flow" />
  <template v-else-if="flow.who">
    <section class="re-who">
      <div>
        <div class="re-who-name">{{ flow.who.last_name }} {{ flow.who.first_name }}</div>
        <div class="re-who-meta">{{ whoMeta }}</div>
      </div>
      <button type="button" class="re-linkbtn" @click="flow.notMe()">Не вы?</button>
    </section>
    <div v-if="flow.alreadyEntered && !flow.restoredAt" class="re-banner">
      Вы уже вводили результаты. Их можно исправить и отправить заново.
    </div>
  </template>

  <div v-if="flow.restoredAt" class="re-banner is-info">
    <span>Восстановлен черновик от {{ formatTime(flow.restoredAt) }}. Ничего не потерялось.</span>
    <button type="button" class="re-linkbtn" @click="flow.dropDraft()">Начать заново</button>
  </div>

  <div class="re-list-head">
    <h2 class="re-h2">Трассы</h2>
    <span class="re-draft-state">{{ draftText }}</span>
  </div>

  <FrenchList
    v-if="flow.french"
    :results="flow.results"
    :invalid="flow.invalidRoutes"
    @step="(index, kind, delta) => flow.changeAttempt(index, kind, delta)"
  />
  <TilesGrid v-else :results="flow.results" @toggle="(index) => flow.toggleTile(index)" />
</template>
