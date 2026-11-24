// # MOCK: 本地 stub 数据，仅在后端 5A（8094）不可用时兜底，页面顶部黄条会标注「mock 环境」。
// 数据结构与数值来源：架构文档 §5.4 的 5 个样例 JSON；未拿到 openapi.json（5A 并行开发中），
// 未臆造额外字段——契约待 5A 产出后复核。
import { ApiError } from './client'

const DAY = 86_400_000

/** 今天往前 offset 天的 YYYY-MM-DD（stub 用相对日期，便于演示时贴近当前日期） */
function dateStr(offset: number): string {
  const d = new Date(Date.now() + offset * DAY)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 确定性微扰（无随机数，同一参数每次结果一致） */
function wiggle(i: number, amp: number): number {
  return Math.round(Math.sin(i * 1.7) * amp * 100) / 100
}

// ---------------------------------------------------------------------------
// /api/trend  样例 1（§5.4）：[{date, price, sales_num, anomaly_flag}]
// ---------------------------------------------------------------------------

export interface TrendPoint {
  date: string
  price: number
  sales_num: number
  anomaly_flag: number
}

/** 样例 SKU（含 §5.4 样例 1/3 中的真实样例值；演示 SKU 显式标注 MOCK） */
export const DEMO_SKUS: { id: string; label: string }[] = [
  { id: '100012043978', label: '杰士邦零感超薄10只装 · jd' },
  { id: '6523411', label: '杜蕾斯air空气感3只装 · pdd' },
  { id: 'SKU-EMPTY-DEMO', label: 'SKU-EMPTY-DEMO（MOCK 演示空态）' },
  { id: 'SKU-ERR-DEMO', label: 'SKU-ERR-DEMO（MOCK 演示错误态）' },
]

const TREND_BASE: Record<string, { base: number; anomalyOffset: number; anomalyPrice: number; sales: number }> = {
  '100012043978': { base: 89.9, anomalyOffset: -4, anomalyPrice: 62.93, sales: 13000 }, // 样例 1：89.90 → 62.93 突变
  '6523411': { base: 19.9, anomalyOffset: -2, anomalyPrice: 25.8, sales: 5200 }, // 样例 3：19.90 → 25.80
}

export function trend(params: { sku_id: string; platform: string; days: 7 | 30 }): TrendPoint[] {
  if (params.sku_id === 'SKU-EMPTY-DEMO') return []
  if (params.sku_id === 'SKU-ERR-DEMO') {
    // # MOCK: 演示错误态——模拟后端返回 50001（内部错误），走视图 error 分支
    throw new ApiError(50001, '演示错误态：服务异常（Mock）', '00000000')
  }
  const conf = TREND_BASE[params.sku_id] ?? TREND_BASE['100012043978']
  const points: TrendPoint[] = []
  for (let i = -(params.days - 1); i <= 0; i++) {
    const isAnomaly = i === conf.anomalyOffset
    const price = isAnomaly ? conf.anomalyPrice : Math.max(0.01, conf.base + wiggle(i + 7, 0.4))
    points.push({
      date: dateStr(i),
      price: Math.round(price * 100) / 100,
      sales_num: conf.sales + (i + params.days) * 100,
      anomaly_flag: isAnomaly ? 1 : 0,
    })
  }
  return points
}

// ---------------------------------------------------------------------------
// /api/platform-compare  样例 2（§5.4）
// ---------------------------------------------------------------------------

export interface CompareRow {
  platform: string
  sku_count: number
  avg_price: number
  min_price: number
  max_price: number
  sum_sales: number
}

const COMPARE_SAMPLE: CompareRow[] = [
  { platform: 'jd', sku_count: 120, avg_price: 78.42, min_price: 39.9, max_price: 159.0, sum_sales: 482000 },
  { platform: 'tmall', sku_count: 110, avg_price: 81.15, min_price: 42.0, max_price: 168.0, sum_sales: 395000 },
  { platform: 'pdd', sku_count: 105, avg_price: 65.3, min_price: 29.9, max_price: 129.0, sum_sales: 612000 },
]

export function compare(params: { date: string; category?: string }): CompareRow[] {
  // category 过滤：样例 2 未给品类维度，非空 category 一律返回空（演示空态），不臆造品类数据
  if (params.category) return []
  return COMPARE_SAMPLE.map((r) => ({ ...r }))
}

// ---------------------------------------------------------------------------
// /api/top-changes  样例 3（§5.4）
// ---------------------------------------------------------------------------

export interface ChangeRow {
  sku_id: string
  title: string
  platform: string
  prev_price: number
  curr_price: number
  change_pct: number
}

function pct(prev: number, curr: number): number {
  return Math.round(((curr - prev) / prev) * 10000) / 100
}

const CHANGES_UP: Omit<ChangeRow, 'change_pct'>[] = [
  { sku_id: '100012043978', title: '杰士邦零感超薄10只装', platform: 'jd', prev_price: 62.93, curr_price: 89.9 }, // 样例 3
  { sku_id: '6523411', title: '杜蕾斯air空气感3只装', platform: 'pdd', prev_price: 19.9, curr_price: 25.8 }, // 样例 3
  { sku_id: 'SKU-7732014', title: '洁柔立体压花抽纸24包', platform: 'jd', prev_price: 39.9, curr_price: 49.9 },
  { sku_id: 'SKU-6102957', title: '立白洗衣液12斤装', platform: 'tmall', prev_price: 59.0, curr_price: 71.9 },
  { sku_id: 'SKU-2048836', title: '清风原木金装卷纸30卷', platform: 'pdd', prev_price: 45.0, curr_price: 54.0 },
  { sku_id: 'SKU-8811402', title: '六神驱蚊花露水180ml', platform: 'jd', prev_price: 15.9, curr_price: 18.9 },
  { sku_id: 'SKU-3301275', title: '蓝月亮洗手液500g×3', platform: 'tmall', prev_price: 29.9, curr_price: 35.5 },
  { sku_id: 'SKU-5520918', title: '维达超韧抽纸27包', platform: 'pdd', prev_price: 52.9, curr_price: 62.3 },
  { sku_id: 'SKU-9987233', title: '舒肤佳沐浴露1L', platform: 'jd', prev_price: 49.9, curr_price: 58.4 },
  { sku_id: 'SKU-4118720', title: '霸王防脱洗发水400ml', platform: 'tmall', prev_price: 79.0, curr_price: 92.0 },
  { sku_id: 'SKU-7003941', title: '海飞丝去屑洗发水750ml', platform: 'pdd', prev_price: 64.9, curr_price: 75.6 },
  { sku_id: 'SKU-1290566', title: '欧莱雅男士护肤套装', platform: 'jd', prev_price: 129.0, curr_price: 149.9 },
]

const CHANGES_DOWN: Omit<ChangeRow, 'change_pct'>[] = [
  { sku_id: 'SKU-5177002', title: '高洁丝臻选棉柔卫生巾', platform: 'jd', prev_price: 89.9, curr_price: 69.9 },
  { sku_id: 'SKU-8623318', title: '伊利纯牛奶250ml×24', platform: 'tmall', prev_price: 59.9, curr_price: 49.9 },
  { sku_id: 'SKU-3902755', title: '三全水饺荠菜猪肉1kg', platform: 'pdd', prev_price: 32.9, curr_price: 26.9 },
  { sku_id: 'SKU-7044182', title: '金龙鱼调和油5L', platform: 'jd', prev_price: 72.9, curr_price: 62.9 },
  { sku_id: 'SKU-2255801', title: '清风黑金卷纸24卷', platform: 'tmall', prev_price: 49.9, curr_price: 42.5 },
  { sku_id: 'SKU-6681023', title: '安慕希酸奶12盒', platform: 'pdd', prev_price: 65.0, curr_price: 55.5 },
  { sku_id: 'SKU-1872960', title: '洽洽坚果每日装750g', platform: 'jd', prev_price: 79.0, curr_price: 69.0 },
  { sku_id: 'SKU-9405517', title: '奥利奥夹心饼干家庭装', platform: 'tmall', prev_price: 25.9, curr_price: 21.9 },
  { sku_id: 'SKU-4126683', title: '百草味猪肉脯200g', platform: 'pdd', prev_price: 29.9, curr_price: 24.9 },
  { sku_id: 'SKU-7719348', title: '鲁花花生油5L', platform: 'jd', prev_price: 139.9, curr_price: 119.9 },
  { sku_id: 'SKU-5826474', title: '德芙丝滑牛奶巧克力252g', platform: 'tmall', prev_price: 32.0, curr_price: 27.5 },
  { sku_id: 'SKU-3091825', title: '福临门大米10kg', platform: 'pdd', prev_price: 68.0, curr_price: 58.9 },
]

export function changes(params: { days: number; direction: 'up' | 'down'; limit: number }): ChangeRow[] {
  const src = params.direction === 'up' ? CHANGES_UP : CHANGES_DOWN
  return src.slice(0, params.limit).map((r) => ({ ...r, change_pct: pct(r.prev_price, r.curr_price) }))
}

// ---------------------------------------------------------------------------
// /api/health  样例 4（§5.4）
// ---------------------------------------------------------------------------

export interface HealthSeriesPoint {
  date: string
  platform?: string
  success_rate: number
  blocked_rate: number
  p95_latency_ms: number
}

export interface HealthData {
  success_rate: number
  blocked_rate: number
  p95_latency_ms: number
  req_cnt: number
  series: HealthSeriesPoint[]
}

const HEALTH_BASE: Record<string, { s: number; b: number; p95: number }> = {
  jd: { s: 0.968, b: 0.021, p95: 812 }, // 样例 4 数值
  tmall: { s: 0.951, b: 0.034, p95: 905 },
  pdd: { s: 0.973, b: 0.015, p95: 760 },
  all: { s: 0.964, b: 0.023, p95: 830 },
}

function round3(v: number): number {
  return Math.round(v * 1000) / 1000
}

export function health(params: { days: number; platform?: string }): HealthData {
  const key = params.platform || 'all'
  const conf = HEALTH_BASE[key] ?? HEALTH_BASE['all']
  const series: HealthSeriesPoint[] = []
  for (let i = -(params.days - 1); i <= 0; i++) {
    const pt: HealthSeriesPoint = {
      date: dateStr(i),
      success_rate: round3(conf.s + wiggle(i + 30, 0.004) / 10),
      blocked_rate: round3(conf.b + wiggle(i + 12, 0.003) / 10),
      p95_latency_ms: Math.round(conf.p95 + wiggle(i + 20, 18)),
    }
    // 传 platform 时 series 每项带 platform 字段（§5.4 #4，P1-09 分平台 series）
    if (params.platform) pt.platform = params.platform
    series.push(pt)
  }
  const last = series[series.length - 1]
  return {
    success_rate: last.success_rate,
    blocked_rate: last.blocked_rate,
    p95_latency_ms: last.p95_latency_ms,
    req_cnt: params.platform ? 96 : 336,
    series,
  }
}
