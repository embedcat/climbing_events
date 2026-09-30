<script setup lang="ts">
import type { MatrixFlow } from './useMatrixFlow'

defineProps<{ flow: MatrixFlow }>()
</script>

<template>
  <div class="re-mx-keys">
    <span v-if="!flow.french"><i class="re-mx-sw v1">FL</i> flash <i class="re-mx-sw v2">RP</i> redpoint <i class="re-mx-sw bl" /> не сохранено</span>
    <span v-else><i class="re-mx-sw v1">2</i> топ <i class="re-mx-sw v2">1</i> зона <i class="re-mx-sw bl" /> не сохранено</span>

    <template v-if="!flow.french">
      <span><kbd>1</kbd> flash <kbd>2</kbd> redpoint <kbd>0</kbd> нет, курсор идёт дальше</span>
      <span><kbd>Пробел</kbd> или клик по выбранной — по кругу</span>
    </template>
    <template v-else>
      <span>цифры — номер попытки, <kbd>Enter</kbd> записать и дальше</span>
      <span><kbd>Esc</kbd> отменить набор</span>
      <span>топ без зоны → зона на той же попытке</span>
      <span>зона позже топа подсвечивается, сохранить нельзя</span>
    </template>

    <span><kbd>←</kbd><kbd>↑</kbd><kbd>→</kbd><kbd>↓</kbd> перейти</span>
    <span><kbd>/</kbd> найти участника по фамилии или PIN</span>
    <span><kbd>Ctrl</kbd>+<kbd>S</kbd> сохранить</span>
    <span class="re-mx-focus-hint">Кликните по ячейке, чтобы вводить с клавиатуры</span>
    <span class="re-mx-hint" aria-live="polite">{{ flow.hint }}</span>
  </div>
</template>
