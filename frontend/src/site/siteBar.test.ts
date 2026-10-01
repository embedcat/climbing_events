import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { memoryStore } from '../domain/storage'
import { rememberParticipant } from '../domain/remember'
import { THEME_KEY } from '../domain/theme'
import { mountSiteBar } from './siteBar'

const MARKUP = `
  <header data-site-bar>
    <button data-site-theme-cycle>тема</button>
    <button data-site-menu-toggle aria-expanded="false">меню</button>
  </header>
  <div data-site-menu hidden>
    <div data-site-menu-close></div>
    <div data-site-remembered hidden><b>Вас помнит этот браузер</b><span data-site-remembered-text></span></div>
    <button data-site-theme-set="auto">Авто</button>
    <button data-site-theme-set="light">Светлая</button>
    <button data-site-theme-set="dark">Тёмная</button>
    <a href="/">События</a>
  </div>`

function fakeMedia(matches = false) {
  const listeners = new Set<() => void>()
  return {
    matches,
    addEventListener: (_: string, fn: () => void) => { listeners.add(fn) },
    removeEventListener: (_: string, fn: () => void) => { listeners.delete(fn) },
    change(next: boolean) { this.matches = next; listeners.forEach((fn) => fn()) },
  }
}

const q = <T extends HTMLElement>(sel: string): T => document.querySelector<T>(sel)!

beforeEach(() => {
  document.body.innerHTML = MARKUP
  document.documentElement.removeAttribute('data-theme')
  document.documentElement.removeAttribute('data-bs-theme')
})
afterEach(() => { document.body.innerHTML = '' })

describe('полоса сайта: тема', () => {
  it('применяет запомненную тему сразу', () => {
    const store = memoryStore({ [THEME_KEY]: 'dark' })
    mountSiteBar({ doc: document, store, media: fakeMedia() })
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(q('[data-site-theme-set="dark"]').getAttribute('aria-pressed')).toBe('true')
    expect(q('[data-site-theme-set="auto"]').getAttribute('aria-pressed')).toBe('false')
  })

  it('кнопка листает авто, светлая, тёмная и запоминает выбор', () => {
    const store = memoryStore()
    mountSiteBar({ doc: document, store, media: fakeMedia() })
    const cycle = q('[data-site-theme-cycle]')
    expect(cycle.getAttribute('aria-label')).toBe('Тема: Авто. Сменить')
    cycle.click()
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
    expect(store.data.get(THEME_KEY)).toBe('light')
    expect(cycle.getAttribute('aria-label')).toBe('Тема: Светлая. Сменить')
    cycle.click()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    cycle.click()
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
    expect(store.data.has(THEME_KEY)).toBe(false)
  })

  it('сегмент в меню выбирает тему напрямую', () => {
    const store = memoryStore()
    mountSiteBar({ doc: document, store, media: fakeMedia() })
    q('[data-site-theme-set="dark"]').click()
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('dark')
  })

  it('в «Авто» следит за темой системы, при явном выборе не реагирует', () => {
    const media = fakeMedia(false)
    mountSiteBar({ doc: document, store: memoryStore(), media })
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('light')
    media.change(true)
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('dark')
    q('[data-site-theme-set="light"]').click()
    media.change(true)
    expect(document.documentElement.getAttribute('data-bs-theme')).toBe('light')
  })
})

describe('полоса сайта: меню', () => {
  it('открывается кнопкой, закрывается подложкой и Escape', () => {
    mountSiteBar({ doc: document, store: memoryStore(), media: fakeMedia() })
    const menu = q('[data-site-menu]')
    const toggle = q('[data-site-menu-toggle]')
    toggle.click()
    expect(menu.hidden).toBe(false)
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    q('[data-site-menu-close]').click()
    expect(menu.hidden).toBe(true)
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    toggle.click()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(menu.hidden).toBe(true)
  })

  it('повторное нажатие на кнопку закрывает меню', () => {
    mountSiteBar({ doc: document, store: memoryStore(), media: fakeMedia() })
    const toggle = q('[data-site-menu-toggle]')
    toggle.click()
    toggle.click()
    expect(q('[data-site-menu]').hidden).toBe(true)
  })

  it('показывает «Вас помнит этот браузер» только когда есть запомненные участники', () => {
    mountSiteBar({ doc: document, store: memoryStore(), media: fakeMedia() })
    expect(q('[data-site-remembered]').hidden).toBe(true)

    const store = memoryStore()
    rememberParticipant(store, 128, { first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 0 })
    rememberParticipant(store, 119, { first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 0 })
    mountSiteBar({ doc: document, store, media: fakeMedia() })
    expect(q('[data-site-remembered]').hidden).toBe(false)
    expect(q('[data-site-remembered-text]').textContent).toBe('Зайцева Юлия · 2 события')
  })

  it('снятие обработчиков отключает кнопки', () => {
    const store = memoryStore()
    const off = mountSiteBar({ doc: document, store, media: fakeMedia() })
    off()
    q('[data-site-theme-cycle]').click()
    expect(store.data.has(THEME_KEY)).toBe(false)
  })
})
