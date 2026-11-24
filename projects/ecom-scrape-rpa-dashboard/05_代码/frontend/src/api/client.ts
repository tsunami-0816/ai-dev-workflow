import { reactive } from 'vue'
import axios from 'axios'

/** §5.2 错误码：0 成功；40001 参数；40401 资源不存在；42901 过频；50001 内部；50301 数据服务不可用 */
export class ApiError extends Error {
  code: number
  traceId?: string
  constructor(code: number, message: string, traceId?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.traceId = traceId
  }
}

/** 全局服务状态：503 顶部条（T25f）与 mock 兜底黄条（T32）的数据源 */
export const apiState = reactive({
  /** 50301 / 网络不可达 → 顶部条「数据服务暂不可用」 */
  unavailable: false,
  /** 后端不可用时是否正在用本地 stub 兜底（stub 来源：架构 §5.4 样例 JSON） */
  usingMock: false,
  /** 最近一次真实后端成功时间，显示在 503 条里（§5.2 50301 前端处理） */
  lastOkAt: '' as string,
})

const http = axios.create({ baseURL: '/api', timeout: 8000 })

// 请求去重：同参数 1s 内重复调用复用同一 Promise（§5.5，切筛选器防连点）
const inflight = new Map<string, Promise<unknown>>()

function cacheKey(path: string, params: Record<string, unknown>): string {
  return path + '|' + JSON.stringify(params)
}

export async function apiGet<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const key = cacheKey(path, params)
  const hit = inflight.get(key)
  if (hit) return hit as Promise<T>

  const p = request<T>(path, params)
  inflight.set(key, p)
  setTimeout(() => {
    if (inflight.get(key) === p) inflight.delete(key)
  }, 1000)
  return p
}

async function request<T>(path: string, params: Record<string, unknown>): Promise<T> {
  try {
    const res = await http.get(path, { params })
    const body = res.data
    // 统一响应包（§5.1）：code !== 0 → 抛 ApiError
    if (!body || typeof body.code !== 'number' || body.code !== 0) {
      if (body?.code === 50301) apiState.unavailable = true
      throw new ApiError(body?.code ?? 50001, body?.message ?? '服务异常', body?.trace_id)
    }
    apiState.unavailable = false
    apiState.usingMock = false
    apiState.lastOkAt = new Date().toLocaleTimeString('zh-CN')
    return body.data as T
  } catch (e) {
    if (e instanceof ApiError) throw e
    const err = e as {
      response?: { status: number; data?: { code?: number; message?: string; trace_id?: string } }
    }
    if (err.response) {
      // 后端真实返回了非 2xx：§5.2 约定 body 携带 code/message，按其错误码走视图 error 态
      const status = err.response.status
      const b = err.response.data
      if (typeof b?.code === 'number') {
        if (b.code === 50301 || status === 503) {
          apiState.unavailable = true
          throw new ApiError(50301, b.message ?? '数据服务暂不可用', b.trace_id)
        }
        if (status === 404 && b.code === 40401 && (b.message ?? '').startsWith('Cannot GET')) {
          // 5A 过渡期规则：路由未实现被后端包装为 40401（message 为 FastAPI 默认 Cannot GET 前缀）。
          // 视为接口不可用 → 走本地 stub 兜底；真实的 40401（sku 无快照，§5.4 #1）message 不同、
          // 会正常进入视图 error/empty 态。5A 落地契约后应删除本规则（见实现文档「契约复核」节）。
          apiState.unavailable = true
          throw new ApiError(50301, '接口未实现')
        }
        throw new ApiError(b.code, b.message ?? `HTTP ${status}`, b.trace_id)
      }
      if (status === 404) {
        // 5A 并行开发中：路由未实现（FastAPI 默认 404 body 无 code）→ 视为接口不可用，走 stub 兜底
        apiState.unavailable = true
        throw new ApiError(50301, '接口未实现（404）')
      }
      if (status >= 500) apiState.unavailable = true
      throw new ApiError(50001, (b?.message as string) ?? `HTTP ${status}`)
    }
    // 网络层失败（连接拒绝/超时）→ 与 50301 同语义：数据服务不可用，不白屏
    apiState.unavailable = true
    throw new ApiError(50301, '数据服务暂不可用')
  }
}
