<script setup lang="ts">
// После регистрации: PIN (если организатор его показывает), статус оплаты и что дальше.
import { computed } from 'vue'
import { onDevice } from '../../domain/device'
import { formatMoney } from './usePay'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const page = computed(() => props.app.page!)
const result = computed(() => props.app.registration.result!)
const participant = computed(() => result.value.participant)
const name = computed(() => `${participant.value.last_name} ${participant.value.first_name}`)
const fee = computed(() => props.app.priceOf(participant.value.reg_type_index))
const needsPay = computed(() => page.value.pay.is_allowed && !result.value.paid)

const goPay = (event: MouseEvent) => props.app.navigate(event, 'pay', { query: { p: participant.value.id } })
const payHref = computed(() => props.app.router.href('pay', { p: participant.value.id }))

function another(event: MouseEvent): void {
  props.app.registration.registerAnother()
  props.app.navigate(event, 'reg')
}
</script>

<template>
  <div class="re-fill">
    <main class="re-main is-narrow">
      <section class="re-done">
        <svg class="re-done-mark" viewBox="0 0 48 48" aria-hidden="true">
          <circle cx="24" cy="24" r="22" />
          <path d="M14 24.5l7 7 13-14" />
        </svg>
        <h2>Вы зарегистрированы</h2>
        <p class="re-muted">{{ name }} · {{ app.meta(participant) }}</p>

        <div v-if="result.pin !== null" class="re-card is-center">
          <span class="re-pc-label">Ваш PIN</span>
          <span class="re-pin-big">{{ result.pin }}</span>
          <p>Нужен, чтобы вносить результаты. Его же напечатают на карточке участника, которую выдаст организатор.</p>
        </div>
        <div v-else class="re-card is-center">
          <p>PIN для ввода результатов будет на карточке участника. Карточку выдаст организатор в день соревнований.</p>
        </div>

        <div v-if="page.pay.is_allowed" class="re-card">
          <div v-if="fee" class="re-kv"><span>Стартовый взнос</span><b>{{ formatMoney(fee) }} ₽</b></div>
          <div class="re-kv">
            <span>Оплата</span>
            <span class="re-pill" :class="result.paid ? 'is-ok' : 'is-due'">{{ result.paid ? 'оплачен' : 'не оплачен' }}</span>
          </div>
          <p v-if="needsPay">Регистрация завершится после оплаты. Оплатить можно сейчас или позже со страницы события.</p>
          <p v-if="result.emailed && result.email">PIN и ссылку на оплату отправили на {{ result.email }}.</p>
        </div>

        <p class="re-remember">
          Мы запомнили вас {{ onDevice }}: на странице события будет ваша карточка, в результатах сразу откроется ваша группа.
        </p>
        <a class="re-linkbtn" :href="app.router.href('reg')" @click="another">Зарегистрировать ещё одного участника</a>
      </section>
    </main>

    <footer class="re-action is-narrow">
      <div v-if="needsPay" class="re-act-row is-two">
        <a class="re-btn" :href="app.router.href('info')" @click="app.navigate($event, 'info')">Позже</a>
        <a class="re-btn is-primary" :href="payHref" @click="goPay">Оплатить{{ fee ? ` ${formatMoney(fee)} ₽` : '' }}</a>
      </div>
      <div v-else class="re-act-row is-two">
        <a class="re-btn" :href="app.router.href('people')" @click="app.navigate($event, 'people')">Участники</a>
        <a class="re-btn is-primary" :href="app.router.href('info')" @click="app.navigate($event, 'info')">К событию</a>
      </div>
    </footer>
  </div>
</template>
