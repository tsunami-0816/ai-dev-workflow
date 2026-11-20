<template>
  <view class="done">
    <text class="ub-num done-no">No.{{ done.bookingId }}</text>
    <text class="ub-title done-title">这一档记下了</text>
    <text v-if="done.duplicated" class="ub-small done-note">你之前提交过同一笔，单号没有变</text>
    <text v-else class="ub-small done-note">状态：待确认 · 我们会在 24 小时内联系你</text>
    <view class="done-actions">
      <button class="btn-primary" @tap="$emit('my')">看我的档期</button>
      <button class="btn-ghost" @tap="$emit('home')">回册子</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import type { BookingCreateData } from '@/api/types'

defineProps<{ done: BookingCreateData }>()
defineEmits<{ my: []; home: [] }>()
</script>

<style scoped>
.done {
  padding-top: var(--sp-5);
}

.done-no {
  display: block;
  color: var(--ub-stamp);
  font-size: var(--fs-small);
  letter-spacing: 0.08em;
}

.done-title {
  display: block;
  margin-top: var(--sp-2);
}

.done-note {
  display: block;
  margin-top: var(--sp-1);
}

.done-actions {
  margin-top: var(--sp-4);
}

.btn-primary {
  width: 100%;
  height: 48px;
  background-color: var(--ub-paper);
  color: var(--ub-ground);
  border-radius: var(--radius-btn);
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-ghost {
  background-color: transparent;
  width: 100%;
  height: 48px;
  margin-top: var(--sp-2);
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-btn);
  color: var(--ub-paper);
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
