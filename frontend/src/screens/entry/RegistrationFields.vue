<script setup lang="ts">
import type { Gender } from '../../api/entry'
import type { EntryFlow } from './useEntryFlow'
import { TEXT_FIELDS, type TextField } from './registration'

const props = defineProps<{ flow: EntryFlow }>()

const GENDERS: Array<[Gender, string]> = [['MALE', 'Мужчины'], ['FEMALE', 'Женщины']]

const config = () => props.flow.config!
const asked = (name: string) => config().registration_fields.includes(name)
const required = (name: string) => config().required_fields.includes(name)

/** Поле подсвечивается, если на него пожаловался сервер или оно пустое после попытки отправить. */
const serverError = (name: string): string => props.flow.fieldErrors[name]?.[0] ?? ''
const invalid = (name: string, empty: boolean): boolean => props.flow.showFieldErrors && (empty || !!serverError(name))

const form = () => props.flow.form
const inputValue = (event: Event) => (event.target as HTMLInputElement).value
</script>

<template>
  <section class="re-form" aria-labelledby="re-form-title">
    <h2 id="re-form-title" class="re-h2">Кто вы</h2>
    <p class="re-muted re-small re-tight">
      Уже вводили результаты? Укажите те же фамилию и имя, и результаты обновятся.
    </p>

    <div class="re-row2">
      <label class="re-fld" :class="{ 'is-invalid': invalid('last_name', !form().last_name.trim()) }">
        <span>Фамилия</span>
        <input
          :value="form().last_name" autocomplete="family-name" autocapitalize="words" maxlength="32"
          @input="flow.setField('last_name', inputValue($event))"
        >
      </label>
      <label class="re-fld" :class="{ 'is-invalid': invalid('first_name', !form().first_name.trim()) }">
        <span>Имя</span>
        <input
          :value="form().first_name" autocomplete="given-name" autocapitalize="words" maxlength="32"
          @input="flow.setField('first_name', inputValue($event))"
        >
      </label>
    </div>

    <div v-if="asked('gender')" class="re-fld" :class="{ 'is-invalid': invalid('gender', !form().gender) }">
      <span id="re-l-gender">Пол</span>
      <div class="re-choice" role="group" aria-labelledby="re-l-gender">
        <button
          v-for="[value, label] in GENDERS" :key="value" type="button"
          :aria-pressed="form().gender === value"
          @click="flow.setField('gender', value)"
        >{{ label }}</button>
      </div>
    </div>

    <div v-if="config().groups.length" class="re-fld" :class="{ 'is-invalid': invalid('group_index', form().group_index < 0) }">
      <span id="re-l-group">Группа</span>
      <div class="re-choice" role="group" aria-labelledby="re-l-group">
        <button
          v-for="(name, index) in config().groups" :key="index" type="button"
          :aria-pressed="form().group_index === index"
          @click="flow.setField('group_index', index)"
        >{{ name }}</button>
      </div>
    </div>

    <div v-if="config().sets.length" class="re-fld" :class="{ 'is-invalid': invalid('set_index', form().set_index < 0) }">
      <span id="re-l-set">Сет</span>
      <div class="re-choice" role="group" aria-labelledby="re-l-set">
        <button
          v-for="set in config().sets" :key="set.index" type="button"
          :aria-pressed="form().set_index === set.index"
          @click="flow.setField('set_index', set.index)"
        >{{ set.name }}<template v-if="set.is_full"> · мест нет</template></button>
      </div>
    </div>

    <template v-for="field in TEXT_FIELDS" :key="field.name">
      <label
        v-if="asked(field.name)" class="re-fld"
        :class="{ 'is-invalid': invalid(field.name, required(field.name) && !form()[field.name as TextField].trim()) }"
      >
        <span>{{ field.label }}<template v-if="!required(field.name)"> · необязательно</template></span>
        <input
          :value="form()[field.name as TextField]" :inputmode="(field.inputmode as 'text')" :autocomplete="field.autocomplete"
          @input="flow.setField(field.name, inputValue($event))"
        >
        <span v-if="serverError(field.name)" class="re-err">{{ serverError(field.name) }}</span>
      </label>
    </template>

    <label v-if="asked('grade')" class="re-fld">
      <span>Разряд · необязательно</span>
      <select :value="form().grade" @change="flow.setField('grade', ($event.target as HTMLSelectElement).value)">
        <option value="">Не указан</option>
        <option v-for="grade in config().grades" :key="grade.value" :value="grade.value">{{ grade.label }}</option>
      </select>
    </label>
  </section>
</template>
