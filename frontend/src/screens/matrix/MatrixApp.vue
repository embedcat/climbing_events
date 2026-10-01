<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { isSaveShortcut, isSlash } from '../../domain/matrixKeys'
import KeyLegend from './KeyLegend.vue'
import MatrixGrid from './MatrixGrid.vue'
import MatrixToolbar from './MatrixToolbar.vue'
import PhoneEntry from './PhoneEntry.vue'
import StatusBar from './StatusBar.vue'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{
  flow: MatrixFlow
  resultsUrl: string
  manageUrl: string
  /** подменяется в тестах: ширина экрана, с которой показываем матрицу вместо шагов */
  wideQuery?: string
}>()

const root = ref<HTMLElement | null>(null)
const wide = ref(true)
let media: MediaQueryList | undefined

const SYSTEMS: Record<string, string> = {
  PROP: 'PROP, от количества пролазов',
  FR: 'французская система',
  SUM: 'сумма баллов',
  TBL: 'по таблице категорий',
  NUM: 'по количеству Всего/Flash',
}

const meta = computed(() => {
  const e = props.flow.event
  if (!e) return ''
  return `${props.flow.participants.length} участников · ${e.routes_num} трасс · ${SYSTEMS[e.score_type] ?? e.score_type}`
})

const networkFailure = computed(() => props.flow.saveError?.isNetwork ?? false)

/** Экран занимает остаток окна: матрица прокручивается внутри, панель сохранения остаётся внизу. */
function measure(): void {
  const el = root.value
  if (el) el.style.setProperty('--re-top', `${Math.round(el.getBoundingClientRect().top + window.scrollY + 8)}px`)
}

function updateWide(): void {
  if (media) wide.value = media.matches
}

function onDocumentKeydown(event: KeyboardEvent): void {
  if (isSaveShortcut(event)) {
    event.preventDefault()
    void props.flow.save()
    return
  }
  const tag = (document.activeElement as HTMLElement | null)?.tagName
  if (isSlash(event) && tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT' && !(document.activeElement as HTMLElement | null)?.classList.contains('re-mx-wrap')) {
    event.preventDefault()
    props.flow.searchFocus++
  }
}

// закрытие вкладки с несохранённым: черновик в браузере остаётся, но предупредить не лишне
function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (props.flow.stats.cells && props.flow.storageOk === false) event.preventDefault()
}

onMounted(() => {
  measure()
  window.addEventListener('resize', measure)
  document.addEventListener('keydown', onDocumentKeydown)
  window.addEventListener('beforeunload', onBeforeUnload)
  media = window.matchMedia?.(props.wideQuery ?? '(min-width: 900px)')
  if (media) {
    wide.value = media.matches
    media.addEventListener('change', updateWide)
  }
  void props.flow.init()
})
onUnmounted(() => {
  window.removeEventListener('resize', measure)
  document.removeEventListener('keydown', onDocumentKeydown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  media?.removeEventListener('change', updateWide)
  props.flow.dispose()
})
</script>

<template>
  <div ref="root" class="re-screen re-matrix" :class="{ 'is-wide': wide }">
    <header class="re-mx-top">
      <div>
        <h1 class="re-mx-title">Ввод результатов</h1>
        <span class="re-mx-meta">{{ meta }}</span>
      </div>
      <nav class="re-mx-links" aria-label="Связанные страницы">
        <a :href="resultsUrl">Результаты</a>
        <a :href="manageUrl">‹ Панель события</a>
      </nav>
    </header>

    <p v-if="flow.status === 'loading'" class="re-muted" role="status">Загружаю…</p>

    <section v-else-if="flow.status === 'fatal'" class="re-banner" role="alert">
      <span>{{ flow.fatalMessage }}</span>
      <button type="button" class="re-linkbtn" @click="flow.init()">Повторить</button>
    </section>

    <section v-else-if="flow.status === 'forbidden'" class="re-banner" role="alert">
      Массовый ввод доступен только организатору события. Войдите под своей учётной записью.
    </section>

    <template v-else-if="flow.payload">
      <MatrixToolbar v-if="wide" :flow="flow" />
      <KeyLegend v-if="wide" :flow="flow" />

      <div v-if="flow.restoredCount && flow.stats.cells" class="re-banner is-info">
        <span>Восстановлен несохранённый черновик: {{ flow.stats.cells }} {{ flow.stats.cells === 1 ? 'результат' : 'результатов' }}.</span>
        <span class="re-mx-banner-actions">
          <button type="button" class="re-mx-btn is-small" @click="flow.save()">Сохранить</button>
          <button type="button" class="re-mx-btn is-small" @click="flow.discard()">Отбросить</button>
        </span>
      </div>

      <div v-if="flow.saveError" class="re-banner is-error" role="alert">
        <span v-if="networkFailure">Не удалось сохранить: нет связи с сервером. Изменения остались в черновике в этом браузере.</span>
        <span v-else>{{ flow.saveError.message }}</span>
        <span class="re-mx-banner-actions">
          <button v-if="flow.errorTarget" type="button" class="re-mx-btn is-small" @click="flow.goToProblem()">Перейти</button>
          <button v-if="networkFailure" type="button" class="re-mx-btn is-small" @click="flow.save()">Повторить</button>
        </span>
      </div>

      <MatrixGrid v-if="wide" :flow="flow" />
      <PhoneEntry v-else :flow="flow" />
      <StatusBar :flow="flow" :compact="!wide" />
    </template>
  </div>
</template>
