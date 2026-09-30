<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { plural } from '../../domain/format'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow; compact?: boolean }>()

const armed = ref(false)
let timer: ReturnType<typeof setTimeout> | undefined

const problem = computed(() => {
  const bad = props.flow.invalid
  if (!bad.length) return null
  const p = props.flow.participants.find((x) => x.id === bad[0].pid)
  return { route: bad[0].r + 1, name: p ? `${p.last_name} ${p.first_name}` : '', more: bad.length - 1 }
})

const dirtyText = computed(() => {
  const { cells, participants } = props.flow.stats
  return `${cells} ${plural(cells, 'результат', 'результата', 'результатов')} у ` +
    `${participants} ${plural(participants, 'участника', 'участников', 'участников')}`
})

const saveLabel = computed(() => {
  if (props.flow.saving) return 'Сохраняю…'
  return props.flow.stats.cells ? `Сохранить · ${props.flow.stats.cells}` : 'Сохранить'
})

/** Отмена стоит дорого: первое нажатие только просит подтвердить, второе в течение трёх секунд отменяет. */
function discard(): void {
  if (!armed.value) {
    armed.value = true
    timer = setTimeout(() => { armed.value = false }, 3000)
    return
  }
  clearTimeout(timer)
  armed.value = false
  props.flow.discard()
}

onUnmounted(() => clearTimeout(timer))
</script>

<template>
  <footer class="re-mx-bar" :class="{ 'is-compact': compact }">
    <div
      class="re-mx-status" :class="{ 'is-ok': !flow.stats.cells && flow.savedMessage, 'is-err': !!problem && !flow.saving }"
      aria-live="polite"
    >
      <template v-if="flow.saving">Отправляю на сервер…</template>
      <template v-else-if="problem">
        <b>Нельзя сохранить:</b> зона позже топа, трасса {{ problem.route }} у участника {{ problem.name }}<template v-if="problem.more">
          и ещё {{ problem.more }}</template>.
        <button type="button" class="re-mx-goto" @click="flow.goToProblem()">Перейти</button>
      </template>
      <template v-else-if="!flow.stats.cells">{{ flow.savedMessage || 'Все изменения сохранены' }}</template>
      <template v-else>
        <b>Не сохранено:</b> {{ dirtyText }}<template v-if="flow.storageOk"> · черновик хранится в этом браузере</template>
        <template v-else> · браузер не даёт сохранить черновик</template>
      </template>
    </div>
    <div class="re-mx-actions">
      <button type="button" class="re-mx-btn" :disabled="flow.refreshing || flow.saving" @click="flow.refresh()">{{ compact ? 'Обновить' : 'Обновить данные' }}</button>
      <button
        type="button" class="re-mx-btn" :class="{ 'is-danger': armed }" :disabled="!flow.stats.cells || flow.saving"
        @click="discard"
      >{{ armed ? `Точно отменить ${flow.stats.cells}?` : compact ? 'Отменить' : 'Отменить изменения' }}</button>
      <button type="button" class="re-mx-btn is-primary" :disabled="!flow.canSave" @click="flow.save()">{{ saveLabel }}</button>
    </div>
  </footer>
</template>
