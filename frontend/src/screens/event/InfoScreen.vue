<script setup lang="ts">
// «Инфо»: афиша и главное, карточка «Вы», этап события, сеты или призёры, описание от организатора.
import { computed } from 'vue'
import MeCard from './MeCard.vue'
import PodiumBlock from './PodiumBlock.vue'
import SetsBlock from './SetsBlock.vue'
import StageCard from './StageCard.vue'
import TabAction from './TabAction.vue'
import { formatMoney } from './usePay'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const page = computed(() => props.app.page!)
const fee = computed(() => {
  const p = page.value
  if (!p.pay.price) return ''
  return `${p.registration.reg_types.length > 1 ? 'от ' : ''}${formatMoney(p.pay.price)} ₽`
})
</script>

<template>
  <div class="re-fill">
    <main class="re-main">
      <div class="re-info">
        <div class="re-info-side">
          <section class="re-intro">
            <button v-if="page.poster" type="button" class="re-poster" aria-label="Открыть афишу" @click="app.openPoster()">
              <img :src="page.poster" :alt="page.title">
            </button>
            <dl class="re-fact-list">
              <div><dt>Когда</dt><dd>{{ page.date_long }}</dd></div>
              <div v-if="page.gym"><dt>Где</dt><dd>{{ page.gym }}</dd></div>
              <div v-if="fee"><dt>Взнос</dt><dd>{{ fee }}</dd></div>
              <div v-if="page.groups.length">
                <dt>Группы</dt>
                <dd>{{ page.groups.join(', ') }}<small>зачёт отдельно у мужчин и женщин</small></dd>
              </div>
            </dl>
          </section>
        </div>

        <div class="re-info-body">
          <MeCard v-if="app.me" :app="app" />
          <StageCard v-if="!app.me || app.started" :app="app" />
          <template v-if="app.stage === 'done'">
            <PodiumBlock v-if="app.resultsOpen" :app="app" />
          </template>
          <SetsBlock v-else :app="app" />
          <section v-if="page.description.trim()" class="re-block">
            <h3 class="re-bh">Описание</h3>
            <!-- описание пишет организатор в редакторе: HTML, как и на прежней странице -->
            <div class="re-prose" v-html="page.description" />
          </section>
        </div>
      </div>
    </main>
    <TabAction tab="info" :app="app" />
  </div>
</template>
