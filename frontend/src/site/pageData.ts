// Данные, которые Django кладёт в страницу тегом `{{ value|json_script:"id" }}`: первая страница каталога, ссылки, кто смотрит.
export function readPageData<T>(id: string, doc: Document = document): T | null {
  const text = doc.getElementById(id)?.textContent
  if (!text) return null
  try {
    return JSON.parse(text) as T
  } catch {
    return null
  }
}
