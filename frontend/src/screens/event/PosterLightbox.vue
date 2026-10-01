<script setup lang="ts">
// Афиша на весь экран: нажатие на неё в «Инфо».
import { onMounted, onUnmounted, ref } from 'vue'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()
const closeButton = ref<HTMLButtonElement | null>(null)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.app.closePoster()
}
onMounted(() => {
  closeButton.value?.focus({ preventScroll: true })
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="re-lightbox" role="dialog" aria-modal="true" aria-label="Афиша" @click="app.closePoster()">
    <div class="re-lb-inner">
      <img :src="app.page!.poster!" :alt="app.page!.title">
      <button ref="closeButton" type="button" class="re-btn" @click="app.closePoster()">Закрыть</button>
    </div>
  </div>
</template>
