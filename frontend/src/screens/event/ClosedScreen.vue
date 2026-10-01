<script setup lang="ts">
// «Ввод» и «Результаты», пока они закрыты: объясняем почему, а не пишем одно «закрыто».
defineProps<{ icon: 'clock' | 'lock'; title: string; lines: string[] }>()
</script>

<template>
  <section class="re-closed">
    <svg v-if="icon === 'clock'" class="re-closed-mark" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="24" r="21" />
      <path d="M24 13v11l7 5" />
    </svg>
    <svg v-else class="re-closed-mark" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="11" y="21" width="26" height="19" rx="4" />
      <path d="M17 21v-5a7 7 0 0 1 14 0v5" />
    </svg>
    <h2>{{ title }}</h2>
    <p v-for="line in lines" :key="line">{{ line }}</p>
  </section>
</template>
