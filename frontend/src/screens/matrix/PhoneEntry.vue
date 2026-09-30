<script setup lang="ts">
import FilterBar from './FilterBar.vue'
import PhoneParticipant from './PhoneParticipant.vue'
import PhoneRoute from './PhoneRoute.vue'
import type { MatrixFlow, PhoneMode } from './useMatrixFlow'

defineProps<{ flow: MatrixFlow }>()

const MODES: Array<[PhoneMode, string]> = [['participant', 'По участнику'], ['route', 'По трассе']]
</script>

<template>
  <div class="re-ph">
    <template v-if="!(flow.phone.mode === 'participant' && flow.phoneParticipant)">
      <div class="re-mx-seg re-ph-modes" role="group" aria-label="Как переносите результаты">
        <button
          v-for="[value, label] in MODES" :key="value" type="button" :aria-pressed="flow.phone.mode === value"
          @click="flow.phone.mode = value"
        >{{ label }}</button>
      </div>
      <p class="re-ph-note">
        <template v-if="flow.phone.mode === 'participant'">Карточка участника: выберите его и отметьте все трассы.</template>
        <template v-else>Протокол трассы: выберите трассу и отметьте всех участников.</template>
      </p>
      <FilterBar :flow="flow" />
    </template>
    <PhoneParticipant v-if="flow.phone.mode === 'participant'" :flow="flow" />
    <PhoneRoute v-else :flow="flow" />
  </div>
</template>
