// Результаты события: `/api/events/<id>/results/`
import type { Http } from './http'
import type { Gender } from './entry'
import type { RouteResult } from '../domain/results'

/** Строка таблицы. Только то, что видно всем: без PIN, email и телефона. */
export interface ResultRow {
  id: number
  last_name: string
  first_name: string
  gender: Gender
  birth_year: number | null
  /** подпись разряда: «б/р», «КМС» */
  grade: string
  city: string
  team: string
  set_index: number
  set: string
  /** null — результат ещё не введён, места нет */
  place: number | null
  score: number
  /** счёт строкой для систем, где он не число: «3T7 4z9» у французской, «5/2» у NUM */
  score_view: string
  /** пусто, если результат не введён или события скрывают прохождения */
  results: RouteResult[]
  counted: boolean[]
}

export interface RoutePoints {
  flash: number
  redpoint: number
}

export interface ResultsTable {
  gender: Gender
  group_index: number
  group: string
  /** стоимость трасс в очках; null, если для системы подсчёта или по настройкам события она не показывается */
  route_points: RoutePoints[] | null
  /** с результатом, по местам */
  ranked: ResultRow[]
  /** без результата, без места */
  waiting: ResultRow[]
}

export interface ResultsRoute {
  number: number
  grade: string | null
  color: string | null
}

export interface ResultsPayload {
  event: {
    id: number
    title: string
    date: string
    gym: string
    /** SUM | PROP | TBL | NUM | FR */
    score_type: string
    routes_num: number
    /** ввод открыт и событие не завершено: результаты меняются */
    is_live: boolean
    /** событие завершено: итоговые результаты */
    is_expired: boolean
    /** организатор или суперпользователь: можно править результаты */
    can_edit: boolean
  }
  display: {
    /** false: прохождения по трассам скрыты, остаются место, имя и счёт */
    is_view_full_results: boolean
    /** в зачёт идут N лучших трасс; 0 — все */
    best_routes_num: number
  }
  routes: ResultsRoute[]
  /** пусто, если группа одна */
  groups: string[]
  tables: ResultsTable[]
}

export interface ResultsApi {
  getResults(eventId: number): Promise<ResultsPayload>
}

export function createResultsApi(http: Http): ResultsApi {
  return { getResults: (eventId) => http.get(`/api/events/${eventId}/results/`) }
}
