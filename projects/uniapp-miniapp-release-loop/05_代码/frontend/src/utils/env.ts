// 环境与平台判定（T-104 条件编译骨架）
// 说明：真机/开发者工具走小程序通道（云函数 8093），浏览器走 H5 直连 8092。
// 生产切换只需改本文件（或注入构建变量），不改业务代码。

export const API_BASE = 'http://127.0.0.1:8092'
export const PROXY_BASE = 'http://127.0.0.1:8093'
export const OPENID_BASE = 'http://127.0.0.1:8094'
export const API_TIMEOUT = 3000

/**
 * 是否微信小程序端。
 * 用 #ifdef 在编译期裁剪，同时保证 TS 静态解析合法（不写重复声明）。
 */
export function isMpWeixin(): boolean {
  let mp = false
  // #ifdef MP-WEIXIN
  mp = true
  // #endif
  return mp
}

/**
 * 是否 H5 端。
 */
export function isH5(): boolean {
  let h5 = false
  // #ifdef H5
  h5 = true
  // #endif
  return h5
}
