<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import type { EChartsCoreOption } from 'echarts/core'
import CardBase from '../components/CardBase.vue'
import ChartPanel from '../components/ChartPanel.vue'
import { fetchTrend, type TrendPoint } from '../api'
import { DEMO_SKUS } from '../api/stub'
import { apiState } from '../api/client'
import { useViewData } from '../composables/useViewData'

// T25b：/api/trend?sku_id&platform&days=7|30 —— 折线 + 异常点标记（anomaly_flag=1）
const PLATFORMS = ['jd', 'tmall', 'pdd']

// 初始筛选支持 URL query（#/trend?sku_id=..&platform=..&days=..），便于直达与走查
const route = useRoute()
const skuId = ref(String(route.query.sku_id || DEMO_SKUS[0].id))
const platform = ref(String(route.query.platform || 'jd'))
const days = ref<7 | 30>(route.query.days === '30' ? 30 : 7)
const filters = computed(() => ({ skuId: skuId.value, platform: platform.value, days: days.value }))

const { state, data, error, reload } = useViewData<TrendPoint[]>(
  () => fetchTrend({ sku_id: skuId.value, platform: platform.value, days: days.value }),
  filters,
)

const anomalyCount = computed(() => (data.value ?? []).filter((p) => p.anomaly_flag === 1).length)

const chartOption = computed<EChartsCoreOption>(() => {
  const rows = data.value ?? []
  const anomalies = rows.filter((p) => p.anomaly_flag === 1)
  return {
    grid: { left: 56, right: 24, top: 32, bottom: 32 },
    tooltip: {
      trigger: 'axis',
      formatter: (params: { name: string; value: number; dataIndex: number }[]) => {
        const p = params[0]
        const row = rows[p.dataIndex]
        if (!row) return ''
        const flag = row.anomaly_flag === 1 ? ' · 异常(>30%)' : ''
        return `${row.date}<br/>价格 ¥${row.price.toFixed(2)}<br/>销量 ${row.sales_num}${flag}`
      },
    },
    xAxis: { type: 'category', data: rows.map((r) => r.date) },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: '¥{value}' } },
    series: [
      {
        name: '价格',
        type: 'line',
        data: rows.map((r) => r.price),
        symbolSize: 6,
        lineStyle: { width: 2, color: '#0f766e' },
        itemStyle: { color: '#0f766e' },
      },
      {
        // 异常点标记：突变 >30% 的快照（D-45），红点叠在折线上
        name: '异常点',
        type: 'scatter',
        data: anomalies.map((a) => [a.date, a.price]),
        symbolSize: 12,
        itemStyle: { color: '#d93025', borderColor: '#fff', borderWidth: 1 },
      },
    ],
  }
})
</script>

<template>
  <div class="view">
    <div class="filters" role="group" aria-label="走势筛选">
      <label>商品
        <select v-model="skuId">
          <option v-for="s in DEMO_SKUS" :key="s.id" :value="s.id">{{ s.label }}</option>
        </select>
      </label>
      <label>平台
        <select v-model="platform">
          <option v-for="p in PLATFORMS" :key="p" :value="p">{{ p }}</option>
        </select>
      </label>
      <label>时间
        <select v-model.number="days">
          <option :value="7">近 7 日</option>
          <option :value="30">近 30 日</option>
        </select>
      </label>
    </div>

    <CardBase
      :title="`价格走势 · ${skuId}`"
      :note="anomalyCount > 0 ? `异常点 ${anomalyCount} 个（涨幅>30%）` : (apiState.usingMock ? '# MOCK' : undefined)"
    >
      <template #actions>
        <button class="btn" @click="reload">刷新</button>
      </template>
      <div v-if="state === 'loading'" class="state state-loading">加载中…</div>
      <div v-else-if="state === 'empty'" class="state state-empty">当日无数据，请先跑采集</div>
      <div v-else-if="state === 'error'" class="state state-error">
        <span>加载失败：{{ error }}</span>
        <button class="btn" @click="reload">重试</button>
      </div>
      <ChartPanel v-else :option="chartOption" height="340px" />
    </CardBase>
  </div>
</template>
