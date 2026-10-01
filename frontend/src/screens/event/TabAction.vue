<script setup lang="ts">
// Главное действие экрана, закреплённое внизу. Что на кнопке, зависит от этапа события и от того, помнит ли браузер
// участника: «Зарегистрироваться», «Оплатить», «Внести результат», «Результаты».
import { computed } from 'vue'
import { formatMoney } from './usePay'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp; tab: 'info' | 'people' | 'enter' | 'results'; narrow?: boolean }>()

type Model =
  | { kind: 'reg'; sub: string }
  | { kind: 'pay' }
  | { kind: 'live' }
  | { kind: 'enter' }
  | { kind: 'results' }
  | null

const model = computed<Model>(() => {
  const app = props.app
  const me = app.me
  const regBar = (sub: string): Model => ({ kind: 'reg', sub })
  const needsPay = !!me && !!app.page?.pay.is_allowed && !me.paid && app.payStatus !== 'pending'
  const finished = app.stage === 'over' || app.stage === 'done'
  switch (props.tab) {
    case 'info':
      if (app.stage === 'live') return app.resultsOpen ? { kind: 'live' } : { kind: 'enter' }
      if (finished) return app.resultsOpen ? { kind: 'results' } : null
      if (needsPay) return { kind: 'pay' }
      return app.regOpen && !me ? regBar(app.freeText) : null
    case 'people':
      return app.regOpen && !me ? regBar('нет вас в списке? зарегистрируйтесь') : null
    case 'enter':
      if (finished && app.resultsOpen) return { kind: 'results' }
      return app.regOpen && !me ? regBar(app.freeText) : null
    default:
      if (app.stage === 'live' && !app.resultsOpen) return { kind: 'enter' }
      return app.regOpen && !me ? regBar(app.freeText) : null
  }
})

const price = computed(() => {
  const value = props.app.page?.pay.price
  return value ? `${formatMoney(value)} ₽` : ''
})
const payPrice = computed(() => {
  const value = props.app.priceOf(props.app.me?.reg_type_index ?? 0)
  return value ? `${formatMoney(value)} ₽` : ''
})
const resultsLabel = computed(() => (props.app.stage === 'done' ? 'Итоговые результаты' : 'Результаты'))
const href = (screen: 'reg' | 'pay' | 'enter' | 'results') => props.app.router.href(
  screen, screen === 'pay' && props.app.me?.id != null ? { p: props.app.me.id } : undefined)
const open = (event: MouseEvent, screen: 'reg' | 'pay' | 'enter' | 'results') => props.app.navigate(
  event, screen, screen === 'pay' && props.app.me?.id != null ? { query: { p: props.app.me.id } } : undefined)
</script>

<template>
  <footer v-if="model" class="re-action" :class="{ 'is-narrow': narrow }">
    <div v-if="model.kind === 'reg'" class="re-act-row">
      <div class="re-sum">
        <span v-if="price" class="re-s"><b>{{ price }}</b></span>
        <span class="re-of">{{ model.sub }}</span>
      </div>
      <a class="re-btn is-primary" :href="href('reg')" @click="open($event, 'reg')">Зарегистрироваться</a>
    </div>

    <div v-else-if="model.kind === 'pay'" class="re-act-row">
      <div class="re-sum">
        <span v-if="payPrice" class="re-s"><b>{{ payPrice }}</b></span>
        <span class="re-of">взнос не оплачен</span>
      </div>
      <a class="re-btn is-primary" :href="href('pay')" @click="open($event, 'pay')">Оплатить</a>
    </div>

    <div v-else-if="model.kind === 'live'" class="re-act-row is-two">
      <a class="re-btn" :href="href('results')" @click="open($event, 'results')">Результаты</a>
      <a class="re-btn is-primary" :href="href('enter')" @click="open($event, 'enter')">Внести результат</a>
    </div>

    <a v-else-if="model.kind === 'enter'" class="re-btn is-primary is-wide" :href="href('enter')" @click="open($event, 'enter')">
      Внести результат
    </a>

    <a v-else class="re-btn is-primary is-wide" :href="href('results')" @click="open($event, 'results')">{{ resultsLabel }}</a>
  </footer>
</template>
