// Что Django сообщает экранам панели: разделы панели (боковое меню на компьютере, список на телефоне).
export interface PanelSection {
  url_name: string
  url: string
  title: string
  hint: string
  external: boolean
  current: boolean
}

export interface PanelSectionGroup {
  title: string
  items: PanelSection[]
}
