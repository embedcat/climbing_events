// Точка входа страницы события для участника. Django кладёт на страницу `<div id="event-app" …>`, сюда её и монтируем.
// Все адреса /e/<id>/… отдают один и тот же HTML: вкладки, регистрация и оплата — экраны этого приложения.
import { createApp } from 'vue'
import { createEntryApi } from '../api/entry'
import { createEventApi } from '../api/event'
import { createHttp } from '../api/http'
import { createResultsApi } from '../api/results'
import { browserStore } from '../domain/storage'
import EventApp from '../screens/event/EventApp.vue'
import { useEventApp } from '../screens/event/useEventApp'
import '../site'
import '../styles/common.css'
import '../styles/event.css'
import '../styles/entry.css'
import '../styles/results.css'

const root = document.getElementById('event-app')
if (root) {
  const eventId = Number(root.dataset.eventId)
  const http = createHttp({ csrfToken: root.dataset.csrfToken })
  const app = useEventApp({
    eventId,
    api: createEventApi(http),
    entryApi: createEntryApi(http),
    resultsApi: createResultsApi(http),
    store: browserStore(),
    manageUrl: root.dataset.manageUrl,
  })
  createApp(EventApp, { app }).mount(root)
}
