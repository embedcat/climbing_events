// Точка входа главной. Django кладёт на страницу `<div id="home-app">`, первую страницу каталога (`home-initial`) и
// сведения о том, кто смотрит и куда вести ссылки (`site-context`).
import { createApp } from 'vue'
import { createHttp } from '../api/http'
import { createSiteApi, type SiteCatalog } from '../api/site'
import { browserStore } from '../domain/storage'
import HomeApp from '../screens/home/HomeApp.vue'
import type { SiteContext } from '../screens/home/context'
import { useHomeApp } from '../screens/home/useHomeApp'
import '../site'
import { readPageData } from '../site/pageData'
import '../styles/common.css'
import '../styles/home.css'

const root = document.getElementById('home-app')
const ctx = readPageData<SiteContext>('site-context')
if (root && ctx) {
  const app = useHomeApp({
    api: createSiteApi(createHttp()),
    store: browserStore(),
    initial: readPageData<SiteCatalog>('home-initial'),
  })
  createApp(HomeApp, { app, ctx }).mount(root)
}
