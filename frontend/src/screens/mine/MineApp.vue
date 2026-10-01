<script setup lang="ts">
// Кабинет «Мои события»: карточки с этапом и числами, фильтры, переход в панель события.
import { computed, onMounted } from 'vue'
import type { MyEventCard } from '../../api/site'
import { eventUrl, matrixUrl, MINE_FILTERS, panelUrl, STAGE_TAG } from '../../domain/siteEvents'
import type { SiteContext } from '../home/context'
import type { MineApp } from './useMineApp'

const props = defineProps<{ app: MineApp, ctx: SiteContext }>()

onMounted(() => { void props.app.init() })

const TAG_CLASS = { '': '', ok: 'is-ok', live: 'is-ok is-live', warn: 'is-warn' } as const
const tagClass = (card: MyEventCard): string => TAG_CLASS[STAGE_TAG[card.stage].kind]
const meta = (card: MyEventCard): string =>
  [card.date, card.gym, props.app.scope === 'all' ? card.owner : ''].filter(Boolean).join(' · ')
const entering = (card: MyEventCard): boolean => card.stage === 'live' || card.stage === 'over'
const title = computed(() => (props.app.scope === 'all' ? 'Все события' : 'Мои события'))
</script>

<template>
  <div class="re-screen re-home">
    <div class="re-h-row">
      <h1>{{ title }}</h1>
      <a class="re-h-btn is-primary" :href="ctx.links.create">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>Создать событие
      </a>
    </div>

    <div v-if="app.isSuperuser" class="re-h-chips" role="group" aria-label="Чьи события">
      <button type="button" :aria-pressed="app.scope === 'mine'" @click="app.setScope('mine')">Мои</button>
      <button type="button" :aria-pressed="app.scope === 'all'" @click="app.setScope('all')">Все события сайта</button>
    </div>

    <div class="re-h-chips" role="group" aria-label="Фильтр">
      <button
        v-for="item in MINE_FILTERS" :key="item.value" type="button"
        :aria-pressed="app.filter === item.value" @click="app.setFilter(item.value)"
      >{{ item.label }}<span class="re-h-cnt">{{ app.counts[item.value] }}</span></button>
    </div>

    <p v-if="app.status === 'loading'" class="re-h-loading" role="status">Загружаю…</p>
    <div v-else-if="app.status === 'error'" class="re-h-err" role="alert">
      <span>{{ app.errorMessage }}</span>
      <button type="button" class="re-h-btn" @click="app.load()">Повторить</button>
    </div>
    <template v-else>
      <div v-if="app.visible.length" class="re-h-cards" :aria-busy="app.busy">
        <article v-for="card in app.visible" :key="card.id" class="re-h-card">
          <div class="re-h-tags">
            <span class="re-tag" :class="tagClass(card)">{{ STAGE_TAG[card.stage].label }}</span>
            <span v-if="card.is_premium" class="re-tag">★ полный доступ</span>
            <span v-if="card.is_pay_allowed" class="re-tag">с оплатой</span>
          </div>
          <h3 class="re-h-title"><a :href="panelUrl(card.id)">{{ card.title }}</a></h3>
          <div class="re-h-meta">{{ meta(card) }}</div>
          <div class="re-h-stats">
            <span>участников <b>{{ card.participants_count }}</b></span>
            <span>внесли результат <b>{{ card.entered_count }}</b></span>
            <span v-if="card.is_pay_allowed">оплатили <b>{{ card.paid_count }}</b></span>
          </div>
          <div class="re-h-btns">
            <a class="re-h-btn is-primary" :href="panelUrl(card.id)">Панель</a>
            <a class="re-h-btn" :href="eventUrl(card.id)">Страница события</a>
            <a v-if="entering(card)" class="re-h-btn" :href="matrixUrl(card.id)">Ввод результатов</a>
          </div>
        </article>
      </div>
      <div v-else class="re-h-none">
        {{ app.cards.length ? 'В этом фильтре пока ничего нет.' : 'Здесь пока ничего нет. Создайте первое событие.' }}
      </div>
    </template>
  </div>
</template>
