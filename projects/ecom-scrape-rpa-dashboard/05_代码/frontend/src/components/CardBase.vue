<script setup lang="ts">
defineProps<{ title: string; note?: string }>()
</script>

<template>
  <section class="card">
    <header class="card-head">
      <h2>{{ title }}</h2>
      <span v-if="note" class="card-note">{{ note }}</span>
      <slot name="actions" />
    </header>
    <div class="card-body">
      <slot />
    </div>
  </section>
</template>
