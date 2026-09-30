// Точка входа экрана ввода результатов. Django кладёт на страницу `<div id="entry-app" …>`, сюда её и монтируем.
import { createApp } from 'vue'
import { createEntryApi } from '../api/entry'
import { createHttp } from '../api/http'
import { browserStore } from '../domain/storage'
import EntryApp from '../screens/entry/EntryApp.vue'
import { useEntryFlow } from '../screens/entry/useEntryFlow'
import '../styles/fonts.css'
import '../styles/common.css'
import '../styles/entry.css'

const root = document.getElementById('entry-app')
if (root) {
  const eventId = Number(root.dataset.eventId)
  const flow = useEntryFlow({
    eventId,
    api: createEntryApi(createHttp({ csrfToken: root.dataset.csrfToken })),
    store: browserStore(),
  })
  createApp(EntryApp, { flow, resultsUrl: root.dataset.resultsUrl ?? `/e/${eventId}/results/` }).mount(root)
}
