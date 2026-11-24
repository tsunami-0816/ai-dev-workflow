<script setup lang="ts">
// 应用入口：只做全局初始化，不放页面逻辑
import { onLaunch } from '@dcloudio/uni-app'

/** 微信隐私接口的最小类型声明（避免 any；只声明本项目用到的两个方法） */
interface WxPrivacySetting {
  needAuthorization?: boolean
}
interface WxPrivacyApi {
  getPrivacySetting?: (opts: { success: (res: WxPrivacySetting) => void }) => void
  requirePrivacyAuthorize?: (opts: { success: () => void; fail: () => void }) => void
}

onLaunch(() => {
  // 旧版本 token 兼容位：目前只清理过期标记，不动有效登录态
  try {
    const expired = uni.getStorageSync('ub_token_expired')
    if (expired) {
      uni.removeStorageSync('ub_token')
      uni.removeStorageSync('ub_token_expired')
    }
  } catch {
    // storage 不可用时不阻塞启动
  }

  // #ifdef MP-WEIXIN
  // 隐私授权：先查是否已授权；未授权则触发微信隐私弹窗，把结果落到本地标记。
  try {
    const wxApi = (globalThis as { wx?: WxPrivacyApi }).wx
    if (wxApi && typeof wxApi.getPrivacySetting === 'function') {
      wxApi.getPrivacySetting({
        success: (res: WxPrivacySetting) => {
          if (res.needAuthorization === false) {
            uni.setStorageSync('ub_privacy_agreed', '1')
            return
          }
          wxApi.requirePrivacyAuthorize?.({
            success: () => uni.setStorageSync('ub_privacy_agreed', '1'),
            fail: () => uni.setStorageSync('ub_privacy_agreed', '0')
          })
        }
      })
    }
  } catch {
    // 低版本基础库不支持隐私接口时退回“提交前拦截”
  }
  // #endif
})
</script>

<style>
@import './styles/tokens.css';
@import './styles/base.css';

/* #ifdef H5 */
/* uni-app H5 默认 tabBar 文案 10px，低于 11px 可读下限；小程序端 tabBar 字号由微信固定，不在此覆盖 */
.uni-tabbar__label {
  font-size: 12px !important;
  line-height: 1.4 !important;
}

/* ---- 桌面版（H5 ≥900px）：手机版式保持不变，宽屏换成居中的桌面编排 ---- */
@media (min-width: 900px) {
  :root,
  page {
    --gutter: 48px;
    --fs-body: 16px;
    --fs-small: 14px;
    --fs-num: 22px;
    --fs-display: 44px;
    --row-h: 84px;
    --sp-4: 56px;
    --sp-5: 88px;
  }
  body {
    background-color: var(--ub-ground);
  }
  /* 页面容器居中收窄，两侧露出底布，不再被 1440 拉满 */
  .ub-page,
  .lb-page {
    max-width: 1040px;
    margin-left: auto;
    margin-right: auto;
  }
  /* 底部 tabBar 跟内容一起居中，收成 480 的停靠条，避免两个标签在 1040 里被拉散 */
  .uni-tabbar {
    left: 50% !important;
    right: auto !important;
    transform: translateX(-50%);
    width: 100%;
    max-width: 480px;
    border-top: 1px solid var(--ub-line);
  }
}
/* #endif */
</style>
