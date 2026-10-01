// Тема оформления сайта: «Авто» (как в системе), «Светлая», «Тёмная». Выбор лежит в браузере и не требует входа.
// Применяем атрибутами на <html>: data-theme для наших цветов, data-bs-theme для Bootstrap на страницах Django.
// Первый раз выбор применяет короткий скрипт в <head> (events/snippets/sn-theme-init.html), чтобы страница не мигала;
// логика у них одна, поэтому ключ и значения менять только вместе.
import type { KeyValueStore } from './storage'

export type ThemePref = 'auto' | 'light' | 'dark'

export const THEME_KEY = 'rockevents-theme'
export const THEMES: readonly ThemePref[] = ['auto', 'light', 'dark']
export const THEME_LABEL: Record<ThemePref, string> = { auto: 'Авто', light: 'Светлая', dark: 'Тёмная' }

const isTheme = (value: string | null): value is ThemePref => value === 'auto' || value === 'light' || value === 'dark'

export function loadTheme(store: KeyValueStore): ThemePref {
  const value = store.get(THEME_KEY)
  return isTheme(value) ? value : 'auto'
}

export function saveTheme(store: KeyValueStore, pref: ThemePref): void {
  if (pref === 'auto') store.remove(THEME_KEY)
  else store.set(THEME_KEY, pref)
}

/** Кнопка в полосе сайта листает по кругу: авто, светлая, тёмная */
export function nextTheme(pref: ThemePref): ThemePref {
  return THEMES[(THEMES.indexOf(pref) + 1) % THEMES.length]
}

export function resolveTheme(pref: ThemePref, systemDark: boolean): 'light' | 'dark' {
  if (pref === 'auto') return systemDark ? 'dark' : 'light'
  return pref
}

/** «Авто» убирает data-theme: тогда цвета берутся из системной темы (prefers-color-scheme) */
export function applyTheme(root: HTMLElement, pref: ThemePref, systemDark: boolean): void {
  if (pref === 'auto') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', pref)
  root.setAttribute('data-bs-theme', resolveTheme(pref, systemDark))
}
