// Что Django сообщает страницам-приложениям: кто смотрит и куда вести ссылки (адреса отдаёт `{% url %}`, а не код Vue).
export interface SiteLinks {
  home: string
  create: string
  mine: string
  login: string
  help: string
  stat: string
  about: string
}

export interface SiteContext {
  /** вошёл ли организатор */
  authenticated: boolean
  isSuperuser: boolean
  links: SiteLinks
}

export const DEFAULT_POSTER = '/static/events/img/default_poster.png'
