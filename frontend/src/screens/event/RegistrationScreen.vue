<script setup lang="ts">
// Регистрация: одна анкета из трёх блоков. Какие поля есть и какие обязательны, решает событие.
import { computed, nextTick, ref, watch } from 'vue'
import type { Gender } from '../../api/entry'
import { plural } from '../../domain/format'
import { TEXT_FIELDS } from '../entry/registration'
import { formatMoney } from './usePay'
import type { EventApp } from './useEventApp'

const props = defineProps<{ app: EventApp }>()

const page = computed(() => props.app.page!)
const flow = computed(() => props.app.registration)
const form = computed(() => flow.value.form)
const reg = computed(() => page.value.registration)

const main = ref<HTMLElement | null>(null)

// ошибка сервера показана вверху анкеты: возвращаемся к ней
watch(() => flow.value.formError, async (error) => {
  if (!error) return
  await nextTick()
  main.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
})

const GENDERS: Array<[Gender, string]> = [['MALE', 'Мужчины'], ['FEMALE', 'Женщины']]

const asked = (name: string) => reg.value.fields.includes(name)
const required = (name: string) => reg.value.required_fields.includes(name)
const serverError = (name: string): string => flow.value.fieldErrors[name]?.[0] ?? ''
const invalid = (name: string, empty: boolean): boolean => flow.value.showErrors && (empty || !!serverError(name))

const hasConnection = computed(() => asked('email') || asked('phone_number'))
const hasChoice = computed(() => page.value.groups.length > 0 || page.value.sets.length > 0 || reg.value.reg_types.length > 0)
const price = computed(() => {
  const types = reg.value.reg_types
  const value = types.length && form.value.reg_type_index >= 0
    ? types.find((t) => t.index === form.value.reg_type_index)?.price ?? null
    : page.value.pay.price
  return value ? `${formatMoney(value)} ₽` : ''
})
const hasFee = computed(() => page.value.pay.is_allowed)

const publicFields = computed(() => [
  asked('birth_year') ? 'год рождения' : '', asked('grade') ? 'разряд' : '', asked('city') ? 'город' : '', asked('team') ? 'команда' : '',
].filter(Boolean))

const setRight = (set: { capacity: number; count: number; is_full: boolean }): string => {
  if (set.capacity <= 0) return ''
  if (set.is_full) return 'мест нет'
  const free = set.capacity - set.count
  return `свободно ${free} ${plural(free, 'место', 'места', 'мест')}`
}

const inputValue = (event: Event) => (event.target as HTMLInputElement).value
const textLabel = (name: string): string => TEXT_FIELDS.find((f) => f.name === name)!.label

function findInList(last: string): void {
  props.app.people.search(last)
  props.app.go('people')
}
</script>

<template>
  <div class="re-fill">
    <main ref="main" class="re-main is-narrow">
      <a class="re-back" :href="app.router.href('info')" @click="app.navigate($event, 'info')">← К событию</a>

      <section v-if="!reg.is_open" class="re-banner" role="status">
        <span>Регистрация закрыта или достигнут лимит участников. Хотите участвовать — напишите организатору.</span>
        <a class="re-linkbtn" :href="app.router.href('info')" @click="app.navigate($event, 'info')">К событию</a>
      </section>

      <template v-else>
        <div>
          <h2>Регистрация</h2>
          <p class="re-lead">Проверьте анкету перед отправкой: поправить её или отменить регистрацию потом сможет только организатор.</p>
        </div>

        <div v-if="flow.formError" class="re-banner is-error" role="alert">
          <template v-if="flow.formError.kind === 'duplicate'">
            <span>
              <b>{{ flow.formError.name }}</b> уже есть в списке участников. Если это вы, регистрироваться второй раз не нужно:
              PIN подскажет организатор.
            </span>
            <button type="button" class="re-linkbtn" @click="findInList((flow.formError as { last: string }).last)">Найти в списке</button>
          </template>
          <span v-else-if="flow.formError.kind === 'too_young'">
            Участвовать можно с {{ reg.min_age }} лет: год рождения {{ flow.formError.year }} или раньше.
          </span>
          <span v-else-if="flow.formError.kind === 'set_full'">
            Сет {{ flow.formError.setNumber }} заполнился, пока вы заполняли анкету. Выберите другой.
          </span>
          <span v-else-if="flow.formError.kind === 'closed'">Регистрация закрыта. Если хотите участвовать, напишите организатору.</span>
          <span v-else-if="flow.formError.kind === 'not_needed'">
            Регистрация на это событие не нужна: имя, группу и сет укажите вместе с результатами.
          </span>
          <span v-else>{{ flow.formError.message }}</span>
        </div>

        <section class="re-form">
          <h3>О себе</h3>
          <div class="re-row2">
            <label class="re-fld" :class="{ 'is-invalid': invalid('last_name', !form.last_name.trim()) }">
              <span>Фамилия</span>
              <input
                :value="form.last_name" autocomplete="family-name" autocapitalize="words" maxlength="32"
                @input="flow.setField('last_name', inputValue($event))"
              >
            </label>
            <label class="re-fld" :class="{ 'is-invalid': invalid('first_name', !form.first_name.trim()) }">
              <span>Имя</span>
              <input
                :value="form.first_name" autocomplete="given-name" autocapitalize="words" maxlength="32"
                @input="flow.setField('first_name', inputValue($event))"
              >
            </label>
          </div>

          <div v-if="asked('gender')" class="re-fld" :class="{ 'is-invalid': invalid('gender', !form.gender) }">
            <span id="re-l-gender">Пол</span>
            <div class="re-choice" role="group" aria-labelledby="re-l-gender">
              <button
                v-for="[value, label] in GENDERS" :key="value" type="button" :aria-pressed="form.gender === value"
                @click="flow.setField('gender', value)"
              >{{ label }}</button>
            </div>
          </div>

          <div v-if="asked('birth_year') || asked('grade')" class="re-row2">
            <label
              v-if="asked('birth_year')" class="re-fld"
              :class="{ 'is-invalid': invalid('birth_year', (required('birth_year') && !form.birth_year.trim()) || flow.badBirthYear) }"
            >
              <span>Год рождения<i v-if="!required('birth_year')"> необязательно</i></span>
              <input
                :value="form.birth_year" inputmode="numeric" maxlength="4" placeholder="1996" autocomplete="bday-year"
                @input="flow.setField('birth_year', inputValue($event).replace(/\D/g, '').slice(0, 4))"
              >
              <span v-if="serverError('birth_year')" class="re-err">{{ serverError('birth_year') }}</span>
            </label>
            <label v-if="asked('grade')" class="re-fld">
              <span>Разряд</span>
              <span class="re-selwrap">
                <select :value="form.grade" @change="flow.setField('grade', ($event.target as HTMLSelectElement).value)">
                  <option v-for="grade in reg.grades" :key="grade.value" :value="grade.value">{{ grade.label }}</option>
                </select>
              </span>
            </label>
          </div>

          <div v-if="asked('city') || asked('team')" class="re-row2">
            <template v-for="name in (['city', 'team'] as const)" :key="name">
              <label
                v-if="asked(name)" class="re-fld"
                :class="{ 'is-invalid': invalid(name, required(name) && !form[name].trim()) }"
              >
                <span>{{ textLabel(name) }}<i v-if="!required(name)"> необязательно</i></span>
                <input
                  :value="form[name]" :autocomplete="name === 'city' ? 'address-level2' : 'organization'" autocapitalize="words"
                  @input="flow.setField(name, inputValue($event))"
                >
              </label>
            </template>
          </div>
        </section>

        <section v-if="hasChoice" class="re-form">
          <h3>{{ reg.reg_types.length && !page.groups.length && !page.sets.length ? 'Тип участия' : 'Группа и сет' }}</h3>

          <div v-if="page.groups.length" class="re-fld" :class="{ 'is-invalid': invalid('group_index', form.group_index < 0) }">
            <span id="re-l-group">Группа</span>
            <div class="re-choice" role="group" aria-labelledby="re-l-group">
              <button
                v-for="(name, index) in page.groups" :key="index" type="button" :aria-pressed="form.group_index === index"
                @click="flow.setField('group_index', index)"
              >{{ name }}</button>
            </div>
          </div>

          <div v-if="page.sets.length" class="re-fld" :class="{ 'is-invalid': invalid('set_index', form.set_index < 0) }">
            <span id="re-l-set">Сет</span>
            <div class="re-setpick" role="radiogroup" aria-labelledby="re-l-set">
              <button
                v-for="set in page.sets" :key="set.index" type="button" role="radio" :aria-checked="form.set_index === set.index"
                :disabled="set.is_full" @click="flow.setField('set_index', set.index)"
              >
                <span class="sp-n">Сет {{ set.index + 1 }}</span>
                <span class="sp-t">{{ set.name }}</span>
                <span class="sp-free">{{ setRight(set) }}</span>
              </button>
            </div>
          </div>

          <div v-if="reg.reg_types.length" class="re-fld" :class="{ 'is-invalid': invalid('reg_type_index', form.reg_type_index < 0) }">
            <span id="re-l-type">Тип участия</span>
            <div class="re-choice" role="group" aria-labelledby="re-l-type">
              <button
                v-for="type in reg.reg_types" :key="type.index" type="button" :aria-pressed="form.reg_type_index === type.index"
                @click="flow.setField('reg_type_index', type.index)"
              >{{ type.name }}<template v-if="type.price"> · {{ formatMoney(type.price) }} ₽</template></button>
            </div>
          </div>
        </section>

        <section v-if="hasConnection" class="re-form">
          <h3>Связь</h3>
          <label v-if="asked('email')" class="re-fld" :class="{ 'is-invalid': invalid('email', required('email') && !form.email.trim()) }">
            <span>Email<i v-if="!required('email')"> необязательно</i></span>
            <input
              :value="form.email" type="email" inputmode="email" autocomplete="email" placeholder="name@mail.ru"
              @input="flow.setField('email', inputValue($event))"
            >
            <span v-if="serverError('email')" class="re-err">{{ serverError('email') }}</span>
          </label>
          <p v-if="asked('email') && hasFee" class="re-hint">Пришлём PIN и ссылку на оплату взноса.</p>
          <label v-if="asked('phone_number')" class="re-fld" :class="{ 'is-invalid': invalid('phone_number', required('phone_number') && !form.phone_number.trim()) }">
            <span>Телефон<i v-if="!required('phone_number')"> необязательно</i></span>
            <input
              :value="form.phone_number" type="tel" inputmode="tel" autocomplete="tel" placeholder="+7"
              @input="flow.setField('phone_number', inputValue($event))"
            >
            <span v-if="serverError('phone_number')" class="re-err">{{ serverError('phone_number') }}</span>
          </label>
          <p class="re-hint">
            Email и телефон видит только организатор.<template v-if="publicFields.length">
              В списке участников видны {{ publicFields.join(', ') }}.</template>
          </p>
        </section>
      </template>
    </main>

    <footer v-if="reg.is_open" class="re-action is-narrow">
      <div class="re-act-row">
        <div class="re-sum">
          <span v-if="price" class="re-s"><b>{{ price }}</b></span>
          <span v-if="price" class="re-of">{{ hasFee ? 'оплата после регистрации' : 'взнос' }}</span>
        </div>
        <button type="button" class="re-btn is-primary" :disabled="flow.sending" @click="flow.submit()">
          {{ flow.sending ? 'Регистрирую…' : 'Зарегистрироваться' }}
        </button>
      </div>
    </footer>
  </div>
</template>
