<script setup lang="ts">
import { computed } from 'vue'
import type { MatrixParticipant } from '../../api/matrix'
import type { Cursor } from '../../domain/matrix'
import type { MatrixFlow } from './useMatrixFlow'

const props = defineProps<{ flow: MatrixFlow; p: MatrixParticipant; index: number; cursor: Cursor | null }>()

const subs = computed(() => (props.flow.french ? 2 : 1))
const routes = computed(() => Array.from({ length: props.flow.routes }, (_, i) => i))

const meta = computed(() => {
  const { event } = props.flow
  const parts: string[] = []
  if (event!.groups.length > 1) parts.push(event!.groups[props.p.group_index] ?? '')
  parts.push(props.p.gender === 'FEMALE' ? 'Ж' : 'М')
  if (event!.sets.length > 1) parts.push(`сет ${props.p.set_index + 1}`)
  return parts.filter(Boolean).join(' · ')
})

const dirty = computed(() => props.flow.rowDirty(props.p.id))
const delta = computed(() => props.flow.deltas.get(props.p.id))
const flashing = computed(() => props.flow.flash?.pid === props.p.id)

function classes(route: number, sub: 0 | 1): string[] {
  const v = props.flow.valueAt(props.p, route)
  const out = ['c']
  if (props.flow.french) {
    out.push(`sub${sub}`)
    const n = sub === 0 ? v.top : v.zone
    out.push(n > 0 ? (sub === 0 ? 'ft' : 'fz') : 'v0')
    if (sub === 1 && v.top > 0 && v.zone > v.top) out.push('bad')
  } else {
    out.push(`v${v.top}`)
  }
  if ((route + 1) % 5 === 0 && sub === subs.value - 1) out.push('g5')
  if (props.flow.isDirty(props.p.id, route)) out.push('dirty')
  const c = props.cursor
  if (c && c.r === route && c.sub === sub) {
    out.push('cur')
    if (props.flow.edit !== null) out.push('editing')
  }
  return out
}

function text(route: number, sub: 0 | 1): string {
  const c = props.cursor
  if (c && c.r === route && c.sub === sub && props.flow.edit !== null) return props.flow.edit
  const v = props.flow.valueAt(props.p, route)
  if (props.flow.french) {
    const n = sub === 0 ? v.top : v.zone
    return n > 0 ? String(n) : ''
  }
  return v.top === 1 ? 'FL' : v.top === 2 ? 'RP' : ''
}

const isEditing = (route: number, sub: 0 | 1): boolean =>
  !!props.cursor && props.cursor.r === route && props.cursor.sub === sub && props.flow.edit !== null

const title = (route: number, sub: 0 | 1): string | undefined => {
  const v = props.flow.valueAt(props.p, route)
  return props.flow.french && sub === 1 && v.top > 0 && v.zone > v.top ? 'Зона позже топа. Проверьте попытки.' : undefined
}
</script>

<template>
  <tr :data-id="p.id" :class="{ 'row-cur': !!cursor, flash: flashing }">
    <td class="stk s-no">{{ index + 1 }}</td>
    <td class="stk s-name" @mousedown.prevent="flow.clickParticipant(p.id)">
      <div class="nm">
        <span class="re-mx-dot" :class="{ 'is-missing': !p.is_entered_result && !dirty }" />
        <span class="nmt">{{ p.last_name }} {{ p.first_name }}</span>
      </div>
      <div class="meta">
        <span>{{ meta }}</span>
        <span v-if="!p.is_entered_result && !dirty" class="miss">нет результата</span>
      </div>
    </td>
    <td class="stk s-pin" @mousedown.prevent="flow.clickParticipant(p.id)">{{ p.pin ?? '' }}</td>
    <template v-for="r in routes" :key="r">
      <td
        v-for="s in subs" :key="s" :data-r="r" :data-s="s - 1" :class="classes(r, (s - 1) as 0 | 1)"
        :title="title(r, (s - 1) as 0 | 1)" @mousedown.prevent="flow.clickCell(p.id, r, (s - 1) as 0 | 1)"
      >{{ text(r, (s - 1) as 0 | 1) }}<span v-if="isEditing(r, (s - 1) as 0 | 1)" class="caret" /></td>
    </template>
    <td class="stkr s-score" :class="{ stale: dirty }" :title="dirty ? 'Пересчитается после сохранения' : undefined">
      {{ p.is_entered_result ? p.score_view : '—' }}
    </td>
    <td class="stkr s-place">
      {{ p.place ?? '—' }}<span v-if="delta" class="delta" :class="delta > 0 ? 'up' : 'down'">{{ delta > 0 ? '▲' : '▼' }}{{ Math.abs(delta) }}</span>
    </td>
  </tr>
</template>
