<script setup lang="ts">
// Вернулись со страницы оплаты ЮMoney: подтверждение приходит вебхуком за несколько минут, пока ждём.
import { computed } from 'vue'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const paid = computed(() => props.app.payStatus === 'paid')
</script>

<template>
  <div class="re-fill">
    <main class="re-main is-narrow">
      <section class="re-done">
        <svg class="re-done-mark" viewBox="0 0 48 48" aria-hidden="true">
          <circle cx="24" cy="24" r="22" />
          <path d="M14 24.5l7 7 13-14" />
        </svg>
        <template v-if="paid">
          <h2>Взнос оплачен</h2>
          <p class="re-muted">ЮMoney подтвердил платёж. Спасибо!</p>
        </template>
        <template v-else>
          <h2>Платёж отправлен</h2>
          <p class="re-muted">
            ЮMoney подтвердит оплату в течение нескольких минут. Статус виден на вкладке «Инфо», в карточке «Вы».
          </p>
        </template>
      </section>
    </main>
    <footer class="re-action is-narrow">
      <a class="re-btn is-primary is-wide" :href="app.router.href('info')" @click="app.navigate($event, 'info')">К событию</a>
    </footer>
  </div>
</template>
