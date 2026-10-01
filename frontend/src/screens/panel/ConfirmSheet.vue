<script setup lang="ts">
// Окно подтверждения опасного действия: снизу на телефоне, по центру на компьютере.
import { onMounted, onUnmounted, ref } from 'vue'

defineProps<{ title: string, question: string, confirmLabel: string, danger: boolean, busy: boolean }>()
const emit = defineEmits<{ (e: 'confirm'): void, (e: 'cancel'): void }>()

const cancelButton = ref<HTMLButtonElement | null>(null)

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') emit('cancel')
}
onMounted(() => {
  cancelButton.value?.focus({ preventScroll: true })
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="re-sheet-host">
    <div class="re-sheet-bg" @click="emit('cancel')" />
    <div class="re-sheet re-p-confirm" role="alertdialog" aria-modal="true" aria-labelledby="re-p-confirm-title" aria-describedby="re-p-confirm-text">
      <div class="re-grabber" />
      <h3 id="re-p-confirm-title">{{ title }}</h3>
      <p id="re-p-confirm-text" class="re-p-hint">{{ question }}</p>
      <div class="re-sheet-actions">
        <button ref="cancelButton" type="button" class="re-btn" :disabled="busy" @click="emit('cancel')">Отмена</button>
        <button type="button" class="re-btn is-primary" :class="{ 'is-danger': danger }" :disabled="busy" @click="emit('confirm')">
          {{ busy ? 'Выполняю…' : confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
