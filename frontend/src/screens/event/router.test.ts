import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { createRouter, eventPath, parseScreen } from './router'

beforeEach(() => { window.history.replaceState(null, '', '/e/7/') })

describe('адреса', () => {
  it('экран по адресу: все вкладки, анкета и оплата', () => {
    expect(parseScreen(7, '/e/7/')).toBe('info')
    expect(parseScreen(7, '/e/7')).toBe('info')
    expect(parseScreen(7, '/e/7/enter/')).toBe('enter')
    expect(parseScreen(7, '/e/7/participants/')).toBe('people')
    expect(parseScreen(7, '/e/7/results/')).toBe('results')
    expect(parseScreen(7, '/e/7/registration/')).toBe('reg')
    expect(parseScreen(7, '/e/7/pay/')).toBe('pay')
    expect(parseScreen(7, '/e/7/pay/done/')).toBe('paydone')
  })

  it('неизвестный адрес открывает «Инфо», адрес другого события — тоже', () => {
    expect(parseScreen(7, '/e/7/что-то/')).toBe('info')
    expect(parseScreen(7, '/e/70/results/')).toBe('info')
  })

  it('адрес по экрану; «готово» после регистрации живёт на адресе анкеты', () => {
    expect(eventPath(7, 'info')).toBe('/e/7/')
    expect(eventPath(7, 'people')).toBe('/e/7/participants/')
    expect(eventPath(7, 'regdone')).toBe('/e/7/registration/')
    expect(eventPath(7, 'paydone')).toBe('/e/7/pay/done/')
  })
})

describe('переходы', () => {
  const routers: Array<ReturnType<typeof createRouter>> = []
  const make = () => {
    const router = createRouter(7)
    routers.push(router)
    return router
  }
  afterEach(() => { routers.splice(0).forEach((r) => r.dispose()) })

  it('начинает с экрана из адреса страницы', () => {
    window.history.replaceState(null, '', '/e/7/results/?autorefresh')
    const router = make()
    expect(router.screen.value).toBe('results')
    expect(router.search.value).toBe('?autorefresh')
  })

  it('go меняет адрес без перезагрузки и добавляет запись в историю', () => {
    const router = make()
    const before = window.history.length
    router.go('people')
    expect(router.screen.value).toBe('people')
    expect(window.location.pathname).toBe('/e/7/participants/')
    expect(window.history.length).toBe(before + 1)
  })

  it('replace не добавляет запись в историю', () => {
    const router = make()
    const before = window.history.length
    router.go('enter', { replace: true })
    expect(window.location.pathname).toBe('/e/7/enter/')
    expect(window.history.length).toBe(before)
  })

  it('параметры адреса: номер участника на экране оплаты', () => {
    const router = make()
    router.go('pay', { query: { p: 386 } })
    expect(window.location.pathname + window.location.search).toBe('/e/7/pay/?p=386')
    expect(router.param('p')).toBe('386')
    expect(router.param('x')).toBeNull()
    expect(router.href('pay', { p: 5 })).toBe('/e/7/pay/?p=5')
  })

  it('кнопка «назад» возвращает прежний экран, в том числе «готово» после регистрации', () => {
    const router = make()
    router.go('reg')
    router.go('regdone')
    window.history.replaceState({ screen: 'reg' }, '', '/e/7/registration/')
    window.dispatchEvent(new PopStateEvent('popstate'))
    expect(router.screen.value).toBe('reg')
    window.history.replaceState(null, '', '/e/7/results/')
    window.dispatchEvent(new PopStateEvent('popstate'))
    expect(router.screen.value).toBe('results')
  })

  it('после dispose адрес больше не слушаем', () => {
    const router = createRouter(7)
    router.dispose()
    window.history.replaceState(null, '', '/e/7/results/')
    window.dispatchEvent(new PopStateEvent('popstate'))
    expect(router.screen.value).toBe('info')
  })
})
