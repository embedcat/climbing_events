<script setup lang="ts">
import type { Gender } from '../../api/entry'
import type { ResultsFlow } from './useResultsFlow'

defineProps<{ flow: ResultsFlow }>()

const GENDERS: Array<[Gender, string]> = [['MALE', 'М'], ['FEMALE', 'Ж']]
</script>

<template>
  <div class="re-gsel">
    <div class="re-seg" role="group" aria-label="Пол">
      <button
        v-for="[value, label] in GENDERS" :key="value" type="button"
        :aria-pressed="flow.gender === value"
        @click="flow.selectGender(value)"
      >{{ label }}</button>
    </div>
    <div v-if="flow.hasGroups" class="re-chips" role="group" aria-label="Группа">
      <button
        v-for="(name, index) in flow.payload!.groups" :key="index" type="button"
        :aria-pressed="flow.groupIndex === index"
        @click="flow.selectGroup(index)"
      >
        {{ name }}<span class="re-cnt">{{ flow.groupCounts[index] }}</span>
        <span v-if="flow.myGroupIndex === index" class="re-medot" title="Ваша группа" />
      </button>
    </div>
  </div>
</template>
