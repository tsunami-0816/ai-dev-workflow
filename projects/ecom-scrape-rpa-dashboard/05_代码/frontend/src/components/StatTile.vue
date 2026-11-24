<script setup lang="ts">
// 单指标块：值由后端计算，前端只做格式化（§4.1 代码规范）
defineProps<{
  label: string
  value: string
  note?: string
  /** 语义色：up=涨红 / down=跌绿（A 股口径，C07）；plain=正文色 */
  tone?: 'up' | 'down' | 'plain'
  /** 主指标放大（用于一行里第一个最重要的指标，避免三等宽卡片味） */
  primary?: boolean
}>()
</script>

<template>
  <div class="stat-tile" :class="[tone ?? 'plain', { primary }]">
    <span class="stat-label">{{ label }}</span>
    <span class="stat-value">{{ value }}</span>
    <span v-if="note" class="stat-note">{{ note }}</span>
  </div>
</template>
