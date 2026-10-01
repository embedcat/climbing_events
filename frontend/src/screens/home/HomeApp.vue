<script setup lang="ts">
// Главная: поиск, «Вы участвуете», вкладки «Предстоящие» и «Прошедшие», карточки событий, для гостя призыв создать событие.
import { onMounted, onUnmounted } from 'vue'
import { DEFAULT_POSTER, type SiteContext } from './context'
import EventCard from './EventCard.vue'
import type { HomeApp } from './useHomeApp'

const props = defineProps<{ app: HomeApp, ctx: SiteContext }>()

onMounted(() => { void props.app.init() })
onUnmounted(() => props.app.dispose())

function onSearch(event: Event): void {
  props.app.setQuery((event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="re-screen re-home">
    <section class="re-h-hero">
      <div class="re-h-copy">
        <h1>Скалолазные соревнования</h1>
        <p class="re-h-lead">Найдите событие, зарегистрируйтесь и вносите результаты с телефона. Результаты обновляются сразу.</p>
      </div>
      <label class="re-h-search">
        <span class="re-sr-only">Найти событие</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></svg>
        <input type="search" :value="app.query" placeholder="Название или скалодром" autocomplete="off" @input="onSearch">
      </label>
    </section>

    <section v-if="app.rows.length" class="re-h-mine" aria-label="Вы участвуете">
      <h2 class="re-h-label">Вы участвуете</h2>
      <a v-for="row in app.rows" :key="row.id" class="re-h-mcard" :href="row.href">
        <span class="re-h-poster"><img :src="row.poster || DEFAULT_POSTER" alt="" loading="lazy"></span>
        <span>
          <span class="re-h-mt">{{ row.title }}</span><br>
          <span class="re-h-ms">{{ row.note }}</span>
        </span>
        <span class="re-h-go">{{ row.go }} →</span>
      </a>
    </section>

    <div v-if="ctx.authenticated" class="re-h-row">
      <p class="re-h-hint">Вы вошли как организатор</p>
      <div class="re-h-acts">
        <a class="re-h-btn" :href="ctx.links.mine">Мои события</a>
        <a class="re-h-btn is-primary" :href="ctx.links.create">Создать событие</a>
      </div>
    </div>

    <div class="re-h-chips" role="group" aria-label="Период">
      <button type="button" :aria-pressed="app.when === 'upcoming'" @click="app.setWhen('upcoming')">
        Предстоящие<span class="re-h-cnt">{{ app.counts.upcoming }}</span>
      </button>
      <button type="button" :aria-pressed="app.when === 'past'" @click="app.setWhen('past')">
        Прошедшие<span class="re-h-cnt">{{ app.counts.past }}</span>
      </button>
    </div>

    <p v-if="app.status === 'loading'" class="re-h-loading" role="status">Загружаю…</p>
    <div v-else-if="app.status === 'error'" class="re-h-err" role="alert">
      <span>{{ app.errorMessage }}</span>
      <button type="button" class="re-h-btn" @click="app.load()">Повторить</button>
    </div>
    <template v-else>
      <div v-if="app.cards.length" class="re-h-evs" :aria-busy="app.busy">
        <EventCard v-for="card in app.cards" :key="card.id" :card="card" :authenticated="ctx.authenticated" />
      </div>
      <div v-else class="re-h-none">
        {{ app.query.trim() ? 'Ничего не нашли. Проверьте название или посмотрите другой период.' : 'Здесь пока нет событий.' }}
      </div>
      <p v-if="app.errorMessage" class="re-h-err" role="alert">{{ app.errorMessage }}</p>
      <button v-if="app.hasMore" type="button" class="re-h-btn re-h-more" :disabled="app.loadingMore" @click="app.loadMore()">
        Показать ещё
      </button>
    </template>

    <section v-if="!ctx.authenticated" class="re-h-promo">
      <div>
        <h2>Проводите соревнования?</h2>
        <ol>
          <li>Создайте событие и опубликуйте афишу.</li>
          <li>Участники регистрируются сами и вносят результаты по PIN.</li>
          <li>Протоколы и карточки участников — в Excel и на печать.</li>
        </ol>
      </div>
      <a class="re-h-btn is-primary is-big" :href="ctx.links.create">Создать событие</a>
    </section>

    <footer class="re-h-foot">
      <div>
        <b>Участникам</b>
        <a :href="ctx.links.home">Все события</a>
      </div>
      <div>
        <b>Организаторам</b>
        <a :href="ctx.links.create">Создать событие</a>
        <a :href="ctx.links.help">Инструкции</a>
      </div>
      <div>
        <b>Проект</b>
        <a :href="ctx.links.about">О проекте</a>
        <a :href="ctx.links.stat">Статистика</a>
      </div>
    </footer>
  </div>
</template>
