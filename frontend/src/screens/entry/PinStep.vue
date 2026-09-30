<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { EntryFlow } from './useEntryFlow'

const props = defineProps<{ flow: EntryFlow }>()
const input = ref<HTMLInputElement | null>(null)

onMounted(() => input.value?.focus({ preventScroll: true }))

function onInput(event: Event): void {
  const el = event.target as HTMLInputElement
  void props.flow.identify(el.value)
  // лишние символы (буквы, пятая цифра) сразу убираем из поля
  el.value = props.flow.pinInput
}
</script>

<template>
  <section class="re-ident">
    <h2 class="re-h2">Ввод результатов</h2>
    <p class="re-muted">Введите PIN с вашей карточки участника.</p>
    <label class="re-pin-label">
      <span class="re-sr-only">PIN</span>
      <input
        ref="input"
        class="re-pin"
        inputmode="numeric"
        pattern="[0-9]*"
        maxlength="4"
        autocomplete="off"
        placeholder="0000"
        aria-describedby="re-pin-msg"
        :value="flow.pinInput"
        :disabled="flow.pinBusy"
        @input="onInput"
      >
    </label>
    <p id="re-pin-msg" class="re-pin-msg" :class="{ 'is-error': flow.pinIsError }" aria-live="polite">
      {{ flow.pinMessage }}
    </p>
    <p class="re-muted re-small">PIN выдаёт организатор, он напечатан на карточке. Нет карточки — спросите организатора.</p>
  </section>
</template>
