<script setup lang="ts">
// Карточка «Вы»: браузер помнит участника. До события в ней статус оплаты взноса, во время события и после — место.
import { computed } from 'vue'
import { genderLabel } from '../../domain/standings'
import { formatMoney } from './usePay'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const me = computed(() => props.app.me!)
const page = computed(() => props.app.page!)
/** Строка про место и оплату появляется, когда сервер ответил: до этого мы не знаем, внёс ли участник результат. */
const loaded = computed(() => me.value.loaded)

const kicker = computed(() => ({ live: 'Вы участвуете', over: 'Ваш результат', done: 'Ваш итог' } as Record<string, string>)[props.app.stage]
  ?? 'Вы зарегистрированы')
const name = computed(() => `${me.value.last_name} ${me.value.first_name}`)
const group = computed(() => [props.app.groupName(me.value.group_index), genderLabel(me.value.gender as 'MALE' | 'FEMALE')]
  .filter(Boolean).join(', '))
const fee = computed(() => {
  const price = props.app.priceOf(me.value.reg_type_index)
  return price ? `Взнос ${formatMoney(price)} ₽` : 'Взнос'
})
const standing = computed(() => me.value.standing)
const payPill = computed(() => ({
  paid: { cls: 'is-ok', text: 'оплачен' },
  pending: { cls: 'is-wait', text: 'проверяем платёж' },
  due: { cls: 'is-due', text: 'не оплачен' },
}[props.app.payStatus]))
</script>

<template>
  <section class="re-me-card" aria-label="Вы">
    <div class="re-mc-top">
      <span class="re-mc-k">{{ kicker }}</span>
      <button type="button" class="re-linkbtn" @click="app.forgetMe()">Не вы?</button>
    </div>
    <div class="re-mc-name">{{ name }}</div>
    <div class="re-mc-meta">{{ app.meta(me) }}</div>

    <template v-if="loaded">
      <div v-if="app.started" class="re-mc-row">
        <template v-if="me.entered && app.resultsOpen && standing">
          <div class="re-mc-place">
            <b>{{ standing.place }}</b>
            <span>место из {{ standing.of }}<br>{{ group }}</span>
          </div>
          <p v-if="app.stage === 'live'">Места меняются, пока другие вносят результаты.</p>
        </template>
        <template v-else-if="me.entered">
          <span>Результат внесён.</span>
          <p v-if="!app.resultsOpen">Место появится, когда организатор откроет результаты.</p>
        </template>
        <template v-else-if="app.stage === 'live'">
          <span>Вы ещё не внесли результат.</span>
          <p>PIN для ввода напечатан на вашей карточке участника.</p>
        </template>
        <template v-else>
          <span>Вы не внесли результат.</span>
          <p>Ввод закрыт. Подойдите к организатору: он внесёт результат по вашей карточке.</p>
        </template>
      </div>

      <div v-else-if="page.pay.is_allowed" class="re-mc-row">
        <span>{{ fee }}</span>
        <span class="re-pill" :class="payPill.cls">{{ payPill.text }}</span>
        <p v-if="page.pay.type === 'sbp' && app.payStatus !== 'paid'">Оплату по СБП организатор отмечает вручную, это может занять время.</p>
        <p v-if="app.payStatus === 'pending'">ЮMoney обычно подтверждает платёж за несколько минут.</p>
      </div>

      <div v-else class="re-mc-row">
        <p>Результаты вносите по PIN с карточки участника. Карточку выдаст организатор.</p>
      </div>
    </template>
  </section>
</template>
