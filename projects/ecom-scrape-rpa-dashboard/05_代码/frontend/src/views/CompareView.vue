<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import CardBase from '../components/CardBase.vue'
import ChartPanel from '../components/ChartPanel.vue'
import StatTile from '../components/StatTile.vue'
import DataTable from '../components/DataTable.vue'
import { fetchCompare, type CompareRow } from '../api'
import { apiState } from '../api/client'
import { useViewData } from '../composables/useViewData'

// T25c：/api/platform-compare?date&category? —— StatTile 三指标 + 柱图 + 表格
const today = new Date().toISOString().slice(0, 10)
const route = useRoute()
// 初始筛选支持 URL query（#/compare?date=..&category=..）
const date = ref(String(route.query.date || today))
const category = ref(String(route.query.category || '')) // 空 = 全部（接口 category 可选）
const filters = computed(() => ({ date: date.value, category: category.value }))

const { state, data, error, reload } = useViewData<CompareRow[]>(
  () => fetchCompare({ date: date.value, category: category.value || undefined }),
  filters,
)

const rows = computed(() => data.value ?? [])

// 三项总览指标：对后端返回行的展示级合计（sku_count / sum_sales 直接求和、均价按 sku 数加权），
// 业务指标口径（均价区间等）仍由后端计算，前端仅格式化
const tiles = computed(() => {
  const rs = rows.value
  const mockNote = apiState.usingMock ? '# MOCK' : undefined
  if (rs.length === 0) return null
  const skuTotal = rs.reduce((a, r) => a + r.sku_count, 0)
  const salesTotal = rs.reduce((a, r) => a + r.sum_sales, 0)
  const avg = rs.reduce((a, r) => a + r.avg_price * r.sku_count, 0) / skuTotal
  return {
    platformCount: { label: '覆盖平台', value: String(rs.length), note: mockNote },
    skuTotal: { label: 'SKU 覆盖合计', value: skuTotal.toLocaleString('zh-CN'), note: mockNote },
    weightedAvg: { label: '加权均价', value: `¥${avg.toFixed(2)}`, note: mockNote },
  }
})

const chartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 48, right: 24, top: 32, bottom: 32 },
  tooltip: { trigger: 'axis' },
  legend: { data: ['平均价', 'SKU 数'] },
  xAxis: { type: 'category', data: rows.value.map((r) => r.platform) },
  yAxis: [
    { type: 'value', axisLabel: { formatter: '¥{value}' } },
    { type: 'value' },
  ],
  series: [
    {
      name: '平均价',
      type: 'bar',
      data: rows.value.map((r) => r.avg_price),
      itemStyle: { color: '#0f766e' },
      barMaxWidth: 48,
    },
    {
      name: 'SKU 数',
      type: 'bar',
      yAxisIndex: 1,
      data: rows.value.map((r) => r.sku_count),
      itemStyle: { color: '#b7bab5' },
      barMaxWidth: 48,
    },
  ],
}))

const columns = [
  { key: 'platform', label: '平台' },
  { key: 'sku_count', label: 'SKU 数', align: 'right' as const, format: (r: CompareRow) => r.sku_count.toLocaleString('zh-CN') },
  { key: 'avg_price', label: '均价', align: 'right' as const, format: (r: CompareRow) => `¥${r.avg_price.toFixed(2)}` },
  { key: 'min_price', label: '最低价', align: 'right' as const, format: (r: CompareRow) => `¥${r.min_price.toFixed(2)}` },
  { key: 'max_price', label: '最高价', align: 'right' as const, format: (r: CompareRow) => `¥${r.max_price.toFixed(2)}` },
  { key: 'sum_sales', label: '销量合计', align: 'right' as const, format: (r: CompareRow) => r.sum_sales.toLocaleString('zh-CN') },
]
</script>

<template>
  <div class="view">
    <div class="filters" role="group" aria-label="对比筛选">
      <label>日期
        <input v-model="date" type="date" :max="today" />
      </label>
      <label>品类
        <select v-model="category">
          <option value="">全部</option>
          <option value="个护清洁">个护清洁（Mock 演示空态）</option>
        </select>
      </label>
    </div>

    <div v-if="tiles" class="stat-row">
      <StatTile primary v-bind="tiles.platformCount" />
      <StatTile v-bind="tiles.skuTotal" />
      <StatTile v-bind="tiles.weightedAvg" />
    </div>

    <CardBase title="平台价格对比" :note="apiState.usingMock ? '# MOCK' : undefined">
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
        <ChartPanel :option="chartOption" height="280px" />
        <DataTable :columns="columns" :rows="rows" />
      </template>
    </CardBase>
  </div>
</template>
