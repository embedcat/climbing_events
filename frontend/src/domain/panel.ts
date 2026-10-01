// Панель события: подписи переключателей и служебных действий, чек-лист подготовки.
import type { ChecklistItem, PanelAction, PanelFlag } from '../api/panel'

export const FLAG_INFO: { flag: PanelFlag, title: string, hint: string }[] = [
  { flag: 'is_published', title: 'Событие опубликовано', hint: 'Видно на главной и по ссылке' },
  { flag: 'is_registration_open', title: 'Регистрация открыта', hint: 'Анкета и кнопка «Зарегистрироваться»' },
  { flag: 'is_enter_result_allowed', title: 'Ввод результатов открыт', hint: 'Вкладка «Ввод» принимает PIN' },
  { flag: 'is_results_allowed', title: 'Результаты открыты', hint: 'Таблицы, места и призёры' },
]

export interface ActionInfo {
  title: string
  hint: string
  /** вопрос в окне подтверждения */
  question: string
  danger: boolean
  /** что показать после выполнения */
  done: string
}

export const ACTION_INFO: Record<PanelAction, ActionInfo> = {
  update_score: {
    title: 'Пересчитать результаты', hint: 'Заново считает баллы и места',
    question: 'Пересчитать баллы трасс и участников?', danger: false, done: 'Результаты пересчитаны',
  },
  clear_results: {
    title: 'Удалить результаты', hint: 'Участники остаются, результаты стираются',
    question: 'Удалить результаты всех участников? Отметки по трассам пропадут, вернуть их нельзя.', danger: true,
    done: 'Результаты удалены',
  },
  clear_event: {
    title: 'Очистить событие', hint: 'Удаляет участников, трассы и прохождения',
    question: 'Удалить всех участников, трассы и прохождения? Вернуть их нельзя.', danger: true,
    done: 'Событие очищено',
  },
  remove_event: {
    title: 'Удалить событие', hint: 'Удаляет событие целиком',
    question: 'Удалить событие полностью вместе с участниками и результатами? Вернуть его нельзя.', danger: true,
    done: 'Событие удалено',
  },
  mock_data: {
    title: 'Тестовые данные', hint: 'Заменяет участников 50 случайными с результатами, для отладки',
    question: 'Удалить всех участников и создать 50 случайных с результатами?', danger: true,
    done: 'Тестовые данные созданы',
  },
}

/** Порядок в окне служебных действий; тестовые данные видит только суперпользователь. */
export const ACTION_ORDER: PanelAction[] = ['update_score', 'clear_results', 'clear_event', 'remove_event', 'mock_data']

export interface ChecklistRow {
  id: ChecklistItem['id']
  title: string
  hint: string
  href: string
  done: boolean
  optional: boolean
}

/** Строки чек-листа: что сделано и куда идти, чтобы доделать. Публикация — это переключатель на этой же странице. */
export function checklistRows(items: ChecklistItem[], eventId: number): ChecklistRow[] {
  return items.map((item) => {
    const optional = Boolean(item.optional)
    switch (item.id) {
      case 'description':
        return {
          id: item.id, title: 'Описание и афиша', optional, done: item.done, href: `/e/${eventId}/admin_description/`,
          hint: item.done ? 'заполнено' : `замените текст по умолчанию${item.poster ? '' : ' и добавьте афишу'}`,
        }
      case 'pay':
        return {
          id: item.id, title: 'Оплата взноса', optional, done: item.done, href: `/e/${eventId}/pay_settings/`,
          hint: item.done ? (item.price ? `${item.price} ₽` : 'настроена') : 'выключена, можно пропустить',
        }
      default:
        return {
          id: item.id, title: 'Опубликовать событие', optional, done: item.done, href: '#re-switch-is_published',
          hint: item.done ? 'опубликовано' : 'участники пока не видят',
        }
    }
  })
}

export interface ChecklistProgress {
  done: number
  total: number
  /** карточка нужна, пока не сделано обязательное */
  open: boolean
}

export function checklistProgress(items: ChecklistItem[]): ChecklistProgress {
  const required = items.filter((item) => !item.optional)
  const done = required.filter((item) => item.done).length
  return { done, total: required.length, open: done < required.length }
}

/** Ссылки для монитора в зале: таблица обновляется сама, отдельно мужская и женская. */
export function hallLinks(eventId: number, origin: string): { gender: 'М' | 'Ж', url: string }[] {
  const base = `${origin}/e/${eventId}/results/?autorefresh`
  return [{ gender: 'М', url: `${base}&m` }, { gender: 'Ж', url: `${base}&f` }]
}
