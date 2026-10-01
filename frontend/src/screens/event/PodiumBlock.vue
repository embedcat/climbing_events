<script setup lang="ts">
// Призёры завершённого события: первые три места в каждой группе у мужчин и женщин.
import { shortPersonName } from '../../domain/people'
import type { EventApp } from './useEventApp'

defineProps<{ app: EventApp }>()

const COLUMNS = [
  { key: 'male', title: 'Мужчины' },
  { key: 'female', title: 'Женщины' },
] as const
</script>

<template>
  <section v-if="app.page!.podium.length" class="re-block">
    <h3 class="re-bh">Призёры</h3>
    <div class="re-pod-list">
      <div v-for="group in app.page!.podium" :key="group.group_index ?? 'all'" class="re-pod">
        <div v-if="group.group" class="re-pod-g">{{ group.group }}</div>
        <div class="re-pod-cols">
          <div v-for="column in COLUMNS" :key="column.key">
            <div class="re-pod-h">{{ column.title }}</div>
            <ol>
              <li v-for="winner in group[column.key]" :key="winner.id" :class="{ 'is-me': app.isMe(winner.id) }">
                <b>{{ winner.place }}</b>{{ shortPersonName(winner) }}
              </li>
              <li v-if="!group[column.key].length" class="re-hint">—</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
