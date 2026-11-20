// 统一请求层（D-09 / T-207）：H5 直连 8092；小程序走云函数 8093。
// 规则：3s 超时、网络失败重试 1 次、业务错误不重试、错误码由页面决定如何展示。

import { API_BASE, PROXY_BASE, API_TIMEOUT, isH5 } from './env'
import { getToken, clearSession } from './auth'

export type Action =
  | 'packages'
  | 'packageDetail'
  | 'login'
  | 'logout'
  | 'createBooking'
  | 'myBookings'

export interface ApiResult<T> {
  code: number
  msg: string
  data: T | null
  traceId?: string
  elapsedMs?: number
}

interface RawResponse {
  status: number
  data: unknown
}

interface H5Target {
  url: string
  method: 'GET' | 'POST'
  data?: Record<string, unknown>
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function normalize<T>(raw: unknown): ApiResult<T> | null {
  if (!raw || typeof raw !== 'object') return null
  const obj = raw as Record<string, unknown>
  if (typeof obj.code !== 'number') return null
  return {
    code: obj.code,
    msg: typeof obj.msg === 'string' ? obj.msg : '',
    data: (obj.data as T) ?? null,
    traceId: typeof obj.traceId === 'string' ? obj.traceId : undefined,
    elapsedMs: typeof obj.elapsedMs === 'number' ? obj.elapsedMs : undefined
  }
}

function sendRaw(
  url: string,
  method: 'GET' | 'POST',
  data: Record<string, unknown> | undefined,
  token: string
): Promise<RawResponse> {
  return new Promise((resolve, reject) => {
    uni.request({
      url,
      method,
      data: data || {},
      timeout: API_TIMEOUT,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: 'Bearer ' + token } : {})
      },
      success: (res) => resolve({ status: res.statusCode, data: res.data }),
      fail: (err) => reject(err)
    })
  })
}

function h5Target(action: Action, payload: Record<string, unknown>): H5Target {
  switch (action) {
    case 'packages':
      return {
        url: API_BASE + '/api/packages',
        method: 'GET',
        data: { page: Number(payload.page ?? 1), size: Number(payload.size ?? 10) }
      }
    case 'packageDetail':
      return { url: API_BASE + '/api/packages/' + String(payload.id), method: 'GET' }
    case 'login':
      return { url: API_BASE + '/api/auth/login', method: 'POST', data: payload }
    case 'logout':
      return { url: API_BASE + '/api/auth/logout', method: 'POST', data: {} }
    case 'createBooking':
      return { url: API_BASE + '/api/bookings', method: 'POST', data: payload }
    case 'myBookings':
      return {
        url: API_BASE + '/api/bookings',
        method: 'GET',
        data: { page: Number(payload.page ?? 1), size: Number(payload.size ?? 10) }
      }
    default:
      return { url: API_BASE + '/api/packages', method: 'GET' }
  }
}

async function sendOnce(
  action: Action,
  payload: Record<string, unknown>,
  token: string
): Promise<RawResponse> {
  if (isH5()) {
    const target = h5Target(action, payload)
    return sendRaw(target.url, target.method, target.data, token)
  }
  // 小程序：同源 handler，签名/超时/重试都在云函数侧完成
  return sendRaw(PROXY_BASE + '/', 'POST', { action, payload, token }, '')
}

export interface RequestOptions {
  token?: string
  retry?: number
}

/**
 * 业务请求统一入口。
 * @param action 云函数 action 名（H5 端映射为 REST 路径）
 * @param payload 业务参数
 * @param options token / 重试次数（默认 1）
 */
export async function requestApi<T>(
  action: Action,
  payload: Record<string, unknown> = {},
  options: RequestOptions = {}
): Promise<ApiResult<T>> {
  const token = options.token ?? getToken()
  const retry = options.retry ?? 1

  for (let attempt = 0; attempt <= retry; attempt += 1) {
    try {
      const res = await sendOnce(action, payload, token)
      if (res.status >= 500 && attempt < retry) {
        await sleep(200)
        continue
      }
      const body = normalize<T>(res.data)
      if (body) {
        // 登录态失效：清本地会话，由页面决定是否跳登录（不在此处强制跳转，避免死循环）
        if (body.code === 40103) clearSession()
        return body
      }
      return { code: 50001, msg: '服务开小差了，请稍后重试', data: null }
    } catch (err) {
      if (attempt < retry) {
        await sleep(200)
        continue
      }
    }
  }

  uni.showToast({ title: '网络不稳定，请重试', icon: 'none', duration: 2000 })
  return { code: 50002, msg: '网络不稳定，请重试', data: null }
}
