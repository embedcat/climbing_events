// Общий каркас сайта для каждой страницы: шрифты, цвета, стили полосы сайта и её поведение.
// Страница события и массовый ввод подключают его вместе со своим экраном, остальные страницы Django — как entries/site.ts.
import '../styles/fonts.css'
import '../styles/tokens.css'
import '../styles/site.css'
import { browserStore } from '../domain/storage'
import { mountSiteBar } from './siteBar'

if (typeof document !== 'undefined') {
  mountSiteBar({ doc: document, store: browserStore(), media: window.matchMedia('(prefers-color-scheme: dark)') })
}
