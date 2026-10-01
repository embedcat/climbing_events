<script setup lang="ts">
// Карточка события на главной: афиша, этап, дата и место, кнопки по этапу.
import { computed } from 'vue'
import type { SiteEventCard } from '../../api/site'
import { cardActions, eventUrl, STAGE_TAG } from '../../domain/siteEvents'
import { DEFAULT_POSTER } from './context'

const props = defineProps<{ card: SiteEventCard, authenticated: boolean }>()

const tag = computed(() => STAGE_TAG[props.card.stage])
const TAG_CLASS = { '': '', ok: 'is-ok', live: 'is-ok is-live', warn: 'is-warn' } as const
const tagClass = computed(() => TAG_CLASS[tag.value.kind])
const actions = computed(() => cardActions(props.card))
const meta = computed(() => [props.card.date, props.card.gym].filter(Boolean).join(' · '))
</script>

<template>
  <article class="re-h-ev" :class="{ 'is-past': card.stage === 'done' }">
    <a class="re-h-poster" :href="eventUrl(card.id)" tabindex="-1" aria-hidden="true">
      <img :src="card.poster || DEFAULT_POSTER" alt="" loading="lazy">
    </a>
    <div class="re-h-main">
      <div class="re-h-tags">
        <span class="re-tag" :class="tagClass">{{ tag.label }}</span>
        <span v-if="card.mine && authenticated" class="re-tag">ваше</span>
      </div>
      <h3 class="re-h-title"><a :href="eventUrl(card.id)">{{ card.title }}</a></h3>
      <div class="re-h-meta">{{ meta }}</div>
      <p v-if="card.short_description" class="re-h-desc">{{ card.short_description }}</p>
      <div class="re-h-btns">
        <a v-for="action in actions" :key="action.label" class="re-h-btn" :class="{ 'is-primary': action.primary }" :href="action.href">
          {{ action.label }}
        </a>
      </div>
    </div>
  </article>
</template>
