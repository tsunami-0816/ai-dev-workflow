<template>
  <view class="ub-page">
    <view class="mast">
      <view class="ub-rule" />
      <view class="mast-row">
        <text class="ub-num mast-no">No.03</text>
        <text class="mast-words">隐私协议</text>
      </view>
    </view>

    <text class="ub-title title">隐私协议</text>
    <text class="ub-small lead"> demo 占位文本，不构成正式法律文件。正式上线前须替换为运营方审核过的协议。</text>

    <view class="section">
      <text class="section-no ub-num">01</text>
      <text class="section-title">我们收集什么</text>
      <text class="body">登录昵称、手机号；你选择的套餐、预约日期、时段与备注。不收集通讯录、相册、定位等与预约无关的信息。</text>
    </view>

    <view class="section">
      <text class="section-no ub-num">02</text>
      <text class="section-title">用来做什么</text>
      <text class="body">仅用于登录识别、生成预约记录、与你确认档期。不会用于广告推送，也不会卖给第三方。</text>
    </view>

    <view class="section">
      <text class="section-no ub-num">03</text>
      <text class="section-title">保存多久</text>
      <text class="body"> demo 环境保存 30 天；你可以随时联系运营方删除预约记录与账号信息。删除后不可恢复。</text>
    </view>

    <view class="section">
      <text class="section-no ub-num">04</text>
      <text class="section-title">第三方</text>
      <text class="body">微信登录会由微信校验你的身份；除此之外不向任何第三方共享你的预约信息。</text>
    </view>

    <view class="ub-rule foot-rule" />
    <text class="ub-small foot">如果你不同意上述信息的使用方式，请不要提交预约。你仍可以浏览套餐与价格。</text>

    <!-- #ifdef MP-WEIXIN -->
    <button class="btn-primary" open-type="agreePrivacyAuthorization" @agreeprivacyauthorization="agree">
      同意并继续
    </button>
    <button class="btn-ghost" @tap="back">先不同意，返回</button>
    <!-- #endif -->
    <!-- #ifndef MP-WEIXIN -->
    <button class="btn-ghost" @tap="back">返回</button>
    <!-- #endif -->
  </view>
</template>

<script setup lang="ts">
function agree(): void {
  try {
    uni.setStorageSync('ub_privacy_agreed', '1')
  } catch {
    // storage 不可用时不阻塞返回
  }
  back()
}

function back(): void {
  uni.navigateBack({
    fail: () => uni.switchTab({ url: '/pages/index/index' })
  })
}
</script>

<style scoped>
.ub-page {
  min-height: 100vh;
  padding: 0 var(--gutter) 64px;
  background-color: var(--ub-ground);
}
.mast { padding-top: var(--sp-3); }
.mast-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: var(--sp-1) 0;
}
.mast-no, .mast-words { font-size: var(--fs-small); color: var(--ub-silver); }
.title { display: block; margin-top: var(--sp-4); }
.lead { display: block; margin-top: var(--sp-2); color: rgba(242, 237, 228, 0.72); line-height: 1.7; }
.section {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--ub-line);
}
.section-no { color: var(--ub-silver); font-size: 13px; }
.section-title { font-family: var(--ub-serif); font-weight: 600; font-size: 18px; color: var(--ub-paper); line-height: 1.4; }
.body { font-size: 15px; line-height: 1.75; color: rgba(242, 237, 228, 0.82); }
.foot-rule { margin-top: var(--sp-5); }
.foot { display: block; margin: var(--sp-2) 0 var(--sp-4); color: rgba(242, 237, 228, 0.72); line-height: 1.7; }
.btn-primary {
  margin-top: var(--sp-3);
  width: 100%;
  height: 48px;
  border: none;
  border-radius: var(--radius-btn);
  background-color: var(--ub-paper);
  color: var(--ub-ground);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-ghost {
  margin-top: var(--sp-2);
  width: 100%;
  height: 48px;
  background-color: transparent;
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-btn);
  color: var(--ub-paper);
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-primary::after, .btn-ghost::after { border: none; }

/* #ifdef H5 */
/* ---- 桌面版（≥900px）：协议收窄到 720 阅读宽度，正文行宽可控 ---- */
@media (min-width: 900px) {
  .ub-page { max-width: 720px; }
  .title { font-size: 40px; }
  .section-title { font-size: 20px; }
  .body { font-size: 16px; }
  .btn-primary, .btn-ghost { width: 280px; }
}
/* #endif */
</style>
