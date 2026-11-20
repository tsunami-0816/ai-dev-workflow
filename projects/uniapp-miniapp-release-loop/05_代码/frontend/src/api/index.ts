// 业务 API（页面只调这里，不直接拼 URL）

import { requestApi, type ApiResult } from '@/utils/request'
import { OPENID_BASE, isH5 } from '@/utils/env'
import type {
  BookingCreateData,
  BookingInput,
  BookingPage,
  LoginData,
  OpenidData,
  PackagePage,
  PackageVO
} from './types'

/** 相同分页参数的并发请求合并：uni H5 首次进 tab 页会挂载两次，避免同一页拉两次 */
const packagesInflight = new Map<string, Promise<ApiResult<PackagePage>>>()

export function fetchPackages(page = 1, size = 10): Promise<ApiResult<PackagePage>> {
  const key = page + '|' + size
  const hit = packagesInflight.get(key)
  if (hit) return hit
  const req = requestApi<PackagePage>('packages', { page, size }).finally(() => {
    packagesInflight.delete(key)
  })
  packagesInflight.set(key, req)
  return req
}

export function fetchPackageDetail(id: number): Promise<ApiResult<PackageVO>> {
  return requestApi<PackageVO>('packageDetail', { id })
}

export function loginByPassword(account: string, password: string): Promise<ApiResult<LoginData>> {
  return requestApi<LoginData>('login', { account, password }, { retry: 0 })
}

export function loginByOpenid(openid: string, nickname?: string): Promise<ApiResult<LoginData>> {
  const payload: Record<string, unknown> = { openid }
  if (nickname) payload.nickname = nickname
  return requestApi<LoginData>('login', payload, { retry: 0 })
}

export function logoutApi(): Promise<ApiResult<null>> {
  return requestApi<null>('logout', {}, { retry: 0 })
}

/**
 * 创建预约。写操作不在这层重试：云函数侧已有「重试 1 次 + 后端幂等」，
 * 前端再重试只会放大请求；用户主动再点时由幂等返回同一单号。
 */
export function createBooking(input: BookingInput): Promise<ApiResult<BookingCreateData>> {
  return requestApi<BookingCreateData>(
    'createBooking',
    {
      packageId: input.packageId,
      bookDate: input.bookDate,
      slot: input.slot,
      contact: input.contact,
      ...(input.remark ? { remark: input.remark } : {})
    },
    { retry: 0 }
  )
}

export function fetchMyBookings(page = 1, size = 10): Promise<ApiResult<BookingPage>> {
  return requestApi<BookingPage>('myBookings', { page, size })
}

/**
 * 小程序：wx.login 的 code → openid（本地 http 模式走 8094，缺 AppSecret 会明确报错）。
 */
export function exchangeOpenid(code: string): Promise<ApiResult<OpenidData>> {
  if (isH5()) {
    return Promise.resolve({ code: 40001, msg: 'H5 端不支持微信登录', data: null })
  }
  return new Promise((resolve) => {
    uni.request({
      url: OPENID_BASE + '/',
      method: 'POST',
      data: { code },
      timeout: 3000,
      header: { 'Content-Type': 'application/json' },
      success: (res) => {
        const body = res.data as { code?: number; msg?: string; data?: OpenidData }
        if (typeof body.code === 'number') {
          resolve({
            code: body.code,
            msg: body.msg || '',
            data: body.data ?? null
          })
        } else {
          resolve({ code: 50001, msg: '登录服务返回异常', data: null })
        }
      },
      fail: () => resolve({ code: 50002, msg: '网络不稳定，请重试', data: null })
    })
  })
}
