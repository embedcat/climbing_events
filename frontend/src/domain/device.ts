// Раскладка меняется с 760 px: на компьютере те же экраны, но шире. От неё зависят и подписи: вместо
// «на телефоне» на компьютере пишем «в этом браузере».
import { computed, ref } from 'vue'

export const DESKTOP_QUERY = '(min-width: 760px)'

const query = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  ? window.matchMedia(DESKTOP_QUERY) : null

/** Окно шире 760 px. В тестах без matchMedia — телефон. */
export const isDesktop = ref(query?.matches ?? false)
query?.addEventListener('change', (e) => { isDesktop.value = e.matches })

/** «на телефоне» / «в этом браузере»: куда сохранён черновик и запомнен участник. */
export const onDevice = computed(() => (isDesktop.value ? 'в этом браузере' : 'на этом телефоне'))
export const onPhone = computed(() => (isDesktop.value ? 'в этом браузере' : 'на телефоне'))
