// Точка входа экрана массового ввода организатором. Django кладёт на страницу `<div id="matrix-app" …>`.
import { createApp } from 'vue'
import { createHttp } from '../api/http'
import { createMatrixApi } from '../api/matrix'
import { browserStore } from '../domain/storage'
import MatrixApp from '../screens/matrix/MatrixApp.vue'
import { useMatrixFlow } from '../screens/matrix/useMatrixFlow'
import '../styles/fonts.css'
import '../styles/common.css'
import '../styles/entry.css'
import '../styles/matrix.css'

const root = document.getElementById('matrix-app')
if (root) {
  const eventId = Number(root.dataset.eventId)
  const flow = useMatrixFlow({
    eventId,
    api: createMatrixApi(createHttp({ csrfToken: root.dataset.csrfToken })),
    store: browserStore(),
    hash: window.location.hash,
  })
  createApp(MatrixApp, {
    flow,
    resultsUrl: root.dataset.resultsUrl ?? `/e/${eventId}/results/`,
    manageUrl: root.dataset.manageUrl ?? `/e/${eventId}/admin_actions/`,
  }).mount(root)
}
