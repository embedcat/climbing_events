// Точка входа содержимого панели события организатора. Django кладёт `<div id="panel-app" data-screen="overview|people" …>`,
// разделы панели (`panel-sections`) и рамку (боковое меню, крошки) рисует сам.
import { createApp } from 'vue'
import { createEventApi } from '../api/event'
import { createHttp } from '../api/http'
import { createPanelApi } from '../api/panel'
import PanelOverview from '../screens/panel/PanelOverview.vue'
import PanelPeople from '../screens/panel/PanelPeople.vue'
import type { PanelSectionGroup } from '../screens/panel/context'
import { usePanelOverview } from '../screens/panel/usePanelOverview'
import { usePanelPeople } from '../screens/panel/usePanelPeople'
import '../site'
import { readPageData } from '../site/pageData'
import '../styles/common.css'
import '../styles/panel.css'

const root = document.getElementById('panel-app')
if (root) {
  const eventId = Number(root.dataset.eventId)
  const csrfToken = root.dataset.csrfToken ?? ''
  const http = createHttp({ csrfToken })
  if (root.dataset.screen === 'people') {
    const app = usePanelPeople({ eventId, api: createEventApi(http) })
    createApp(PanelPeople, { app, csrfToken }).mount(root)
  } else {
    const app = usePanelOverview({ eventId, api: createPanelApi(http), isSuperuser: root.dataset.superuser === '1' })
    const sections = readPageData<PanelSectionGroup[]>('panel-sections') ?? []
    createApp(PanelOverview, { app, sections }).mount(root)
  }
}
