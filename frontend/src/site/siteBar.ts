// Полоса сайта (docs/mockups/site.html): логотип, ссылки, тема и меню аккаунта. Разметку отдаёт Django
// (events/snippets/sn-site-bar.html), так что полоса есть на каждой странице, а здесь только поведение:
// переключатель темы, меню, строка «Вас помнит этот браузер».
import { plural } from '../domain/format'
import { listRememberedEvents } from '../domain/remember'
import type { KeyValueStore } from '../domain/storage'
import { applyTheme, loadTheme, nextTheme, saveTheme, THEME_LABEL, type ThemePref } from '../domain/theme'

/** Тема системы (prefers-color-scheme): из неё берётся «Авто» */
export interface SystemTheme {
  matches: boolean
  addEventListener(type: 'change', listener: () => void): void
  removeEventListener(type: 'change', listener: () => void): void
}

export interface SiteBarDeps {
  doc: Document
  store: KeyValueStore
  media: SystemTheme
}

const FOCUSABLE = 'a[href], button:not([disabled])'

/** Возвращает функцию, снимающую обработчики (нужна тестам) */
export function mountSiteBar({ doc, store, media }: SiteBarDeps): () => void {
  const root = doc.documentElement
  let pref: ThemePref = loadTheme(store)

  const cycleButtons = Array.from(doc.querySelectorAll<HTMLElement>('[data-site-theme-cycle]'))
  const setButtons = Array.from(doc.querySelectorAll<HTMLElement>('[data-site-theme-set]'))
  const toggles = Array.from(doc.querySelectorAll<HTMLElement>('[data-site-menu-toggle]'))
  const menu = doc.querySelector<HTMLElement>('[data-site-menu]')

  function syncTheme(): void {
    applyTheme(root, pref, media.matches)
    for (const button of cycleButtons) {
      const label = `Тема: ${THEME_LABEL[pref]}. Сменить`
      button.setAttribute('aria-label', label)
      button.setAttribute('title', label)
    }
    for (const button of setButtons) {
      button.setAttribute('aria-pressed', String(button.dataset.siteThemeSet === pref))
    }
  }
  function choose(next: ThemePref): void {
    pref = next
    saveTheme(store, pref)
    syncTheme()
  }

  const cleanups: Array<() => void> = []
  const on = (el: EventTarget, type: string, fn: (e: Event) => void): void => {
    el.addEventListener(type, fn)
    cleanups.push(() => el.removeEventListener(type, fn))
  }

  for (const button of cycleButtons) on(button, 'click', () => choose(nextTheme(pref)))
  for (const button of setButtons) {
    on(button, 'click', () => choose(button.dataset.siteThemeSet as ThemePref))
  }
  const onSystemChange = (): void => { if (pref === 'auto') syncTheme() }
  media.addEventListener('change', onSystemChange)
  cleanups.push(() => media.removeEventListener('change', onSystemChange))

  function setMenu(open: boolean): void {
    if (!menu) return
    const wasOpen = !menu.hidden
    menu.hidden = !open
    for (const toggle of toggles) toggle.setAttribute('aria-expanded', String(open))
    if (open) menu.querySelector<HTMLElement>(FOCUSABLE)?.focus()
    else if (wasOpen) toggles.find((t) => t.offsetParent !== null)?.focus()
  }
  for (const toggle of toggles) on(toggle, 'click', () => setMenu(Boolean(menu?.hidden)))
  for (const closer of Array.from(doc.querySelectorAll<HTMLElement>('[data-site-menu-close]'))) {
    on(closer, 'click', () => setMenu(false))
  }
  on(doc, 'keydown', (e) => { if ((e as KeyboardEvent).key === 'Escape' && menu && !menu.hidden) setMenu(false) })

  const remembered = doc.querySelector<HTMLElement>('[data-site-remembered]')
  if (remembered) {
    const list = listRememberedEvents(store)
    if (list.length) {
      const { who } = list[0]
      const text = remembered.querySelector<HTMLElement>('[data-site-remembered-text]')
      if (text) {
        text.textContent = `${who.last_name} ${who.first_name} · ${list.length} ${plural(list.length, 'событие', 'события', 'событий')}`
      }
      remembered.hidden = false
    }
  }

  syncTheme()
  return () => cleanups.forEach((fn) => fn())
}
