// Обёртка над localStorage: в приватном режиме и при переполнении он бросает исключения,
// а экран должен работать и без черновика.

export interface KeyValueStore {
  get(key: string): string | null
  /** false, если браузер не дал сохранить */
  set(key: string, value: string): boolean
  remove(key: string): void
  /** все ключи хранилища: страница ищет по ним записи о запомненных участниках */
  keys(): string[]
}

export function browserStore(): KeyValueStore {
  return {
    get(key) {
      try {
        return localStorage.getItem(key)
      } catch {
        return null
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, value)
        return true
      } catch {
        return false
      }
    },
    remove(key) {
      try {
        localStorage.removeItem(key)
      } catch {
        /* хранилище недоступно, удалять нечего */
      }
    },
    keys() {
      try {
        return Array.from({ length: localStorage.length }, (_, i) => localStorage.key(i)).filter((k): k is string => k !== null)
      } catch {
        return []
      }
    },
  }
}

/** Хранилище в памяти: для тестов. */
export function memoryStore(initial: Record<string, string> = {}): KeyValueStore & { data: Map<string, string> } {
  const data = new Map(Object.entries(initial))
  return {
    data,
    get: (key) => data.get(key) ?? null,
    set: (key, value) => {
      data.set(key, value)
      return true
    },
    remove: (key) => {
      data.delete(key)
    },
    keys: () => Array.from(data.keys()),
  }
}
