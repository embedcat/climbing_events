<script setup lang="ts">
// Карточка участника из списка. Организатору в ней видны ещё PIN, контакты и оплата, и ссылка на правку анкеты.
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { Person } from '../../api/event'
import { isDesktop } from '../../domain/device'
import { genderLabel } from '../../domain/standings'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp; person: Person }>()

const closeButton = ref<HTMLButtonElement | null>(null)

const page = computed(() => props.app.page!)
const isMe = computed(() => props.app.isMe(props.person.id))
const name = computed(() => `${props.person.last_name} ${props.person.first_name}`)
const facts = computed(() => [
  props.person.birth_year ? `${props.person.birth_year} г. р.` : '',
  props.person.grade,
  props.person.city,
  props.person.team ? `«${props.person.team}»` : '',
].filter(Boolean).join(' · '))
const group = computed(() => [props.app.groupName(props.person.group_index), genderLabel(props.person.gender)]
  .filter(Boolean).join(', '))
const set = computed(() => `${props.person.set_index + 1}, ${props.app.setName(props.person.set_index)}`)
const payPill = computed(() => {
  if (props.person.paid) return { cls: 'is-ok', text: 'оплачен' }
  return { cls: 'is-due', text: 'не оплачен' }
})
const myPill = computed(() => ({
  paid: { cls: 'is-ok', text: 'оплачен' },
  pending: { cls: 'is-wait', text: 'проверяем платёж' },
  due: { cls: 'is-due', text: 'не оплачен' },
}[props.app.payStatus]))

function remember(): void {
  const p = props.person
  props.app.rememberPerson({
    id: p.id, first_name: p.first_name, last_name: p.last_name, gender: p.gender,
    group_index: p.group_index, set_index: p.set_index,
  })
  props.app.people.closeSheet()
  props.app.showToast('Запомнили. На вкладке «Инфо» будет ваша карточка.')
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Escape') props.app.people.closeSheet()
}
onMounted(() => {
  closeButton.value?.focus({ preventScroll: true })
  document.addEventListener('keydown', onKeydown)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="re-sheet-host">
    <div class="re-sheet-bg" @click="app.people.closeSheet()" />
    <div class="re-sheet" role="dialog" aria-modal="true" aria-labelledby="re-person-title">
      <div class="re-grabber" />
      <h3 id="re-person-title">{{ name }}</h3>
      <p v-if="facts" class="re-facts-line">{{ facts }}</p>

      <div class="re-kv"><span>{{ page.groups.length ? 'Группа' : 'Зачёт' }}</span><b>{{ group }}</b></div>
      <div v-if="page.sets.length" class="re-kv"><span>Сет</span><b>{{ set }}</b></div>
      <div v-if="person.place" class="re-kv"><span>Место</span><b>{{ person.place }} из {{ person.place_of }}</b></div>
      <div v-if="isMe && page.pay.is_allowed" class="re-kv">
        <span>Взнос</span><span class="re-pill" :class="myPill.cls">{{ myPill.text }}</span>
      </div>

      <template v-if="app.people.canManage">
        <div class="re-kv"><span>PIN</span><b>{{ person.pin ?? '—' }}</b></div>
        <div v-if="person.phone" class="re-kv"><span>Телефон</span><b>{{ person.phone }}</b></div>
        <div v-if="person.email" class="re-kv"><span>Email</span><b>{{ person.email }}</b></div>
        <div v-if="page.pay.is_allowed" class="re-kv">
          <span>Взнос</span><span class="re-pill" :class="payPill.cls">{{ payPill.text }}</span>
        </div>
        <div class="re-kv"><span>Результат</span><b>{{ person.entered ? 'внесён' : 'не внесён' }}</b></div>
      </template>

      <template v-if="isMe">
        <p class="re-is-me">
          Это вы. {{ isDesktop ? 'Браузер' : 'Телефон' }} помнит вас для этого события, карточка «Вы» — на вкладке «Инфо».
        </p>
        <div class="re-sheet-actions is-one">
          <button ref="closeButton" type="button" class="re-btn" @click="app.people.closeSheet()">Закрыть</button>
        </div>
      </template>
      <div v-else class="re-sheet-actions">
        <button ref="closeButton" type="button" class="re-btn" @click="app.people.closeSheet()">Закрыть</button>
        <button type="button" class="re-btn is-primary" @click="remember">Это я, запомнить</button>
      </div>
      <a v-if="app.people.canManage" class="re-linkbtn re-edit-link" :href="`/e/${app.eventId}/p/${person.id}/`">
        Править анкету (организатор)
      </a>
    </div>
  </div>
</template>
