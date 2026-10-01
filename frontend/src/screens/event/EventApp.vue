<script setup lang="ts">
// Оболочка страницы события: шапка с вкладками не прыгает при переходе между экранами, а главное действие каждого
// экрана закреплено внизу.
import { nextTick, onMounted, onUnmounted, watch } from 'vue'
import EnterTab from './EnterTab.vue'
import InfoScreen from './InfoScreen.vue'
import PayDone from './PayDone.vue'
import PayScreen from './PayScreen.vue'
import PeopleScreen from './PeopleScreen.vue'
import PosterLightbox from './PosterLightbox.vue'
import RegistrationDone from './RegistrationDone.vue'
import RegistrationScreen from './RegistrationScreen.vue'
import ResultsTab from './ResultsTab.vue'
import { TABS } from './router'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

onMounted(() => { void props.app.init() })
onUnmounted(() => props.app.dispose())

const onVisible = () => { if (!document.hidden) props.app.refreshPage(60_000) }
onMounted(() => document.addEventListener('visibilitychange', onVisible))
onUnmounted(() => document.removeEventListener('visibilitychange', onVisible))

// новый экран открывается с начала
watch(() => props.app.screen, async () => {
  await nextTick()
  document.querySelector<HTMLElement>('.re-app .re-main')?.scrollTo?.(0, 0)
})
</script>

<template>
  <div class="re-screen re-app">
    <header class="re-head">
      <div class="re-head-top">
        <div>
          <div class="re-title">{{ app.page?.title ?? ' ' }}</div>
          <div v-if="app.page" class="re-date">{{ [app.page.date, app.page.gym].filter(Boolean).join(' · ') }}</div>
        </div>
        <a v-if="app.canManage && app.manageUrl" class="re-manage" :href="app.manageUrl">Управление</a>
      </div>
      <nav class="re-tabs" aria-label="Разделы события">
        <a
          v-for="item in TABS" :key="item.tab" :href="app.router.href(item.tab)"
          :aria-current="app.tab === item.tab ? 'page' : undefined"
          @click="app.navigate($event, item.tab)"
        >{{ item.label }}</a>
      </nav>
    </header>

    <main v-if="app.status === 'loading'" class="re-main"><p class="re-loading" role="status">Загружаю…</p></main>

    <main v-else-if="app.status === 'fatal'" class="re-main">
      <section class="re-banner" role="alert">
        <span>{{ app.fatalMessage }}</span>
        <button type="button" class="re-linkbtn" @click="app.init()">Повторить</button>
      </section>
    </main>

    <template v-else-if="app.page">
      <InfoScreen v-if="app.screen === 'info'" :app="app" />
      <PeopleScreen v-else-if="app.screen === 'people'" :app="app" />
      <EnterTab v-else-if="app.screen === 'enter'" :app="app" />
      <ResultsTab v-else-if="app.screen === 'results'" :app="app" />
      <RegistrationScreen v-else-if="app.screen === 'reg'" :app="app" />
      <RegistrationDone v-else-if="app.screen === 'regdone'" :app="app" />
      <PayScreen v-else-if="app.screen === 'pay'" :app="app" />
      <PayDone v-else-if="app.screen === 'paydone'" :app="app" />
    </template>

    <PosterLightbox v-if="app.poster && app.page?.poster" :app="app" />
    <div v-if="app.toast" class="re-toast" role="status">{{ app.toast }}</div>
  </div>
</template>
