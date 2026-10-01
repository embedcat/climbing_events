// Точка входа кабинета «Мои события». Django кладёт на страницу `<div id="mine-app">`, список событий (`mine-initial`)
// и сведения о том, кто смотрит и куда вести ссылки (`site-context`).
import { createApp } from 'vue'
import { createHttp } from '../api/http'
import { createSiteApi, type MyEvents } from '../api/site'
import type { SiteContext } from '../screens/home/context'
import MineApp from '../screens/mine/MineApp.vue'
import { useMineApp } from '../screens/mine/useMineApp'
import '../site'
import { readPageData } from '../site/pageData'
import '../styles/common.css'
import '../styles/home.css'

const root = document.getElementById('mine-app')
const ctx = readPageData<SiteContext>('site-context')
if (root && ctx) {
  const app = useMineApp({ api: createSiteApi(createHttp()), initial: readPageData<MyEvents>('mine-initial') })
  createApp(MineApp, { app, ctx }).mount(root)
}
