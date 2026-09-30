import { describe, expect, it } from 'vitest'
import { clearDraft, draftKey, loadDraft, saveDraft } from './draft'
import { readPinFromHash } from './link'
import { loadRememberedParticipant, rememberParticipant } from './remember'
import { emptyResults } from './results'
import { browserStore, memoryStore } from './storage'

describe('черновик', () => {
  const key = draftKey(7, '1234')

  it('сохраняется и читается обратно', () => {
    const store = memoryStore()
    const results = emptyResults(3)
    results[1] = { top: 2, zone: 0 }
    expect(saveDraft(store, key, { results, fields: { last_name: 'Зайцева' }, savedAt: 1000 })).toBe(true)
    expect(loadDraft(store, key, 3, false, 20)).toEqual({ results, fields: { last_name: 'Зайцева' }, savedAt: 1000 })
  })

  it('у разных событий и участников ключи разные', () => {
    expect(draftKey(7, '1234')).not.toBe(draftKey(8, '1234'))
    expect(draftKey(7, '1234')).not.toBe(draftKey(7, 'wo'))
  })

  it('черновик от другого числа трасс отбрасывается', () => {
    const store = memoryStore()
    saveDraft(store, key, { results: emptyResults(3), fields: null, savedAt: 1 })
    expect(loadDraft(store, key, 5, false, 20)).toBeNull()
  })

  it('испорченные данные не ломают чтение', () => {
    expect(loadDraft(memoryStore({ [key]: '{oops' }), key, 3, false, 20)).toBeNull()
    expect(loadDraft(memoryStore({ [key]: '{"v":"x"}' }), key, 3, false, 20)).toBeNull()
    expect(loadDraft(memoryStore(), key, 3, false, 20)).toBeNull()
  })

  it('удаляется', () => {
    const store = memoryStore()
    saveDraft(store, key, { results: emptyResults(3), fields: null, savedAt: 1 })
    clearDraft(store, key)
    expect(loadDraft(store, key, 3, false, 20)).toBeNull()
  })
})

describe('браузерное хранилище', () => {
  it('работает, а когда localStorage бросает исключения, молча сообщает о неудаче', () => {
    const store = browserStore()
    expect(store.set('rockevents-test', '1')).toBe(true)
    expect(store.get('rockevents-test')).toBe('1')
    store.remove('rockevents-test')
    expect(store.get('rockevents-test')).toBeNull()

    const broken = () => { throw new Error('quota') }
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')!
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      value: { getItem: broken, setItem: broken, removeItem: broken },
    })
    try {
      expect(store.set('k', 'v')).toBe(false)
      expect(store.get('k')).toBeNull()
      expect(() => store.remove('k')).not.toThrow()
    } finally {
      Object.defineProperty(window, 'localStorage', original)
    }
  })
})

describe('PIN из ссылки', () => {
  it('читает четыре цифры из фрагмента', () => {
    expect(readPinFromHash('#pin=1234')).toBe('1234')
    expect(readPinFromHash('#a=1&pin=0042')).toBe('0042')
  })

  it('остальное игнорирует', () => {
    for (const hash of ['', '#', '#pin=12', '#pin=12345', '#pin=abcd', '#mypin=1234', '?pin=1234']) {
      expect(readPinFromHash(hash), hash).toBeNull()
    }
  })
})

describe('запомненный участник', () => {
  it('хранит имя и группу, но не PIN', () => {
    const store = memoryStore()
    rememberParticipant(store, 7, { first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 })
    expect(loadRememberedParticipant(store, 7))
      .toEqual({ first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 })
    expect(loadRememberedParticipant(store, 8)).toBeNull()
    expect([...store.data.values()].join()).not.toMatch(/pin/i)
  })
})
