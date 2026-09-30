<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { ResultRow } from '../../api/results'
import { cellView, formatPoints, formatScore, shortName } from '../../domain/standings'
import type { ResultsFlow } from './useResultsFlow'

const props = defineProps<{ flow: ResultsFlow }>()

const wrap = ref<HTMLElement | null>(null)

const payload = computed(() => props.flow.payload!)
const table = computed(() => props.flow.table)
const scoreType = computed(() => payload.value.event.score_type)
const showRoutes = computed(() => payload.value.display.is_view_full_results)
const routes = computed(() => (showRoutes.value ? payload.value.routes : []))
const ranked = computed(() => table.value?.ranked ?? [])
const waiting = computed(() => table.value?.waiting ?? [])
const hasGrades = computed(() => routes.value.some((r) => r.grade))
const hasColors = computed(() => routes.value.some((r) => r.color))

/** Нижняя строка: очки за RP по трассам, а во французской системе число топов. */
const footer = computed<'points' | 'tops' | null>(() => {
  if (!showRoutes.value) return null
  if (props.flow.french) return 'tops'
  return table.value?.route_points ? 'points' : null
})
const topsOn = (index: number) => ranked.value.filter((r) => (r.results[index]?.top ?? 0) > 0).length

const waitingTitle = computed(() => {
  const rows = waiting.value
  const verb = rows.length > 1 ? 'ввели' : rows[0]?.gender === 'FEMALE' ? 'ввела' : 'ввёл'
  return `Ещё не ${verb} результат`
})

const cell = (row: ResultRow, index: number) =>
  cellView(row.results[index], props.flow.french, row.counted[index] ?? true)
const groupEdge = (index: number) => index > 0 && index % 5 === 0

function rowClass(row: ResultRow) {
  return {
    'is-me': row.id === props.flow.meId,
    'is-wait': row.place === null,
    'is-changed': props.flow.changed.has(row.id),
  }
}

// ---- «это вы» уехало за край экрана? ----

let frame = 0
function measureMe(): void {
  const el = wrap.value
  const id = props.flow.meId
  if (!el || id === null) return
  const row = el.querySelector<HTMLElement>(`tbody tr[data-id="${id}"]`)
  if (!row) {
    props.flow.setMeRowVisible(false)
    return
  }
  const a = row.getBoundingClientRect()
  const b = el.getBoundingClientRect()
  const head = el.querySelector('thead')?.getBoundingClientRect().height ?? 0
  props.flow.setMeRowVisible(a.top >= b.top + head - 4 && a.bottom <= b.bottom + 4)
}

function onScroll(): void {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(measureMe)
}

function scrollToRow(id: number): void {
  const el = wrap.value
  const row = el?.querySelector<HTMLElement>(`tbody tr[data-id="${id}"]`)
  if (!el || !row) return
  el.scrollTop = Math.max(0, row.offsetTop - el.clientHeight / 2 + row.offsetHeight / 2)
  row.classList.remove('is-flash')
  void row.offsetWidth // перезапускаем анимацию
  row.classList.add('is-flash')
  measureMe()
}

watch(() => props.flow.focusRow, async (request) => {
  if (!request) return
  await nextTick()
  scrollToRow(request.id)
})
// сменили таблицу: начинаем сверху и слева, как при первом показе
watch(table, async () => {
  if (wrap.value) { wrap.value.scrollTop = 0; wrap.value.scrollLeft = 0 }
  await nextTick()
  measureMe()
})
watch(() => [props.flow.meId, props.flow.payload], async () => {
  await nextTick()
  measureMe()
})

onMounted(() => {
  measureMe()
  // шрифты меняют высоту строк
  void document.fonts?.ready.then(measureMe)
})
onUnmounted(() => cancelAnimationFrame(frame))
</script>

<template>
  <div ref="wrap" class="re-tbl-wrap" @scroll.passive="onScroll">
    <table class="re-rt" :class="{ 'is-fr': flow.french }">
      <thead>
        <tr>
          <th class="s1">#</th>
          <th class="s2">Участник</th>
          <th
            v-for="(route, index) in routes" :key="route.number" class="c" :class="{ g: groupEdge(index) }"
            :title="route.grade ? `Трасса ${route.number}, категория ${route.grade}` : undefined"
          >
            {{ route.number }}
            <span v-if="hasGrades" class="re-rgrade">{{ route.grade }}</span>
            <span v-if="hasColors" class="re-rcolor" :style="{ background: route.color ?? 'transparent' }" />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in ranked" :key="row.id" :data-id="row.id" :class="rowClass(row)"
          @click="flow.openPerson(row.id)"
        >
          <td class="s1">{{ row.place }}</td>
          <td class="s2">
            <button type="button" class="re-nbtn" @click.stop="flow.openPerson(row.id)">
              <span class="n">{{ shortName(row) }}</span>
              <span class="v">
                {{ formatScore(row, scoreType) }}
                <span v-if="flow.deltas.get(row.id)" class="re-delta" :class="flow.deltas.get(row.id)! > 0 ? 'is-up' : 'is-down'">
                  {{ flow.deltas.get(row.id)! > 0 ? '▲' : '▼' }}{{ Math.abs(flow.deltas.get(row.id)!) }}
                </span>
              </span>
            </button>
          </td>
          <td
            v-for="(_, index) in routes" :key="index" class="c" :class="[cell(row, index).kind && `k-${cell(row, index).kind}`, { g: groupEdge(index), nc: cell(row, index).dim }]"
          >{{ cell(row, index).text }}</td>
        </tr>

        <template v-if="waiting.length">
          <tr class="sep">
            <td class="s1" />
            <td class="s2">{{ waitingTitle }}</td>
            <td :colspan="routes.length || 1" />
          </tr>
          <tr
            v-for="row in waiting" :key="row.id" :data-id="row.id" :class="rowClass(row)"
            @click="flow.openPerson(row.id)"
          >
            <td class="s1">—</td>
            <td class="s2">
              <button type="button" class="re-nbtn" @click.stop="flow.openPerson(row.id)">
                <span class="n">{{ shortName(row) }}</span>
                <span class="v">нет результата</span>
              </button>
            </td>
            <td v-for="(_, index) in routes" :key="index" class="c" :class="{ g: groupEdge(index) }" />
          </tr>
        </template>
      </tbody>
      <tfoot v-if="footer">
        <tr>
          <td class="s1" />
          <td class="s2">{{ footer === 'tops' ? 'Топов' : 'Очков за RP' }}</td>
          <td v-for="(_, index) in routes" :key="index" class="c" :class="{ g: groupEdge(index) }">
            <template v-if="footer === 'tops'">{{ topsOn(index) }}</template>
            <template v-else>{{ table!.route_points![index] && table!.route_points![index].redpoint ? formatPoints(table!.route_points![index].redpoint) : '—' }}</template>
          </td>
        </tr>
      </tfoot>
    </table>
    <p v-if="!ranked.length && !waiting.length" class="re-empty">В этой группе пока нет участников.</p>
  </div>
</template>
