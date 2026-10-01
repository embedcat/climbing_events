import { describe, expect, it } from 'vitest'
import { forgetParticipant, listRememberedEvents, rememberParticipant } from './remember'
import { memoryStore } from './storage'

const who = { first_name: 'Юлия', last_name: 'Зайцева', gender: 'FEMALE', group_index: 1 }

describe('запомненные участники по всем событиям', () => {
  it('находит записи всех событий, свежие события первыми', () => {
    const store = memoryStore({ 'rockevents-pay:v1:5': '{}', 'rockevents-theme': 'dark' })
    rememberParticipant(store, 105, who)
    rememberParticipant(store, 128, { ...who, id: 7 })
    expect(listRememberedEvents(store).map((r) => r.eventId)).toEqual([128, 105])
    expect(listRememberedEvents(store)[0].who.id).toBe(7)
  })

  it('пропускает битые записи и чужие ключи', () => {
    const store = memoryStore({ 'rockevents-me:v1:9': '{не json', 'rockevents-me:v1:abc': '{}' })
    expect(listRememberedEvents(store)).toEqual([])
  })

  it('забытый участник из списка пропадает', () => {
    const store = memoryStore()
    rememberParticipant(store, 128, who)
    forgetParticipant(store, 128)
    expect(listRememberedEvents(store)).toEqual([])
  })
})
