import { describe, expect, it } from 'vitest'
import { makePerson } from '../screens/event/testing'
import { matchesPanelQuery } from './people'

describe('поиск организатора по участникам', () => {
  const yulia = makePerson('Зайцева', 'Юлия', { pin: 8335 })
  const bare = makePerson('Орлова', 'Анна')

  it('пустой запрос находит всех', () => {
    expect(matchesPanelQuery(yulia, '')).toBe(true)
    expect(matchesPanelQuery(yulia, '   ')).toBe(true)
  })

  it('имя ищется в обоих порядках, как на публичной вкладке', () => {
    expect(matchesPanelQuery(yulia, 'зайц')).toBe(true)
    expect(matchesPanelQuery(yulia, 'юлия зайцева')).toBe(true)
    expect(matchesPanelQuery(yulia, 'орл')).toBe(false)
  })

  it('цифры ищут по началу PIN', () => {
    expect(matchesPanelQuery(yulia, '83')).toBe(true)
    expect(matchesPanelQuery(yulia, '8335')).toBe(true)
    expect(matchesPanelQuery(yulia, '35')).toBe(false)
  })

  it('у участника без PIN цифры ничего не находят', () => {
    expect(matchesPanelQuery(bare, '1')).toBe(false)
  })
})
