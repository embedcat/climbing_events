// PIN из QR-кода на карточке лежит во фрагменте ссылки (`#pin=1234`), а не в query:
// фрагмент не уходит на сервер и не попадает в логи.

/** Четырёхзначный PIN из фрагмента ссылки или null. */
export function readPinFromHash(hash: string): string | null {
  const match = /(?:^#|&)pin=(\d{4})(?:&|$)/.exec(hash)
  return match ? match[1] : null
}
