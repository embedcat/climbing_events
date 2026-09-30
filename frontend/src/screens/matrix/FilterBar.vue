<script setup lang="ts">
import type { Gender } from '../../api/entry'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow }>()

const GENDERS: Array<['all' | Gender, string]> = [['all', 'Все'], ['MALE', 'М'], ['FEMALE', 'Ж']]

const setName = (index: number) => props.flow.event!.sets[index]?.name ?? ''
</script>

<template>
  <div class="re-mx-filters">
    <div v-if="flow.hasSets" class="re-mx-field">
      <span id="re-l-set" class="re-mx-label">Сет</span>
      <div class="re-mx-seg" role="group" aria-labelledby="re-l-set">
        <button type="button" :aria-pressed="flow.filters.set === -1" @click="flow.setFilter('set', -1)">Все</button>
        <button
          v-for="s in flow.event!.sets" :key="s.index" type="button" :aria-pressed="flow.filters.set === s.index"
          @click="flow.setFilter('set', s.index)"
        >{{ s.index + 1 }}<span class="t">{{ setName(s.index) }}</span></button>
      </div>
    </div>

    <div v-if="flow.hasGroups" class="re-mx-field">
      <span id="re-l-group" class="re-mx-label">Группа</span>
      <div class="re-mx-seg" role="group" aria-labelledby="re-l-group">
        <button type="button" :aria-pressed="flow.filters.group === -1" @click="flow.setFilter('group', -1)">Все</button>
        <button
          v-for="(name, index) in flow.event!.groups" :key="index" type="button"
          :aria-pressed="flow.filters.group === index" @click="flow.setFilter('group', index)"
        >{{ name }}</button>
      </div>
    </div>

    <div class="re-mx-field">
      <span id="re-l-gender" class="re-mx-label">Пол</span>
      <div class="re-mx-seg" role="group" aria-labelledby="re-l-gender">
        <button
          v-for="[value, label] in GENDERS" :key="value" type="button" :aria-pressed="flow.filters.gender === value"
          @click="flow.setFilter('gender', value)"
        >{{ label }}</button>
      </div>
    </div>

    <button
      type="button" class="re-mx-chip" :aria-pressed="flow.filters.missing"
      title="Показать только тех, у кого ещё нет результата" @click="flow.setFilter('missing', !flow.filters.missing)"
    >
      <span class="re-mx-dot is-missing" />Без результата: <b>{{ flow.missingCount }}</b>
    </button>
  </div>
</template>
