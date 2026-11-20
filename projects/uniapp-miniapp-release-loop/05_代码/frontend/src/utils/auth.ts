// 登录态存取与跳转守卫（防死循环：导航锁 + 当前页判定）

const TOKEN_KEY = 'ub_token'
const USER_KEY = 'ub_user'

export interface SessionUser {
  userId: number
  nickname: string
}

export function getToken(): string {
  try {
    return String(uni.getStorageSync(TOKEN_KEY) || '')
  } catch {
    return ''
  }
}

export function getSessionUser(): SessionUser | null {
  try {
    const raw = uni.getStorageSync(USER_KEY)
    if (!raw) return null
    const obj = raw as SessionUser
    if (typeof obj.userId !== 'number') return null
    return obj
  } catch {
    return null
  }
}

export function saveSession(token: string, user: SessionUser): void {
  try {
    uni.setStorageSync(TOKEN_KEY, token)
    uni.setStorageSync(USER_KEY, user)
  } catch {
    // 存储失败不阻断登录流程，页面会提示重新登录
  }
}

export function clearSession(): void {
  try {
    uni.removeStorageSync(TOKEN_KEY)
    uni.removeStorageSync(USER_KEY)
  } catch {
    // 忽略
  }
}

export function hasToken(): boolean {
  const token = getToken()
  return token.length > 0
}

let navLocking = false

/**
 * 跳登录页（带返回地址）。同一时刻只允许一次跳转，避免 onShow 多次触发造成路由堆叠/死循环。
 */
export function goLogin(redirect?: string): void {
  if (navLocking) return
  const pages = getCurrentPages()
  const current = pages.length ? pages[pages.length - 1].route || '' : ''
  if (current === 'pages/login/index') return
  navLocking = true
  const query = redirect ? '?redirect=' + encodeURIComponent(redirect) : ''
  uni.navigateTo({
    url: '/pages/login/index' + query,
    complete: () => {
      setTimeout(() => {
        navLocking = false
      }, 800)
    }
  })
}
