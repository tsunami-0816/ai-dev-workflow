<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import CardBase from '../components/CardBase.vue'
import ChartPanel from '../components/ChartPanel.vue'
import StatTile from '../components/StatTile.vue'
import { fetchHealth, type HealthData } from '../api'
import { apiState } from '../api/client'
import { useViewData } from '../composables/useViewData'

// T25e：/api/health?days=7&platform? —— 成功率/封禁率/P95 三指标 + 7 日曲线
// 三指标均为后端口径（§7.1），前端只格式化
const PLATFORM_OPTIONS = ['', 'jd', 'tmall', 'pdd']
// 初始筛选支持 URL query（#/health?platform=jd）
const route = useRoute()
const platform = ref(String(route.query.platform || ''))
const filters = computed(() => ({ platform: platform.value }))

const { state, data, error, reload } = useViewData<HealthData>(
  () => fetchHealth({ days: 7, platform: platform.value || undefined }),
  filters,
  { isEmpty: (d) => d.series.length === 0 },
)

const series = computed(() => data.value?.series ?? [])

const chartOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 56, right: 56, top: 32, bottom: 32 },
  tooltip: { trigger: 'axis' },
  legend: { data: ['成功率', '封禁率', 'P95 耗时(ms)'] },
  xAxis: { type: 'category', data: series.value.map((s) => s.date) },
  yAxis: [
    { type: 'value', min: 0.8, max: 1, axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` } },
    { type: 'value', axisLabel: { formatter: '{value}ms' } },
  ],
  series: [
    {
      name: '成功率',
      type: 'line',
      data: series.value.map((s) => s.success_rate),
      lineStyle: { width: 2, color: '#0f766e' },
      itemStyle: { color: '#0f766e' },
    },
    {
      name: '封禁率',
      type: 'line',
      data: series.value.map((s) => s.blocked_rate),
      lineStyle: { width: 2, color: '#d93025' },
      itemStyle: { color: '#d93025' },
    },
    {
      name: 'P95 耗时(ms)',
      type: 'line',
      yAxisIndex: 1,
      data: series.value.map((s) => s.p95_latency_ms),
      lineStyle: { width: 2, type: 'dashed', color: '#667079' },
      itemStyle: { color: '#667079' },
    },
  ],
}))

function pctText(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}
function toneFor(rate: number, warn: boolean): 'up' | 'plain' {
  // 成功率 <95% 或封禁率 >10% 走告警红（§7.1 阈值），仅换展示色，不在前端算指标
  return warn && rate >= 0 ? 'up' : 'plain'
}
</script>

<template>
  <div class="view">
    <div class="filters" role="group" aria-label="健康度筛选">
      <label>平台
        <select v-model="platform">
          <option v-for="p in PLATFORM_OPTIONS" :key="p" :value="p">{{ p === '' ? '全部（汇总）' : p }}</option>
        </select>
      </label>
      <span class="filter-note">近 7 日 · 成功率红线 95% · 封禁率红线 10%（§7.1）</span>
    </div>

    <div v-if="data" class="stat-row">
      <StatTile
        primary
        label="采集成功率"
        :value="pctText(data.success_rate)"
        :note="apiState.usingMock ? '# MOCK' : undefined"
        :tone="toneFor(data.success_rate, data.success_rate < 0.95)"
      />
      <StatTile
        label="封禁率"
        :value="pctText(data.blocked_rate)"
        :note="apiState.usingMock ? '# MOCK' : undefined"
        :tone="toneFor(data.blocked_rate, data.blocked_rate > 0.1)"
      />
      <StatTile
        label="P95 耗时"
        :value="`${data.p95_latency_ms} ms`"
        :note="apiState.usingMock ? '# MOCK' : `请求数 ${data.req_cnt}`"
      />
    </div>

    <CardBase title="健康度 7 日曲线" :note="apiState.usingMock ? '# MOCK' : undefined">
      <template #actions>
        <button class="btn" @click="reload">刷新</button>
      </template>
      <div v-if="state === 'loading'" class="state state-loading">加载中…</div>
      <div v-else-if="state === 'empty'" class="state state-empty">当日无数据，请先跑采集</div>
      <div v-else-if="state === 'error'" class="state state-error">
        <span>加载失败：{{ error }}</span>
        <button class="btn" @click="reload">重试</button>
      </div>
      <ChartPanel v-else :option="chartOption" height="320px" />
    </CardBase>
  </div>
</template>
