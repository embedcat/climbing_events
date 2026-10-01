// Анкета участника: при регистрации и при вводе без регистрации. Какие поля показывать и какие обязательны,
// решает событие.
import type { Gender, RegistrationPayload } from '../../api/entry'

/** Что анкете нужно знать о событии. Его отдают и конфигурация ввода, и страница события. */
export interface RegistrationConfig {
  registration_fields: string[]
  required_fields: string[]
  /** пусто, если группа одна */
  groups: string[]
  /** пусто, если сет один */
  sets: unknown[]
}

export interface RegistrationForm {
  last_name: string
  first_name: string
  gender: '' | Gender
  /** -1 — не выбрано */
  group_index: number
  set_index: number
  birth_year: string
  city: string
  team: string
  grade: string
  email: string
  phone_number: string
}

export type TextField = 'birth_year' | 'city' | 'team' | 'email' | 'phone_number'

/** Необязательные текстовые поля анкеты: подпись, подсказка для клавиатуры. */
export const TEXT_FIELDS: Array<{ name: TextField; label: string; inputmode: string; autocomplete: string }> = [
  { name: 'birth_year', label: 'Год рождения', inputmode: 'numeric', autocomplete: 'bday-year' },
  { name: 'city', label: 'Город', inputmode: 'text', autocomplete: 'address-level2' },
  { name: 'team', label: 'Команда', inputmode: 'text', autocomplete: 'organization' },
  { name: 'email', label: 'Email', inputmode: 'email', autocomplete: 'email' },
  { name: 'phone_number', label: 'Телефон', inputmode: 'tel', autocomplete: 'tel' },
]

export const emptyForm = (): RegistrationForm => ({
  last_name: '', first_name: '', gender: '', group_index: -1, set_index: -1,
  birth_year: '', city: '', team: '', grade: '', email: '', phone_number: '',
})

const hasField = (config: RegistrationConfig, name: string): boolean => config.registration_fields.includes(name)
const isRequired = (config: RegistrationConfig, name: string): boolean => config.required_fields.includes(name)

/** Что ещё надо заполнить, в винительном падеже: «Заполните фамилию, имя, пол». */
export function missingFields(config: RegistrationConfig, form: RegistrationForm): string[] {
  const missing: string[] = []
  if (!form.last_name.trim()) missing.push('фамилию')
  if (!form.first_name.trim()) missing.push('имя')
  if (hasField(config, 'gender') && !form.gender) missing.push('пол')
  if (config.groups.length && form.group_index < 0) missing.push('группу')
  if (config.sets.length && form.set_index < 0) missing.push('сет')
  const accusative: Record<TextField, string> = {
    birth_year: 'год рождения', city: 'город', team: 'команду', email: 'email', phone_number: 'телефон',
  }
  for (const { name } of TEXT_FIELDS) {
    if (hasField(config, name) && isRequired(config, name) && !form[name].trim()) missing.push(accusative[name])
  }
  return missing
}

/** Поля анкеты, которые отправляем: только те, что попросило событие. */
export function toRegistrationPayload(config: RegistrationConfig, form: RegistrationForm): RegistrationPayload {
  const payload: RegistrationPayload = { last_name: form.last_name.trim(), first_name: form.first_name.trim() }
  if (hasField(config, 'gender') && form.gender) payload.gender = form.gender
  if (config.groups.length) payload.group_index = form.group_index
  if (config.sets.length) payload.set_index = form.set_index
  for (const { name } of TEXT_FIELDS) {
    const value = form[name].trim()
    if (!hasField(config, name) || !value) continue
    payload[name] = name === 'birth_year' && /^\d+$/.test(value) ? Number(value) : value
  }
  if (hasField(config, 'grade') && form.grade) payload.grade = form.grade
  return payload
}

/** Поля, которые можно достать из сохранённого черновика. Всё остальное отбрасываем. */
export function pickForm(raw: Record<string, unknown>): Partial<RegistrationForm> {
  const picked: Partial<RegistrationForm> = {}
  for (const key of ['last_name', 'first_name', 'birth_year', 'city', 'team', 'grade', 'email', 'phone_number'] as const) {
    const value = raw[key]
    if (typeof value === 'string') picked[key] = value
  }
  if (raw.gender === 'MALE' || raw.gender === 'FEMALE' || raw.gender === '') picked.gender = raw.gender
  for (const key of ['group_index', 'set_index'] as const) {
    const value = raw[key]
    if (typeof value === 'number' && Number.isInteger(value)) picked[key] = value
  }
  return picked
}
