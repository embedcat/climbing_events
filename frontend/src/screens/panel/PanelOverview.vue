<script setup lang="ts">
// «Обзор» панели события по макету site.html: переключатели дня события, числа, чек-лист подготовки,
// ссылки для зала и служебные действия. С телефона под ними список разделов панели.
import { computed, onMounted, onUnmounted } from 'vue'
import { plural } from '../../domain/format'
import { FLAG_INFO, ACTION_INFO } from '../../domain/panel'
import { STAGE_TAG } from '../../domain/siteEvents'
import ConfirmSheet from './ConfirmSheet.vue'
import type { PanelSectionGroup } from './context'
import type { PanelOverviewApp } from './usePanelOverview'

const props = defineProps<{ app: PanelOverviewApp, sections: PanelSectionGroup[] }>()

onMounted(() => { void props.app.load() })
onUnmounted(() => props.app.dispose())

const stageLabel = computed(() => (props.app.overview ? STAGE_TAG[props.app.overview.stage].label : ''))
const people = (n: number): string => plural(n, 'участник', 'участника', 'участников')
const phoneSections = computed(() => props.sections.flatMap((group) => group.items).filter((item) => item.url_name !== 'admin_actions'))
const asking = computed(() => (props.app.confirm ? ACTION_INFO[props.app.confirm] : null))
const shortUrl = (url: string): string => url.replace(/^https?:\/\//, '')
</script>

<template>
  <div class="re-screen re-panel">
    <p v-if="app.status === 'loading'" class="re-p-loading" role="status">Загружаю…</p>
    <div v-else-if="app.status === 'error'" class="re-p-err" role="alert">
      <span>{{ app.errorMessage }}</span>
      <button type="button" class="re-p-btn" @click="app.load()">Повторить</button>
    </div>

    <template v-else-if="app.overview">
      <section class="re-p-card" aria-labelledby="re-p-now">
        <h2 id="re-p-now">Сейчас</h2>
        <div class="re-p-switches">
          <div v-for="info in FLAG_INFO" :key="info.flag" class="re-p-sw">
            <div>
              <b>{{ info.title }}</b>
              <small>{{ info.hint }}</small>
            </div>
            <button
              :id="`re-switch-${info.flag}`" type="button" class="re-p-tgl" role="switch"
              :aria-checked="app.flags[info.flag]" :aria-label="info.title" @click="app.toggle(info.flag)"
            />
          </div>
        </div>
        <p class="re-p-hint">
          Этап для участников: <b>{{ stageLabel }}</b>. Закрыть ввод по окончании события — здесь же, автоматики по времени нет.
        </p>
      </section>

      <div class="re-p-kpis">
        <div class="re-p-kpi"><b>{{ app.overview.participants_count }}</b><span>{{ people(app.overview.participants_count) }}</span></div>
        <div class="re-p-kpi"><b>{{ app.overview.entered_count }}</b><span>внесли результат</span></div>
        <div class="re-p-kpi"><b>{{ app.overview.is_pay_allowed ? app.overview.paid_count : '—' }}</b><span>оплатили взнос</span></div>
      </div>
      <div v-if="app.overview.entered_count > 0">
        <div class="re-p-bar" aria-hidden="true"><i :style="{ width: `${app.percent}%` }" /></div>
        <p class="re-p-hint re-p-under">Внесли результат {{ app.overview.entered_count }} из {{ app.overview.participants_count }}</p>
      </div>

      <section v-if="app.progress.open" class="re-p-card" aria-labelledby="re-p-todo">
        <h2 id="re-p-todo">Подготовка · {{ app.progress.done }} из {{ app.progress.total }}</h2>
        <div class="re-p-todo">
          <a v-for="row in app.checklist" :key="row.id" :href="row.href" :class="{ 'is-done': row.done }">
            <span class="re-p-tick" aria-hidden="true">
              <svg v-if="row.done" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
            </span>
            <span>{{ row.title }}<br><small>{{ row.hint }}</small></span>
            <svg class="re-p-chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
          </a>
        </div>
      </section>

      <section class="re-p-card" aria-labelledby="re-p-hall">
        <h2 id="re-p-hall">Для зала</h2>
        <div class="re-p-links">
          <div v-for="link in app.links" :key="link.gender" class="re-p-link">
            <code>{{ shortUrl(link.url) }}</code>
            <button type="button" class="re-p-btn" :aria-label="`Скопировать ссылку: ${link.gender === 'М' ? 'мужчины' : 'женщины'}`" @click="app.copyLink(link.url, link.gender === 'М' ? 'мужчины' : 'женщины')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h8" /></svg>{{ link.gender }}
            </button>
          </div>
        </div>
        <p class="re-p-hint">Монитор для экрана в зале: таблица обновляется каждые 10 секунд. QR-коды и карточки с PIN — в разделе «Протоколы и файлы».</p>
      </section>

      <section v-if="phoneSections.length" class="re-p-phone" aria-label="Разделы панели">
        <h2 class="re-p-label">Разделы</h2>
        <div class="re-p-secmenu">
          <a v-for="item in phoneSections" :key="item.url" :href="item.url">
            <span><b>{{ item.title }}{{ item.external ? ' ↗' : '' }}</b><small>{{ item.hint }}</small></span>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6l6 6-6 6" /></svg>
          </a>
        </div>
      </section>

      <details class="re-p-card re-p-danger">
        <summary>Служебные действия</summary>
        <div class="re-p-acts">
          <div v-for="item in app.actions" :key="item.action">
            <span>{{ item.hint }}</span>
            <button type="button" class="re-p-btn" :class="{ 'is-danger': item.danger }" :disabled="item.disabled" @click="app.ask(item.action)">
              {{ item.title }}
            </button>
          </div>
        </div>
      </details>
    </template>

    <ConfirmSheet
      v-if="asking" :title="asking.title" :question="asking.question" :confirm-label="asking.title"
      :danger="asking.danger" :busy="app.acting" @confirm="app.run()" @cancel="app.cancel()"
    />
    <div v-if="app.toast" class="re-toast" role="status">{{ app.toast }}</div>
  </div>
</template>
