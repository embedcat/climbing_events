<script setup lang="ts">
// Карточка этапа события: что с регистрацией и вводом результатов, чего ждать участнику.
import { computed } from 'vue'
import { plural } from '../../domain/format'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const page = computed(() => props.app.page!)
const people = (n: number) => `${n} ${plural(n, 'участник', 'участника', 'участников')}`

/** «До 3 октября, 23:59 · 42 участника · свободно 6 мест». */
const openLine = computed(() => {
  const r = page.value.registration
  const parts = [r.until ? `До ${r.until}` : '', people(page.value.participants_count)]
  if (r.free_places !== null) parts.push(props.app.freeText)
  return parts.filter(Boolean).join(' · ')
})
const enteredLine = computed(() => `внесли ${page.value.entered_count} из ${page.value.participants_count}`)
</script>

<template>
  <section v-if="app.stage === 'reg' && page.is_without_registration" class="re-status">
    <div class="re-st-h">Регистрация не нужна</div>
    <p>Приходите к началу своего сета. После сета внесите результаты: имя, группу и сет укажете в той же форме.</p>
  </section>

  <section v-else-if="app.stage === 'reg'" class="re-status is-open">
    <div class="re-st-h"><span class="re-dot" aria-hidden="true" />Регистрация открыта</div>
    <p>{{ openLine }}</p>
  </section>

  <section v-else-if="app.stage === 'reg_closed'" class="re-status">
    <div class="re-st-h">Регистрация закрыта</div>
    <p>Хотите участвовать — напишите организатору, контакты в описании ниже.</p>
  </section>

  <section v-else-if="app.stage === 'live'" class="re-status is-live">
    <div class="re-st-h"><span class="re-dot" aria-hidden="true" />Идёт</div>
    <p>Ввод результатов открыт · {{ enteredLine }}.</p>
    <p v-if="page.is_without_registration">Внесите результаты после своего сета: имя, группу и сет укажете в той же форме.</p>
    <p v-else>PIN для ввода напечатан на вашей карточке участника.</p>
    <p v-if="page.registration.is_open && !app.me">
      Ещё не зарегистрированы?
      <a class="re-linkbtn" :href="app.router.href('reg')" @click="app.navigate($event, 'reg')">Зарегистрироваться</a>
    </p>
  </section>

  <section v-else-if="app.stage === 'over'" class="re-status">
    <div class="re-st-h">Ввод результатов закрыт</div>
    <p>Внесли результат {{ page.entered_count }} из {{ page.participants_count }}.</p>
    <p>Не успели внести результат или нашли ошибку — подойдите к организатору, он исправит.</p>
  </section>

  <section v-else class="re-status">
    <div class="re-st-h">Соревнование завершено</div>
    <p>
      {{ page.date_short }} · {{ people(page.participants_count) }}.
      {{ app.resultsOpen ? 'Итоговые результаты открыты и останутся на сайте.' : 'Итоговые результаты появятся, когда организатор их откроет.' }}
    </p>
  </section>
</template>
