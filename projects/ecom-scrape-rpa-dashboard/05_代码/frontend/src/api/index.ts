// 视图调用层：先打真实后端（vite proxy → 8094）；50301/网络失败/路由未实现时落到本地 stub 兜底
// （不白屏），并置 apiState.usingMock = true 让顶部黄条标注「mock 环境」（T25f/T32）。
// 其余错误码（40001/40401/50001…）与结构校验失败原样抛给视图走 error 态，不用 mock 掩盖真实错误。
// 契约待 5A 产出 openapi.json 后复核；结构校验按架构 §5.4 样例 JSON 的字段集。
import { apiGet, ApiError, apiState } from './client'
import * as stub from './stub'

export type { TrendPoint, CompareRow, ChangeRow, HealthData, HealthSeriesPoint } from './stub'

async function withMockFallback<T>(real: Promise<T>, mock: () => T): Promise<T> {
  try {
    return await real
  } catch (e) {
    if (e instanceof ApiError && e.code === 50301) {
      // # MOCK: 后端不可用（5A 并行开发中）→ §5.4 样例 stub 兜底
      apiState.usingMock = true
      return mock()
    }
    throw e
  }
}

function ensureArray<T>(v: unknown, endpoint: string): T[] {
  if (!Array.isArray(v)) {
    throw new ApiError(50001, `接口返回结构异常：${endpoint} 应返回数组（契约待 5A 复核）`)
  }
  return v as T[]
}

function ensureHealth(d: unknown): stub.HealthData {
  const h = d as { success_rate?: number; blocked_rate?: number; p95_latency_ms?: number; req_cnt?: number; series?: unknown[] }
  if (!h || !Array.isArray(h.series) || typeof h.success_rate !== 'number') {
    throw new ApiError(50001, '接口返回结构异常：/api/health 应含 success_rate 与 series（契约待 5A 复核）')
  }
  return d as stub.HealthData
}

/** T25b：GET /api/trend?sku_id&platform&days=7|30 */
export function fetchTrend(params: { sku_id: string; platform: string; days: 7 | 30 }): Promise<stub.TrendPoint[]> {
  return withMockFallback(
    apiGet<unknown>('/trend', params).then((d) => ensureArray<stub.TrendPoint>(d, '/api/trend')),
    () => stub.trend(params),
  )
}

/** T25c：GET /api/platform-compare?date&category? */
export function fetchCompare(params: { date: string; category?: string }): Promise<stub.CompareRow[]> {
  return withMockFallback(
    apiGet<unknown>('/platform-compare', params).then((d) => ensureArray<stub.CompareRow>(d, '/api/platform-compare')),
    () => stub.compare(params),
  )
}

/** T25d：GET /api/top-changes?days=1&direction=up|down&limit=10 */
export function fetchChanges(params: { days: number; direction: 'up' | 'down'; limit: number }): Promise<stub.ChangeRow[]> {
  return withMockFallback(
    apiGet<unknown>('/top-changes', params).then((d) => ensureArray<stub.ChangeRow>(d, '/api/top-changes')),
    () => stub.changes(params),
  )
}

/** T25e：GET /api/health?days=7&platform? */
export async function fetchHealth(params: { days: number; platform?: string }): Promise<stub.HealthData> {
  return withMockFallback(
    apiGet<unknown>('/health', params).then((d) => ensureHealth(d)),
    () => stub.health(params),
  )
}
