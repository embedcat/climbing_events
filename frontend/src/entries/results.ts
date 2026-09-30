// Точка входа экрана результатов. Django кладёт на страницу `<div id="results-app" …>`, сюда её и монтируем.
import { createApp } from 'vue'
import { createHttp } from '../api/http'
import { createResultsApi } from '../api/results'
import { browserStore } from '../domain/storage'
import ResultsApp from '../screens/results/ResultsApp.vue'
import { useResultsFlow } from '../screens/results/useResultsFlow'
import '../styles/fonts.css'
import '../styles/common.css'
import '../styles/results.css'

const root = document.getElementById('results-app')
if (root) {
  const eventId = Number(root.dataset.eventId)
  const flow = useResultsFlow({
    eventId,
    api: createResultsApi(createHttp()),
    store: browserStore(),
    search: window.location.search,
  })
  // правка результатов участника организатором: матрица открывается сразу на нём
  const editUrl = (participantId: number) => `/e/${eventId}/matrix/#p=${participantId}`
  createApp(ResultsApp, { flow, editUrl }).mount(root)
}
