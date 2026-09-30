<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { interpretKey } from '../../domain/matrixKeys'
import MatrixRow from './MatrixRow.vue'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow }>()

const wrap = ref<HTMLElement | null>(null)
const routes = computed(() => Array.from({ length: props.flow.routes }, (_, i) => i))

function onKeydown(event: KeyboardEvent): void {
  // только когда фокус на самой матрице: в поиске и других полях клавиши работают как обычно
  if (event.target !== wrap.value) return
  const action = interpretKey(event)
  if (!action) return
  event.preventDefault()
  props.flow.applyKey(action)
}

/** Курсор не должен прятаться под закреплёнными столбцами и шапкой: подкручиваем матрицу к нему. */
function ensureVisible(): void {
  const el = wrap.value
  const c = props.flow.cursor
  if (!el || !c) return
  const td = el.querySelector<HTMLElement>(`tr[data-id="${c.pid}"] td[data-r="${c.r}"][data-s="${c.sub}"]`)
  if (!td) return
  const width = (selector: string) => el.querySelector<HTMLElement>(selector)?.offsetWidth ?? 0
  const left = width('th.s-no') + width('th.s-name') + width('th.s-pin')
  const right = width('th.s-score') + width('th.s-place')
  const head = el.querySelector('thead')?.getBoundingClientRect().height ?? 0
  const x = td.offsetLeft
  const y = td.offsetTop
  if (x - left < el.scrollLeft) el.scrollLeft = x - left
  else if (x + td.offsetWidth + right > el.scrollLeft + el.clientWidth) el.scrollLeft = x + td.offsetWidth + right - el.clientWidth
  if (y - head < el.scrollTop) el.scrollTop = y - head
  else if (y + td.offsetHeight > el.scrollTop + el.clientHeight) el.scrollTop = y + td.offsetHeight - el.clientHeight
}

watch(() => props.flow.cursor, async () => { await nextTick(); ensureVisible() })
watch(() => props.flow.gridFocus, () => wrap.value?.focus({ preventScroll: true }))
onMounted(() => { ensureVisible(); void document.fonts?.ready.then(ensureVisible) })
</script>

<template>
  <div
    ref="wrap" class="re-mx-wrap" tabindex="0" aria-label="Матрица результатов: строки — участники, столбцы — трассы"
    @keydown="onKeydown"
  >
    <table class="re-mx" :class="{ 'is-fr': flow.french }">
      <colgroup>
        <col><col><col>
        <template v-for="r in routes" :key="r">
          <col
            v-for="s in (flow.french ? 2 : 1)" :key="s"
            :class="{ 'col-cur': flow.cursor?.r === r && (!flow.french || flow.cursor?.sub === s - 1) }"
          >
        </template>
        <col><col>
      </colgroup>
      <thead>
        <tr>
          <th class="stk s-no" rowspan="2">№</th>
          <th class="stk s-name" rowspan="2">Участник</th>
          <th class="stk s-pin" rowspan="2">PIN</th>
          <th
            v-for="r in routes" :key="r" class="rh" :class="{ hcur: flow.cursor?.r === r }" :colspan="flow.french ? 2 : 1"
            :title="`Трасса ${r + 1}`"
          >
            {{ r + 1 }}<span v-if="flow.french" class="tcnt">{{ flow.routeCounts[r] ? `${flow.routeCounts[r]}т` : '' }}</span>
          </th>
          <th class="stkr s-score" rowspan="2">Баллы<small>по сохранённым</small></th>
          <th class="stkr s-place" rowspan="2">Место<small>в группе</small></th>
        </tr>
        <tr>
          <template v-if="flow.french">
            <template v-for="r in routes" :key="r">
              <th class="sh" :class="{ hcur: flow.cursor?.r === r && flow.cursor?.sub === 0 }">Т</th>
              <th class="sh" :class="{ hcur: flow.cursor?.r === r && flow.cursor?.sub === 1 }">З</th>
            </template>
          </template>
          <template v-else>
            <th
              v-for="r in routes" :key="r" class="sh" :class="{ hcur: flow.cursor?.r === r }"
              title="Пролазов среди показанных участников"
            >{{ flow.routeCounts[r] }}</th>
          </template>
        </tr>
      </thead>
      <tbody>
        <MatrixRow
          v-for="(p, index) in flow.rows" :key="p.id" :flow="flow" :p="p" :index="index"
          :cursor="flow.cursor?.pid === p.id ? flow.cursor : null"
        />
        <tr v-if="!flow.rows.length">
          <td class="empty" :colspan="5 + flow.routes * (flow.french ? 2 : 1)">
            Под этот фильтр никто не попал. Выберите другой сет или группу.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
