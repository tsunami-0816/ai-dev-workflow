<template>
  <view class="ub-page">
    <view v-if="loading" class="state">
      <text class="state-text">正在翻册子…</text>
    </view>

    <view v-else-if="errorMsg" class="state">
      <text class="state-text">{{ errorMsg }}</text>
      <button class="btn-ghost" @tap="load">重新加载</button>
    </view>

    <template v-else-if="item">
      <view class="mast">
        <view class="ub-rule" />
        <view class="mast-row">
          <text class="ub-num mast-no">No.{{ pad(item.id) }}</text>
          <text class="mast-words">套餐 · 档期</text>
        </view>
      </view>

      <text class="ub-title title">{{ item.title }}</text>
      <text class="ub-num price">¥{{ Number(item.price).toFixed(0) }}</text>

      <view class="tags">
        <text v-for="t in item.tags" :key="t" class="tag">{{ t }}</text>
      </view>

      <view class="section">
        <text class="section-label ub-small">说明</text>
        <text class="summary" :class="{ clamp: !expanded }">{{ item.summary || '暂无更多说明' }}</text>
        <text v-if="needFold" class="fold" @tap="expanded = !expanded">{{ expanded ? '收起' : '展开' }}</text>
      </view>

      <view class="ub-rule" />

      <view class="photo" />

      <view class="bar ub-safe-bottom">
        <button class="btn-primary" @tap="goBooking">立即预约</button>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { fetchPackageDetail } from '@/api'
import type { PackageVO } from '@/api/types'

const item = ref<PackageVO | null>(null)
const loading = ref(true)
const errorMsg = ref('')
const expanded = ref(false)
let packageId = 0

const needFold = computed(() => (item.value?.summary || '').length > 52)

async function load(): Promise<void> {
  loading.value = true
  errorMsg.value = ''
  const res = await fetchPackageDetail(packageId)
  if (res.code === 0 && res.data) {
    item.value = res.data
  } else {
    errorMsg.value = res.msg || '套餐加载失败'
  }
  loading.value = false
}

onLoad((query) => {
  packageId = Number((query as Record<string, string> | undefined)?.id || 0)
  if (!packageId) {
    loading.value = false
    errorMsg.value = '缺少套餐编号'
    return
  }
  load()
})

function goBooking(): void {
  if (!item.value) return
  uni.navigateTo({
    url:
      '/pages/booking/form?packageId=' + item.value.id +
      '&title=' + encodeURIComponent(item.value.title) +
      '&price=' + item.value.price
  })
}

function pad(n: number): string {
  return String(n).padStart(2, '0')
}
</script>

<style scoped>
.ub-page {
  min-height: 100vh;
  padding: 0 var(--gutter) 112px;
  background-color: var(--ub-ground);
}

.mast {
  padding-top: var(--sp-3);
}

.mast-row {
  display: flex;
  justify-content: space-between;
  padding: var(--sp-2) 0 var(--sp-1);
}

.mast-no,
.mast-words {
  font-size: var(--fs-small);
  color: var(--ub-silver);
  letter-spacing: 0.08em;
}

.title {
  display: block;
  margin-top: var(--sp-3);
}

.price {
  display: block;
  margin-top: var(--sp-2);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  margin-top: var(--sp-2);
}

.tag {
  margin: 0 var(--sp-1) var(--sp-1) 0;
  padding: 2px 6px;
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-tag);
  font-size: var(--fs-small);
  color: var(--ub-silver);
}

.photo {
  /* 单列账本：照片左右出血到页面边缘。
     mp-weixin 对 aspect-ratio 支持不稳定，这里用 padding-bottom 125%（4:5）兜底，
     两条写法结果一致，且 margin 拆成合法简写（Q-006 / D-30）。 */
  position: relative;
  /* 出血宽度 = 视口宽，故高度取 125vw 即 4:5；vw 在 H5 与 mp-weixin 都稳定，
     避免 WXSS 对 calc(百分比 + 长度 × 系数) 的兼容差异。 */
  width: calc(100% + var(--gutter) * 2);
  height: 125vw;
  margin: var(--sp-3) calc(var(--gutter) * -1);
  background-color: var(--ub-photo);
  border-bottom: 1px solid var(--ub-line);
}

.section {
  padding: var(--sp-3) 0;
}

.section-label {
  display: block;
  margin-bottom: var(--sp-1);
  letter-spacing: 0.08em;
}

.summary {
  display: block;
  color: var(--ub-paper);
}

.clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  overflow: hidden;
}

.fold {
  display: inline-block;
  margin-top: var(--sp-1);
  color: var(--ub-silver);
  font-size: var(--fs-small);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  padding: var(--sp-2) var(--gutter);
  background-color: var(--ub-ground);
  border-top: 1px solid var(--ub-line);
}

.btn-primary {
  width: 100%;
  height: 48px;
  background-color: var(--ub-paper);
  color: var(--ub-ground);
  border-radius: var(--radius-btn);
  font-size: var(--fs-body);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.state {
  padding: var(--sp-5) 0;
}

.state-text {
  display: block;
  font-family: var(--ub-serif);
  font-size: 20px;
  margin-bottom: var(--sp-2);
}

.btn-ghost {
  background-color: transparent;
  min-height: var(--tap-min);
  padding: 0 var(--sp-3);
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-btn);
  color: var(--ub-paper);
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
