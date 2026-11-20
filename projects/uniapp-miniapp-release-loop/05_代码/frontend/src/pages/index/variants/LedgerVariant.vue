<template>
  <view class="lb-page">
    <view class="mast">
      <view class="ub-rule" />
      <view class="mast-row">
        <text class="ub-num mast-no">No.01</text>
        <text class="mast-words">约拍档期</text>
      </view>
    </view>

    <view v-if="loading" class="skeleton">
      <view v-for="n in 4" :key="n" class="sk-row"><view class="sk-line" /></view>
    </view>

    <view v-else-if="errorMsg" class="state">
      <text class="state-text">{{ errorMsg }}</text>
      <button class="btn-ghost" @tap="$emit('retry')">重新加载</button>
    </view>

    <template v-else-if="hero">
      <view class="hero">
        <view class="hero-copy">
          <text class="ub-title hero-title">{{ hero.title }}</text>
          <text class="hero-sub">{{ tagsOf(hero) }}</text>
          <text class="ub-num hero-price">{{ priceText(hero.price) }}</text>
          <text class="ub-small hero-note">{{ list.length }} 个套餐，30 天内可约</text>
        </view>
        <view class="hero-photo">
          <view class="photo-inner" />
          <text class="photo-no">01 / {{ pad(list.length) }}</text>
        </view>
      </view>

      <view class="ub-rule hero-rule" />

      <view class="list" v-if="shown.length">
        <view v-for="(p, i) in shown" :key="p.id" class="row" @tap="onOpen(p)">
          <text class="ub-num row-no">{{ pad(i + 2) }}</text>
          <view class="row-main">
            <view class="row-line">
              <text class="row-title">{{ p.title }}</text>
              <text class="ub-num row-price">{{ rowPriceText(p) }}</text>
            </view>
            <view class="row-sub">
              <text class="ub-small row-tags">{{ tagsOf(p) }}</text>
              <view v-if="i === 1" class="stamp">
                <view class="stamp-bar" />
                <text class="stamp-text">剩 2 档</text>
              </view>
            </view>
          </view>
        </view>
      </view>

      <view class="ub-rule foot-rule" />
      <text class="ub-small foot-note">一个小档期。只做四本册子</text>
    </template>

    <view v-else class="state">
      <text class="state-text">这几天还没有档期</text>
      <text class="ub-small">下拉刷新，或稍后再来</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PackageVO } from '@/api/types'

const props = defineProps<{ list: PackageVO[]; hero: PackageVO | null; loading: boolean; errorMsg: string }>()
const emit = defineEmits<{ retry: []; open: [p: PackageVO] }>()

/** 首屏 hero 已经展示第 1 个套餐，清单从第 2 个起，避免同一档期在一屏里出现两次 */
const shown = computed<PackageVO[]>(() => props.list.slice(1))

/** 方向稿 §2.5-②：点清单行时价格 300ms 等宽数字跳动；递减动效偏好下直接跳转 */
const TICK_MS = 300
const tickingId = ref<number | null>(null)
const tickValue = ref(0)
const reduceMotion = ((): boolean => {
  try {
    const w = typeof window !== 'undefined' ? window : null
    return !!w && typeof w.matchMedia === 'function' && w.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
})()

function onOpen(p: PackageVO): void {
  if (reduceMotion || tickingId.value !== null) {
    emit('open', p)
    return
  }
  const target = Number(p.price) || 0
  const start = Date.now()
  tickingId.value = p.id
  tickValue.value = 0
  const timer = setInterval(() => {
    const t = Math.min(1, (Date.now() - start) / TICK_MS)
    tickValue.value = Math.round(target * t)
    if (t >= 1) {
      clearInterval(timer)
      tickingId.value = null
      emit('open', p)
    }
  }, 16)
}

function rowPriceText(p: PackageVO): string {
  return tickingId.value === p.id ? '¥' + tickValue.value : priceText(p.price)
}

function tagsOf(p: PackageVO): string {
  return p.tags.slice(0, 2).join(' · ') || '周末 · 室内'
}
function priceText(price: number): string {
  return '¥' + Number(price).toFixed(0)
}
function pad(n: number): string {
  return String(n).padStart(2, '0')
}
</script>

<style scoped>
.lb-page {
  min-height: 100vh;
  padding: 0 var(--gutter) 96px;
  background-color: var(--ub-ground);
}
.mast { padding-top: var(--sp-3); }
/* 方向稿 §2.5-①：进入时细线从左到右「曝光」铺开 */
.mast .ub-rule {
  transform-origin: left center;
  animation: lb-expose 480ms cubic-bezier(0.2, 0.7, 0.3, 1) both;
}
@keyframes lb-expose {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}
@media (prefers-reduced-motion: reduce) {
  .mast .ub-rule { animation: none; transform: none; }
}
.mast-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--sp-2) 0 var(--sp-1);
}
.mast-no { color: var(--ub-silver); font-size: var(--fs-small); letter-spacing: 0.08em; }
.mast-words { font-size: var(--fs-small); color: var(--ub-silver); letter-spacing: 0.08em; }

.hero { display: flex; align-items: flex-start; padding: var(--sp-3) 0 var(--sp-4); }
.hero-copy { flex: 1; min-width: 0; padding-right: var(--sp-2); }
.hero-title { display: block; color: var(--ub-paper); }
.hero-sub { display: block; margin-top: var(--sp-1); font-size: var(--fs-body); color: var(--ub-silver); }
.hero-price { display: block; margin-top: var(--sp-3); color: var(--ub-paper); }
.hero-note { display: block; margin-top: var(--sp-1); }
.hero-photo {
  position: relative;
  width: 46%;
  height: 188px;
  margin-right: calc(var(--gutter) * -1);
  background-color: var(--ub-photo);
  border-left: 1px solid var(--ub-line);
}
.photo-inner {
  position: absolute;
  top: 10px;
  right: 10px;
  bottom: 10px;
  left: 10px;
  border: 1px solid rgba(242, 237, 228, 0.18);
}
.photo-no {
  position: absolute;
  top: 12px;
  left: 12px;
  font-family: var(--ub-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
  color: rgba(242, 237, 228, 0.72);
}
.hero-rule { margin: var(--sp-1) 0 0; }

.skeleton { padding: var(--sp-3) 0; }
.sk-row { height: var(--row-h); display: flex; align-items: center; }
.sk-line { width: 100%; height: 1px; background-color: var(--ub-line); animation: lb-breathe 1.4s ease-in-out infinite; }
@keyframes lb-breathe { 0%, 100% { opacity: 0.35; } 50% { opacity: 0.9; } }

.list { padding-top: var(--sp-1); }
.row {
  position: relative;
  display: flex;
  align-items: center;
  min-height: var(--row-h);
  border-bottom: 1px solid var(--ub-line);
}
.row:last-child { border-bottom: none; }
.row-no {
  position: absolute;
  left: -18px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  text-align: left;
  color: var(--ub-silver);
  font-size: 13px;
}
.row-main { flex: 1; min-width: 0; }
.row-line { display: flex; align-items: baseline; justify-content: space-between; }
.row-sub { display: flex; align-items: center; justify-content: space-between; margin-top: 2px; }
.row-title {
  display: block;
  font-family: var(--ub-serif);
  font-weight: 600;
  font-size: 18px;
  line-height: 1.45;
  color: var(--ub-paper);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
  padding-right: var(--sp-2);
}
.row-tags { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.stamp { display: flex; align-items: center; flex: none; }
.stamp-bar { width: 2px; height: 10px; margin-right: 8px; background-color: var(--ub-stamp); }
.stamp-text { font-size: 11px; color: var(--ub-silver); white-space: nowrap; }
.row-price { flex: none; width: 64px; text-align: right; color: rgba(242, 237, 228, 0.82); font-size: var(--fs-num); }

.state { padding: var(--sp-5) 0; display: flex; flex-direction: column; align-items: flex-start; }
.state-text { font-family: var(--ub-serif); font-size: 20px; color: var(--ub-paper); margin-bottom: var(--sp-2); }
.btn-ghost {
  background-color: transparent;
  min-height: var(--tap-min);
  padding: 0 var(--sp-3);
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-btn);
  color: var(--ub-paper);
  font-size: var(--fs-body);
  display: flex;
  align-items: center;
}
.foot-rule { margin-top: var(--sp-5); }
.foot-note { display: block; margin-top: var(--sp-2); }
</style>
