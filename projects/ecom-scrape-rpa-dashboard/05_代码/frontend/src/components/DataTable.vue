<script setup lang="ts">
// 通用只读表格：视图传列定义与行数据；单元格一律文本插值，不用 v-html（§8 边界输入）
export interface Column {
  key: string
  label: string
  align?: 'left' | 'right'
  format?: (row: Record<string, unknown>, index: number) => string
  color?: (row: Record<string, unknown>) => string
}

defineProps<{ columns: Column[]; rows: Record<string, unknown>[] }>()
</script>

<template>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th
            v-for="c in columns"
            :key="c.key"
            :style="{ textAlign: c.align ?? 'left' }"
          >{{ c.label }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(r, i) in rows" :key="i">
          <td
            v-for="c in columns"
            :key="c.key"
            :style="{ textAlign: c.align ?? 'left', color: c.color ? c.color(r) : undefined }"
          >{{ c.format ? c.format(r, i) : String(r[c.key] ?? '') }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
