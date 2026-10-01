import { describe, expect, it } from 'vitest'
import { makePerson, standardPeople } from '../screens/event/testing'
import { cityLine, emptyFilters, filterPeople, isFiltered, matchesQuery, personMeta, shortPersonName } from './people'

describe('фильтры списка участников', () => {
  const people = standardPeople()

  it('без фильтров все, по фамилии', () => {
    expect(filterPeople(people, emptyFilters()).map((p) => p.last_name)).toEqual(['Зайцева', 'Кузнецов', 'Орлова', 'Соколов'])
    expect(isFiltered(emptyFilters())).toBe(false)
  })

  it('пол, группа и сет вместе', () => {
    expect(filterPeople(people, { ...emptyFilters(), gender: 'FEMALE' }).map((p) => p.last_name)).toEqual(['Зайцева', 'Орлова'])
    expect(filterPeople(people, { ...emptyFilters(), group: 1 }).map((p) => p.last_name)).toEqual(['Зайцева', 'Соколов'])
    expect(filterPeople(people, { ...emptyFilters(), set: 0 }).map((p) => p.last_name)).toEqual(['Кузнецов', 'Соколов'])
    expect(filterPeople(people, { gender: 'FEMALE', group: 0, set: 1, q: '' }).map((p) => p.last_name)).toEqual(['Орлова'])
  })

  it('поиск по части фамилии или имени, регистр не важен, пробелы по краям тоже', () => {
    expect(matchesQuery(people[0], ' ЗАЙЦ ')).toBe(true)
    expect(matchesQuery(people[0], 'юли')).toBe(true)
    expect(matchesQuery(people[0], 'юлия зайцева')).toBe(true) // имя и фамилия в любом порядке
    expect(matchesQuery(people[0], 'зайцева кузнецов')).toBe(false)
    expect(filterPeople(people, { ...emptyFilters(), q: 'ов' }).map((p) => p.last_name)).toEqual(['Кузнецов', 'Орлова', 'Соколов'])
  })

  it('любой заданный фильтр считается активным', () => {
    expect(isFiltered({ ...emptyFilters(), q: ' ' })).toBe(false)
    expect(isFiltered({ ...emptyFilters(), q: 'я' })).toBe(true)
    expect(isFiltered({ ...emptyFilters(), set: 0 })).toBe(true)
  })

  it('сортировка по-русски: «Ё» и «Е» рядом, заглавные и строчные вместе', () => {
    const list = [makePerson('Ёлкин', 'А'), makePerson('Егоров', 'А'), makePerson('арбузов', 'А'), makePerson('Яковлев', 'А')]
    expect(filterPeople(list, emptyFilters()).map((p) => p.last_name)).toEqual(['арбузов', 'Егоров', 'Ёлкин', 'Яковлев'])
  })
})

describe('подписи', () => {
  it('города под списком: три самых частых и сколько ещё', () => {
    const people = [
      ...Array.from({ length: 5 }, () => makePerson('А', 'А', { city: 'Москва' })),
      ...Array.from({ length: 3 }, () => makePerson('Б', 'Б', { city: 'Тверь' })),
      makePerson('В', 'В', { city: 'Казань' }),
      makePerson('Г', 'Г', { city: 'Уфа' }),
      makePerson('Д', 'Д', { city: 'Омск' }),
      makePerson('Е', 'Е', { city: ' ' }),
    ]
    expect(cityLine(people)).toBe('Москва 5 · Тверь 3 · Казань 1 · ещё 2 города')
  })

  it('мало городов — без «ещё», никто не указал — пустая строка', () => {
    expect(cityLine([makePerson('А', 'А', { city: 'Москва' })])).toBe('Москва 1')
    expect(cityLine([makePerson('А', 'А', { city: '' })])).toBe('')
  })

  it('строка данных и короткое имя', () => {
    expect(personMeta(makePerson('Иванов', 'Иван', { birth_year: 1996, grade: '2 сп.р.', city: 'Москва', team: 'Магнезия' })))
      .toBe('1996 · 2 сп.р. · Москва · «Магнезия»')
    expect(personMeta(makePerson('Иванов', 'Иван', { birth_year: null, grade: '', city: '', team: '' }))).toBe('')
    expect(shortPersonName(makePerson('Зайцева', 'Юлия'))).toBe('Зайцева Ю.')
  })
})
