import { afterEach, describe, expect, it } from 'vitest'
import { readPageData } from './pageData'

afterEach(() => { document.body.innerHTML = '' })

describe('данные страницы от Django', () => {
  it('читает JSON из тега script', () => {
    document.body.innerHTML = '<script id="d" type="application/json">{"a": [1, 2], "b": "текст"}</script>'
    expect(readPageData<{ a: number[], b: string }>('d')).toEqual({ a: [1, 2], b: 'текст' })
  })

  it('нет тега, пусто или битый JSON: null, а не исключение', () => {
    expect(readPageData('нет')).toBeNull()
    document.body.innerHTML = '<script id="e" type="application/json"></script><script id="f" type="application/json">{oops</script>'
    expect(readPageData('e')).toBeNull()
    expect(readPageData('f')).toBeNull()
  })
})
