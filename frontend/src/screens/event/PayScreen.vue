<script setup lang="ts">
// Оплата взноса. ЮMoney: промокод и переход на страницу оплаты. СБП: главная кнопка открывает приложение банка,
// а QR-код нужен для оплаты с другого устройства.
import { computed, onMounted, watch } from 'vue'
import { formatMoney } from './usePay'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const pay = computed(() => props.app.pay)
const info = computed(() => pay.value.info)

/** За кого платим: из адреса (`?p=` в письме), иначе тот, кого помнит браузер, иначе только что зарегистрированный. */
const participantId = computed<number | null>(() => {
  const fromUrl = Number(props.app.router.param('p'))
  return Number.isInteger(fromUrl) && fromUrl > 0 ? fromUrl : props.app.me?.id ?? props.app.registration.result?.participant.id ?? null
})
const who = computed(() => {
  const me = props.app.me
  return me && me.id === participantId.value ? `${me.last_name} ${me.first_name}` : ''
})

const load = () => { if (participantId.value !== null) void pay.value.load(participantId.value) }
onMounted(load)
watch(participantId, load)

const title = computed(() => (info.value?.type === 'sbp' ? 'Оплата по СБП' : 'Оплата взноса'))
const money = (value: number | null) => (value === null ? '' : `${formatMoney(value)} ₽`)
const promoClass = computed(() => (pay.value.promo.state === 'bad' ? 'is-err' : pay.value.promo.state === 'ok' ? 'is-ok' : ''))
</script>

<template>
  <div class="re-fill">
    <main class="re-main is-narrow">
      <a class="re-back" :href="app.router.href('info')" @click="app.navigate($event, 'info')">← К событию</a>
      <div>
        <h2>{{ title }}</h2>
        <p class="re-lead">{{ [who, app.page!.title].filter(Boolean).join(' · ') }}</p>
      </div>

      <section v-if="participantId === null" class="re-banner">
        <span>Не знаем, за кого платить. Найдите себя в списке участников и нажмите «Это я».</span>
        <a class="re-linkbtn" :href="app.router.href('people')" @click="app.navigate($event, 'people')">К списку</a>
      </section>
      <p v-else-if="pay.status === 'loading' || pay.status === 'idle'" class="re-loading" role="status">Загружаю…</p>
      <section v-else-if="pay.status === 'error'" class="re-banner is-error" role="alert">
        <span>{{ pay.errorMessage }}</span>
        <button type="button" class="re-linkbtn" @click="load">Повторить</button>
      </section>
      <section v-else-if="pay.status === 'unavailable'" class="re-banner" role="status">
        Онлайн-оплата временно недоступна. Напишите организатору: контакты на вкладке «Инфо».
      </section>
      <section v-else-if="pay.status === 'paid'" class="re-card is-center">
        <span class="re-pc-label">Взнос</span>
        <span class="re-pill is-ok">оплачен</span>
        <p>Спасибо! Платить ещё раз не нужно.</p>
      </section>

      <template v-else-if="info && info.type === 'sbp'">
        <div class="re-card is-center">
          <template v-if="info.amount !== null">
            <span class="re-pc-label">К оплате</span>
            <span class="re-amount">{{ money(info.amount) }}</span>
          </template>
          <p>Кнопка внизу откроет приложение вашего банка, сумма и получатель уже заполнены.</p>
        </div>
        <div class="re-divider">или с другого устройства</div>
        <img class="re-qr" :src="info.qr" alt="QR-код для оплаты по СБП">
        <div class="re-banner is-info">
          Оплату по СБП организатор отмечает вручную. После оплаты напишите ему: контакты на вкладке «Инфо».
        </div>
      </template>

      <template v-else-if="info">
        <div class="re-card is-center">
          <span class="re-pc-label">К оплате</span>
          <span class="re-amount">
            <s v-if="pay.promo.state === 'ok'">{{ formatMoney(pay.baseAmount!) }}</s>{{ money(pay.amount) }}
          </span>
        </div>
        <div class="re-fld">
          <span>Промокод<i> если есть</i></span>
          <div class="re-promo">
            <input
              v-model="pay.promo.code" autocapitalize="characters" autocomplete="off" aria-describedby="re-promo-msg"
              @keydown.enter.prevent="pay.applyPromo()"
            >
            <button type="button" class="re-btn" :disabled="pay.promo.state === 'checking'" @click="pay.applyPromo()">Применить</button>
          </div>
          <p id="re-promo-msg" class="re-hint" :class="promoClass" aria-live="polite">{{ pay.promo.message }}</p>
        </div>
        <p class="re-hint">Оплата картой на странице ЮMoney. После оплаты вы вернётесь сюда.</p>
      </template>
    </main>

    <footer v-if="info" class="re-action is-narrow">
      <div v-if="info.type === 'sbp'" class="re-act-row is-two">
        <a class="re-btn" :href="app.router.href('info')" @click="app.navigate($event, 'info')">Готово</a>
        <button type="button" class="re-btn is-primary" @click="pay.start()">Открыть банк</button>
      </div>
      <button v-else type="button" class="re-btn is-primary is-wide" :disabled="pay.sending" @click="pay.start()">
        {{ pay.sending ? 'Открываю ЮMoney…' : `Перейти к оплате · ${money(pay.amount)}` }}
      </button>
    </footer>
  </div>
</template>
