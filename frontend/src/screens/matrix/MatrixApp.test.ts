import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MatrixPayload } from '../../api/matrix'
import { memoryStore } from '../../domain/storage'
import { apiError, networkError } from '../entry/testing'
import MatrixApp from './MatrixApp.vue'
import { fakeMatrixApi, standardMatrix } from './testing'
import { useMatrixFlow } from './useMatrixFlow'

const EVENT_ID = 7

/** jsdom не знает matchMedia: подставляем, чтобы выбрать матрицу (широкий экран) или шаги на телефоне. */
function stubMedia(wide: boolean): void {
  window.matchMedia = ((query: string) => ({
    matches: wide, media: query, addEventListener: () => {}, removeEventListener: () => {},
  })) as unknown as typeof window.matchMedia
}

async function mountApp(payload: MatrixPayload = standardMatrix(), options: { wide?: boolean; store?: ReturnType<typeof memoryStore> } = {}) {
  stubMedia(options.wide ?? true)
  const { api, state } = fakeMatrixApi(payload)
  const store = options.store ?? memoryStore()
  const flow = useMatrixFlow({ eventId: EVENT_ID, api, store })
  const wrapper = mount(MatrixApp, {
    props: { flow, resultsUrl: '/e/7/results/', manageUrl: '/e/7/admin_actions/' }, attachTo: document.body,
  })
  await flushPromises()
  return { wrapper, flow, api, state, store }
}

const grid = (w: VueWrapper) => w.get('.re-mx-wrap')
const rowOf = (w: VueWrapper, last: string) => w.findAll('.re-mx tbody tr').find((r) => r.text().includes(last))!
const cellsOf = (row: ReturnType<typeof rowOf>) => row.findAll('td.c')
const press = async (w: VueWrapper, key: string, init: KeyboardEventInit = {}) => {
  await grid(w).trigger('keydown', { key, ...init })
}
const mouse = async (cell: ReturnType<typeof rowOf>) => { await cell.trigger('mousedown') }
const status = (w: VueWrapper) => w.get('.re-mx-status').text().replace(/\s+/g, ' ')
const save = (w: VueWrapper) => w.get('.re-mx-btn.is-primary')

beforeEach(() => { document.body.innerHTML = '' })
afterEach(() => { vi.useRealTimers() })

describe('матрица', () => {
  it('строки по сету, закреплённые имя и PIN, счёт и место, счётчики трасс', async () => {
    const { wrapper } = await mountApp()
    const names = wrapper.findAll('.re-mx tbody .nmt').map((n) => n.text())
    expect(names).toEqual(['Гаврилов Олег', 'Зайцева Юлия', 'Титова Полина'])
    const row = rowOf(wrapper, 'Зайцева')
    expect(row.find('.s-pin').text()).toBe('5555')
    expect(row.find('.s-place').text()).toBe('1')
    expect(rowOf(wrapper, 'Титова').find('.s-place').text()).toBe('—')
    expect(rowOf(wrapper, 'Титова').text()).toContain('нет результата')
    expect(wrapper.findAll('thead th.rh')).toHaveLength(6)
    expect(wrapper.findAll('thead tr + tr th.sh').map((t) => t.text())).toEqual(['1', '1', '1', '0', '0', '0'])
  })

  it('ячейки FL и RP, у участника без результата точки', async () => {
    const { wrapper } = await mountApp()
    const cells = cellsOf(rowOf(wrapper, 'Зайцева'))
    expect(cells.slice(0, 3).map((c) => c.text())).toEqual(['FL', 'FL', 'FL'])
    expect(cells[0].classes()).toContain('v1')
    expect(cellsOf(rowOf(wrapper, 'Титова'))[0].classes()).toContain('v0')
  })

  it('курсор на первой ячейке первой строки, строка и столбец выделены', async () => {
    const { wrapper } = await mountApp()
    expect(cellsOf(rowOf(wrapper, 'Гаврилов'))[0].classes()).toContain('cur')
    expect(rowOf(wrapper, 'Гаврилов').classes()).toContain('row-cur')
    expect(wrapper.findAll('col')[3].classes()).toContain('col-cur')
  })

  it('клавиши 2, 1, 0 пишут значения и двигают курсор, изменения помечены', async () => {
    const { wrapper } = await mountApp()
    await press(wrapper, '2')
    await press(wrapper, '1')
    await press(wrapper, '0')
    const cells = cellsOf(rowOf(wrapper, 'Гаврилов'))
    expect(cells.slice(0, 4).map((c) => c.text())).toEqual(['RP', 'FL', '', ''])
    expect(cells.slice(0, 3).every((c) => c.classes().includes('dirty'))).toBe(true)
    expect(cells[3].classes()).toContain('cur')
    expect(status(wrapper)).toBe('Не сохранено: 3 результата у 1 участника · черновик хранится в этом браузере')
    expect(save(wrapper).text()).toBe('Сохранить · 3')
    expect(rowOf(wrapper, 'Гаврилов').find('.s-score').classes()).toContain('stale')
  })

  it('клавиши в поле поиска матрицу не трогают', async () => {
    const { wrapper } = await mountApp()
    await wrapper.get('#re-search').trigger('keydown', { key: '2' })
    expect(wrapper.findAll('td.dirty')).toHaveLength(0)
  })

  it('клик по ячейке ставит курсор, второй клик по ней переключает значение', async () => {
    const { wrapper } = await mountApp()
    const cell = () => cellsOf(rowOf(wrapper, 'Титова'))[2]
    await mouse(cell())
    expect(cell().classes()).toContain('cur')
    await mouse(cell())
    expect(cell().text()).toBe('FL')
    await mouse(cell())
    expect(cell().text()).toBe('RP')
  })

  it('фильтры меняют строки, счётчик «без результата» и подсказка про пустой фильтр', async () => {
    const { wrapper } = await mountApp()
    const button = (text: string) => wrapper.findAll('.re-mx-seg button').find((b) => b.text().startsWith(text))!
    await button('1').trigger('click')
    expect(wrapper.findAll('.re-mx tbody .nmt').map((n) => n.text())).toEqual(['Андреев Иван', 'Борисов Пётр', 'Власов Глеб'])
    await button('Спорт').trigger('click')
    expect(wrapper.find('.re-mx td.empty').text()).toContain('Под этот фильтр никто не попал')
    // сет снова «Все», группа ещё «Спорт»: в ней без результата только Гаврилов
    await button('Все').trigger('click')
    await wrapper.get('.re-mx-chip').trigger('click')
    expect(wrapper.get('.re-mx-chip').text()).toContain('Без результата: 1')
    expect(wrapper.findAll('.re-mx tbody .nmt').map((n) => n.text())).toEqual(['Гаврилов Олег'])
  })

  it('направление курсора переключается и работает', async () => {
    const { wrapper } = await mountApp()
    await wrapper.findAll('.re-mx-seg button').find((b) => b.text().includes('по трассе'))!.trigger('click')
    await press(wrapper, '2')
    expect(cellsOf(rowOf(wrapper, 'Зайцева'))[0].classes()).toContain('cur')
  })

  it('поиск по PIN: список, выбор клавишей Enter переводит курсор и переключает сет', async () => {
    const { wrapper } = await mountApp()
    const input = wrapper.get('#re-search')
    await input.setValue('2222')
    expect(wrapper.get('[role="listbox"]').text()).toContain('Борисов')
    expect(wrapper.get('[role="listbox"]').text()).toContain('вне фильтра, переключу')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(cellsOf(rowOf(wrapper, 'Борисов'))[0].classes()).toContain('cur')
    expect(wrapper.find('[role="listbox"]').exists()).toBe(false)
  })

  it('поиск: никого не нашли', async () => {
    const { wrapper } = await mountApp()
    await wrapper.get('#re-search').setValue('Яяя')
    expect(wrapper.get('[role="listbox"]').text()).toContain('Никого не нашли')
  })

  it('Ctrl+S сохраняет, после сохранения всё чисто и есть сообщение', async () => {
    const { wrapper, api } = await mountApp()
    await press(wrapper, '2')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', code: 'KeyS', ctrlKey: true, cancelable: true }))
    await flushPromises()
    expect(api.save).toHaveBeenCalledOnce()
    expect(wrapper.findAll('td.dirty')).toHaveLength(0)
    expect(status(wrapper)).toBe('Сохранено 1 результат у 1 участника. Баллы и места пересчитаны.')
    expect(save(wrapper).attributes('disabled')).toBeDefined()
    expect(rowOf(wrapper, 'Гаврилов').text()).not.toContain('нет результата')
  })

  it('без изменений кнопки сохранить и отменить недоступны', async () => {
    const { wrapper } = await mountApp()
    expect(status(wrapper)).toBe('Все изменения сохранены')
    expect(save(wrapper).attributes('disabled')).toBeDefined()
    const discard = wrapper.findAll('.re-mx-actions .re-mx-btn')[1]
    expect(discard.attributes('disabled')).toBeDefined()
  })

  it('«Отменить изменения» просит подтвердить, а через три секунды отказывается от просьбы', async () => {
    vi.useFakeTimers()
    const { wrapper } = await mountApp()
    await press(wrapper, '2')
    const discard = () => wrapper.findAll('.re-mx-actions .re-mx-btn')[1]
    await discard().trigger('click')
    expect(discard().text()).toBe('Точно отменить 1?')
    vi.advanceTimersByTime(3100)
    await flushPromises()
    expect(discard().text()).toBe('Отменить изменения')
    await discard().trigger('click')
    await discard().trigger('click')
    expect(wrapper.findAll('td.dirty')).toHaveLength(0)
    expect(status(wrapper)).toBe('Все изменения сохранены')
  })

  it('нет связи при сохранении: плашка с «Повторить», черновик остался', async () => {
    const { wrapper, api } = await mountApp()
    await press(wrapper, '2')
    api.save.mockRejectedValueOnce(networkError())
    await save(wrapper).trigger('click')
    await flushPromises()
    const banner = wrapper.get('.re-banner.is-error')
    expect(banner.text()).toContain('Не удалось сохранить: нет связи с сервером')
    expect(wrapper.findAll('td.dirty')).toHaveLength(1)
    await banner.get('.re-mx-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.re-banner.is-error').exists()).toBe(false)
    expect(wrapper.findAll('td.dirty')).toHaveLength(0)
  })

  it('восстановленный черновик: плашка с «Сохранить» и «Отбросить»', async () => {
    const first = await mountApp()
    await press(first.wrapper, '2')
    first.wrapper.unmount()
    const { wrapper, api } = await mountApp(standardMatrix(), { store: first.store })
    expect(wrapper.get('.re-banner.is-info').text()).toContain('Восстановлен несохранённый черновик: 1 результат')
    await wrapper.findAll('.re-banner.is-info .re-mx-btn').find((b) => b.text() === 'Сохранить')!.trigger('click')
    await flushPromises()
    expect(api.save).toHaveBeenCalledOnce()
    expect(wrapper.find('.re-banner.is-info').exists()).toBe(false)
  })

  it('«Отбросить» убирает восстановленное', async () => {
    const first = await mountApp()
    await press(first.wrapper, '2')
    first.wrapper.unmount()
    const { wrapper } = await mountApp(standardMatrix(), { store: first.store })
    await wrapper.findAll('.re-banner.is-info .re-mx-btn').find((b) => b.text() === 'Отбросить')!.trigger('click')
    expect(wrapper.findAll('td.dirty')).toHaveLength(0)
    expect(wrapper.find('.re-banner.is-info').exists()).toBe(false)
  })

  it('нет прав: сообщение вместо матрицы', async () => {
    stubMedia(true)
    const { api } = fakeMatrixApi(standardMatrix())
    api.getMatrix.mockRejectedValueOnce(apiError('error', 403))
    const flow = useMatrixFlow({ eventId: EVENT_ID, api, store: memoryStore() })
    const wrapper = mount(MatrixApp, { props: { flow, resultsUrl: '/r', manageUrl: '/m' }, attachTo: document.body })
    await flushPromises()
    expect(wrapper.text()).toContain('доступен только организатору')
    expect(wrapper.find('table').exists()).toBe(false)
  })

  it('шапка: сведения о событии и ссылки', async () => {
    const { wrapper } = await mountApp()
    expect(wrapper.get('.re-mx-meta').text()).toBe('6 участников · 6 трасс · PROP, от количества пролазов')
    expect(wrapper.findAll('.re-mx-links a').map((a) => a.attributes('href'))).toEqual(['/e/7/results/', '/e/7/admin_actions/'])
  })
})

describe('матрица, французская система', () => {
  const french = () => standardMatrix({ score_type: 'FR' })

  it('два подстолбца на трассу, набор цифр и запись по Enter', async () => {
    const { wrapper } = await mountApp(french())
    expect(wrapper.findAll('thead tr + tr th').slice(0, 4).map((t) => t.text())).toEqual(['Т', 'З', 'Т', 'З'])
    await press(wrapper, '3')
    const row = rowOf(wrapper, 'Гаврилов')
    expect(cellsOf(row)[0].classes()).toContain('editing')
    expect(cellsOf(row)[0].text()).toBe('3')
    expect(cellsOf(row)[0].find('.caret').exists()).toBe(true)
    await press(wrapper, 'Enter')
    expect(cellsOf(row).slice(0, 3).map((c) => c.text())).toEqual(['3', '3', ''])
    expect(cellsOf(row)[1].classes()).toContain('cur')
  })

  it('зона позже топа: красная ячейка, «нельзя сохранить», кнопка «Перейти»', async () => {
    const { wrapper } = await mountApp(french())
    await press(wrapper, '1')
    await press(wrapper, 'Enter')
    await press(wrapper, '4')
    await press(wrapper, 'Enter')
    const row = rowOf(wrapper, 'Гаврилов')
    expect(cellsOf(row)[1].classes()).toContain('bad')
    expect(status(wrapper)).toContain('Нельзя сохранить: зона позже топа, трасса 1 у участника Гаврилов Олег')
    expect(save(wrapper).attributes('disabled')).toBeDefined()
    await press(wrapper, 'ArrowUp')
    await wrapper.get('.re-mx-goto').trigger('click')
    expect(cellsOf(row)[1].classes()).toContain('cur')
  })

  it('в шапке число топов по трассе', async () => {
    const { wrapper } = await mountApp(french())
    expect(wrapper.findAll('thead th.rh')[0].text()).toContain('1т')
  })
})

describe('на телефоне', () => {
  const phone = (payload?: MatrixPayload) => mountApp(payload, { wide: false })

  it('вместо матрицы шаги: по участнику и по трассе, фильтры', async () => {
    const { wrapper } = await phone()
    expect(wrapper.find('.re-mx-wrap').exists()).toBe(false)
    expect(wrapper.findAll('.re-ph-modes button').map((b) => b.text())).toEqual(['По участнику', 'По трассе'])
    expect(wrapper.findAll('.re-ph-row').map((r) => r.find('b').text())).toEqual(['Гаврилов Олег', 'Зайцева Юлия', 'Титова Полина'])
    expect(wrapper.findAll('.re-ph-state').map((s) => s.text())).toEqual(['нет результата', 'внесён', 'нет результата'])
  })

  it('участник → плитки → «Следующий», отметки попадают в черновик и уходят одним запросом', async () => {
    const { wrapper, api } = await phone()
    await wrapper.findAll('.re-ph-row')[0].trigger('click')
    expect(wrapper.find('.re-ph-list').exists()).toBe(false)
    expect(wrapper.get('.re-who-name').text()).toBe('Гаврилов Олег')
    expect(wrapper.get('.re-ph-edit .re-banner').text()).toContain('Результат ещё не внесён')
    const tile = (n: number) => wrapper.get(`.re-tile[aria-label^="Трасса ${n}:"]`)
    await tile(1).trigger('click')
    await tile(2).trigger('click')
    await tile(2).trigger('click')
    expect(tile(1).attributes('aria-label')).toBe('Трасса 1: flash')
    expect(tile(2).attributes('aria-label')).toBe('Трасса 2: redpoint')
    expect(status(wrapper)).toContain('Не сохранено: 2 результата у 1 участника')

    await wrapper.findAll('.re-ph-nav .re-btn')[1].trigger('click')
    expect(wrapper.get('.re-who-name').text()).toBe('Зайцева Юлия')
    await save(wrapper).trigger('click')
    await flushPromises()
    expect(api.save.mock.calls[0][1]).toHaveLength(1)
  })

  it('«К списку» возвращает к списку, у внесённого результаты видны', async () => {
    const { wrapper } = await phone()
    await wrapper.findAll('.re-ph-row')[1].trigger('click')
    expect(wrapper.get('.re-tile[aria-label^="Трасса 1:"]').attributes('aria-label')).toBe('Трасса 1: flash')
    await wrapper.get('.re-who .re-linkbtn').trigger('click')
    expect(wrapper.find('.re-ph-list').exists()).toBe(true)
  })

  it('по трассе: выбор трассы, кнопки нет/FL/RP для каждого участника', async () => {
    const { wrapper } = await phone()
    await wrapper.findAll('.re-ph-modes button')[1].trigger('click')
    expect(wrapper.find('.re-ph-routenav select').exists()).toBe(true)
    const rows = wrapper.findAll('.re-ph-route-row')
    expect(rows).toHaveLength(3)
    await rows[0].findAll('.re-ph-three button')[2].trigger('click')
    await rows[2].findAll('.re-ph-three button')[1].trigger('click')
    expect(rows[0].findAll('.re-ph-three button')[2].attributes('aria-pressed')).toBe('true')
    expect(status(wrapper)).toContain('Не сохранено: 2 результата у 2 участников')

    await wrapper.findAll('.re-ph-nav .re-btn')[1].trigger('click')
    expect((wrapper.get('.re-ph-routenav select').element as HTMLSelectElement).value).toBe('1')
    expect(wrapper.findAll('.re-ph-route-row')[0].findAll('.re-ph-three button')[0].attributes('aria-pressed')).toBe('true')
  })

  it('по трассе во французской системе: два счётчика попыток', async () => {
    const { wrapper } = await phone(standardMatrix({ score_type: 'FR' }))
    await wrapper.findAll('.re-ph-modes button')[1].trigger('click')
    const first = wrapper.findAll('.re-ph-route-row')[0]
    expect(first.findAll('.re-stepper')).toHaveLength(2)
    await first.get('button[aria-label$="Топ: на попытку больше"]').trigger('click')
    expect(first.findAll('output').map((o) => o.text())).toEqual(['1', '1'])
  })

  it('на телефоне нет подсказок по клавишам и панели фильтров матрицы', async () => {
    const { wrapper } = await phone()
    expect(wrapper.find('.re-mx-keys').exists()).toBe(false)
    expect(wrapper.find('.re-mx-toolbar').exists()).toBe(false)
  })

  it('кнопки панели сохранения короткие', async () => {
    const { wrapper } = await phone()
    expect(wrapper.findAll('.re-mx-actions .re-mx-btn').map((b) => b.text())).toEqual(['Обновить', 'Отменить', 'Сохранить'])
  })
})
