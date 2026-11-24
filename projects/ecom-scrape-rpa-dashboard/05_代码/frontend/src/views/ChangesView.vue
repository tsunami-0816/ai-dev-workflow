<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import CardBase from '../components/CardBase.vue'
import DataTable from '../components/DataTable.vue'
import { fetchChanges, type ChangeRow } from '../api'
import { apiState } from '../api/client'
import { useViewData } from '../composables/useViewData'

// T25d：/api/top-changes?days=1&direction=up|down&limit=10
// 涨 = 红 #d93025，跌 = 绿 #1a7f37（A 股口径，C07）
const UP = '#d93025'
const DOWN = '#1a7f37'

// 初始筛选支持 URL query（#/changes?direction=down&limit=20）
const route = useRoute()
const direction = ref<'up' | 'down'>(route.query.direction === 'down' ? 'down' : 'up')
const limit = ref(Number(route.query.limit) === 20 ? 20 : 10)
const filters = computed(() => ({ direction: direction.value, limit: limit.value }))

const { state, data, error, reload } = useViewData<ChangeRow[]>(
  () => fetchChanges({ days: 1, direction: direction.value, limit: limit.value }),
  filters,
)

const rows = computed(() => data.value ?? [])

const columns = [
  { key: 'rank', label: '#', align: 'left' as const, format: (_r: Record<string, unknown>, i?: number) => String((i ?? 0) + 1) },
  { key: 'sku_id', label: 'SKU' },
  { key: 'title', label: '商品' },
  { key: 'platform', label: '平台' },
  { key: 'prev_price', label: '前价', align: 'right' as const, format: (r: Record<string, unknown>) => `¥${Number(r.prev_price).toFixed(2)}` },
  { key: 'curr_price', label: '现价', align: 'right' as const, format: (r: Record<string, unknown>) => `¥${Number(r.curr_price).toFixed(2)}` },
  {
    key: 'change_pct',
    label: '涨跌幅',
    align: 'right' as const,
    format: (r: Record<string, unknown>) => `${Number(r.change_pct) > 0 ? '+' : ''}${Number(r.change_pct).toFixed(2)}%`,
    color: (r: Record<string, unknown>) => (Number(r.change_pct) >= 0 ? UP : DOWN),
  },
]

const heading = computed(() => (direction.value === 'up' ? '涨幅 TOP' : '跌幅 TOP'))
const directionColor = computed(() => (direction.value === 'up' ? UP : DOWN))
</script>

<template>
  <div class="view">
    <div class="filters" role="group" aria-label="变动筛选">
      <div class="seg" role="tablist" aria-label="涨跌方向">
        <button
          :class="{ active: direction === 'up' }"
          :style="direction === 'up' ? { color: UP, borderColor: UP } : undefined"
          @click="direction = 'up'"
        >涨幅榜</button>
        <button
          :class="{ active: direction === 'down' }"
          :style="direction === 'down' ? { color: DOWN, borderColor: DOWN } : undefined"
          @click="direction = 'down'"
        >跌幅榜</button>
      </div>
      <label>条数
        <select v-model.number="limit">
          <option :value="10">10</option>
          <option :value="20">20</option>
        </select>
      </label>
      <span class="filter-note">对比跨度 days=1（后端自动前推 1 天取前值，§4.5 Q2）</span>
    </div>

    <CardBase :title="heading" :note="apiState.usingMock ? '# MOCK' : undefined">
      <template #actions>
        <button class="btn" @click="reload">刷新</button>
      </template>
      <div v-if="state === 'loading'" class="state state-loading">加载中…</div>
      <div v-else-if="state === 'empty'" class="state state-empty">当日无数据，请先跑采集</div>
      <div v-else-if="state === 'error'" class="state state-error">
        <span>加载失败：{{ error }}</span>
        <button class="btn" @click="reload">重试</button>
      </div>
      <template v-else>
        <p class="changes-legend">
          <span :style="{ color: directionColor }">{{ direction === 'up' ? '■ 涨' : '■ 跌' }}</span>
          {{ direction === 'up' ? '红 = 上涨（A 股口径）' : '绿 = 下跌（A 股口径）' }}
        </p>
        <DataTable :columns="columns" :rows="rows" />
      </template>
    </CardBase>
  </div>
</template>
