import { describe, expect, it } from 'vitest'
import { memoryStore } from './storage'
import { applyTheme, loadTheme, nextTheme, resolveTheme, saveTheme, THEME_KEY } from './theme'

describe('тема оформления', () => {
  it('по умолчанию «Авто»; мусор в хранилище тоже читается как «Авто»', () => {
    expect(loadTheme(memoryStore())).toBe('auto')
    expect(loadTheme(memoryStore({ [THEME_KEY]: 'розовая' }))).toBe('auto')
  })

  it('сохраняет светлую и тёмную, а «Авто» стирает запись', () => {
    const store = memoryStore()
    saveTheme(store, 'dark')
    expect(store.data.get(THEME_KEY)).toBe('dark')
    expect(loadTheme(store)).toBe('dark')
    saveTheme(store, 'auto')
    expect(store.data.has(THEME_KEY)).toBe(false)
  })

  it('кнопка листает по кругу: авто, светлая, тёмная', () => {
    expect(nextTheme('auto')).toBe('light')
    expect(nextTheme('light')).toBe('dark')
    expect(nextTheme('dark')).toBe('auto')
  })

  it('«Авто» берёт тему системы, явный выбор от неё не зависит', () => {
    expect(resolveTheme('auto', true)).toBe('dark')
    expect(resolveTheme('auto', false)).toBe('light')
    expect(resolveTheme('light', true)).toBe('light')
    expect(resolveTheme('dark', false)).toBe('dark')
  })

  it('ставит data-theme для явного выбора и data-bs-theme всегда', () => {
    const root = document.createElement('html')
    applyTheme(root, 'dark', false)
    expect(root.getAttribute('data-theme')).toBe('dark')
    expect(root.getAttribute('data-bs-theme')).toBe('dark')
    applyTheme(root, 'auto', true)
    expect(root.hasAttribute('data-theme')).toBe(false)
    expect(root.getAttribute('data-bs-theme')).toBe('dark')
    applyTheme(root, 'auto', false)
    expect(root.getAttribute('data-bs-theme')).toBe('light')
  })
})
