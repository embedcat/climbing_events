// Клавиатура матрицы. Какое действие вызывает нажатие: отдельно от состояния, чтобы проверять без браузера.
//
// Цифры берём из `key`, а не из `code`: на русской раскладке цифры верхнего ряда остаются цифрами.
// Поиск и сохранение берём из `code` (Slash, KeyS): на русской раскладке буква S и символ / лежат на других знаках.

export type KeyAction =
  | { type: 'move'; dRow: number; dCol: number }
  | { type: 'home' | 'end' | 'search' | 'backspace' | 'delete' | 'escape' | 'enter' | 'space' }
  | { type: 'digit'; digit: number }

export interface KeyLike {
  key: string
  code: string
  shiftKey: boolean
  ctrlKey: boolean
  metaKey: boolean
  altKey: boolean
}

const ARROWS: Record<string, [number, number]> = {
  ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1],
}

export const isSlash = (e: Pick<KeyLike, 'key' | 'code'>): boolean => e.code === 'Slash' || e.key === '/'

/** Ctrl+S (на Mac Cmd+S) работает из любого места страницы. */
export const isSaveShortcut = (e: Pick<KeyLike, 'code' | 'ctrlKey' | 'metaKey'>): boolean =>
  (e.ctrlKey || e.metaKey) && e.code === 'KeyS'

/** null — клавиша ничего не значит для матрицы, её не перехватываем. */
export function interpretKey(e: KeyLike): KeyAction | null {
  if (e.ctrlKey || e.metaKey || e.altKey) return null
  const arrow = ARROWS[e.key]
  if (arrow) return { type: 'move', dRow: arrow[0], dCol: arrow[1] }
  if (e.key === 'Tab') return { type: 'move', dRow: 0, dCol: e.shiftKey ? -1 : 1 }
  if (e.key === 'Home') return { type: 'home' }
  if (e.key === 'End') return { type: 'end' }
  if (isSlash(e)) return { type: 'search' }
  if (/^[0-9]$/.test(e.key)) return { type: 'digit', digit: Number(e.key) }
  if (e.key === 'Backspace') return { type: 'backspace' }
  if (e.key === 'Delete') return { type: 'delete' }
  if (e.key === 'Escape') return { type: 'escape' }
  if (e.key === 'Enter') return { type: 'enter' }
  if (e.key === ' ') return { type: 'space' }
  return null
}
