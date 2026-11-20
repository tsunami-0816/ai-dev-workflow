<template>
  <view class="tk-page">
    <view class="tk-mast">
      <view class="ub-rule" />
      <view class="tk-mast-row">
        <text class="ub-num tk-mast-no">No.03</text>
        <text class="tk-mast-words">票根 · 档期</text>
      </view>
    </view>

    <view v-if="loading" class="tk-skeleton">
      <view class="tk-sk-hero" />
      <view v-for="n in 4" :key="n" class="tk-sk-ticket" />
    </view>

    <view v-else-if="errorMsg" class="tk-state">
      <text class="tk-state-text">{{ errorMsg }}</text>
      <button class="tk-btn" @tap="$emit('retry')">重新加载</button>
    </view>

    <template v-else-if="hero">
      <!-- 第一张：整幅票根，上下联可撕 -->
      <view class="tk-hero" @tap="$emit('open', hero)">
        <view class="tk-hero-top">
          <text class="ub-num tk-hero-no">No.01</text>
          <text class="tk-hero-label">主推档期 · 30 天内可约</text>
        </view>
        <text class="ub-title tk-hero-title">{{ hero.title }}</text>
        <text class="tk-hero-tags">{{ tagsOf(hero) }}</text>
        <view class="tk-hero-row">
          <text class="ub-num tk-hero-price">{{ priceText(hero.price) }}</text>
          <text class="tk-hero-seat">余档 {{ list.length }} 个套餐</text>
        </view>
        <view class="tk-perf" />
        <view class="tk-hero-foot">
          <text class="tk-hero-fine">凭此联到店确认档期</text>
          <text class="tk-hero-tear">撕下预约 →</text>
        </view>
      </view>

      <view class="tk-head">
        <text class="tk-head-title">余下票根</text>
        <text class="ub-num tk-head-count">{{ rest.length }} 张</text>
      </view>
      <view class="ub-rule" />

      <!-- 余下票根：左侧编号存根 + 纵向齿线，逐张错位叠放 -->
      <view class="tk-stack">
        <view
          v-for="(p, i) in rest"
          :key="p.id"
          class="tk-ticket"
          :style="{ marginLeft: offset(i) }"
          @tap="$emit('open', p)"
        >
          <view class="tk-stub">
            <text class="ub-num tk-stub-no">{{ pad(i + 2) }}</text>
            <text class="tk-stub-label">档</text>
          </view>
          <view class="tk-body">
            <view class="tk-body-line">
              <text class="tk-title">{{ p.title }}</text>
              <text class="ub-num tk-price">{{ priceText(p.price) }}</text>
            </view>
            <view class="tk-body-foot">
              <text class="tk-tags">{{ tagsOf(p) }}</text>
              <view v-if="i === 1" class="tk-stamp"><view class="tk-dot" /><text class="tk-stamp-text">剩 2 档</text></view>
              <text v-else class="tk-open">撕下 →</text>
            </view>
          </view>
        </view>
      </view>

      <view class="ub-rule tk-foot-rule" />
      <text class="ub-small tk-foot-note">一个小档期 · 一张票根换一个周末</text>
    </template>

    <view v-else class="tk-state">
      <text class="tk-state-text">这几天还没有档期</text>
      <text class="ub-small">下拉刷新，或稍后再来</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PackageVO } from '@/api/types'

const props = defineProps<{ list: PackageVO[]; hero: PackageVO | null; loading: boolean; errorMsg: string }>()
defineEmits<{ retry: []; open: [p: PackageVO] }>()

const rest = computed<PackageVO[]>(() => (props.list.length ? props.list.slice(1) : []))

function tagsOf(p: PackageVO): string {
  return p.tags.slice(0, 2).join(' · ') || '周末 · 室内'
}
function priceText(price: number): string {
  return '¥' + Number(price).toFixed(0)
}
function pad(n: number): string {
  return String(n).padStart(2, '0')
}
function offset(i: number): string {
  // 叠放顺序：前四张逐张右移 8px，之后保持，形成一叠不齐边的票根
  return Math.min(i, 3) * 8 + 'px'
}
</script>

<style scoped>
.tk-page {
  min-height: 100vh;
  padding: 0 var(--gutter) 96px;
  background-color: var(--ub-ground);
}

.tk-mast { padding-top: var(--sp-3); }
.tk-mast-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--sp-2) 0 var(--sp-1);
}
.tk-mast-no { color: var(--ub-silver); font-size: var(--fs-small); letter-spacing: 0.08em; }
.tk-mast-words { font-size: var(--fs-small); color: var(--ub-silver); letter-spacing: 0.08em; }

/* 第一张票根：整幅，上下两联 */
.tk-hero {
  margin-top: var(--sp-3);
  border: 1px solid var(--ub-line);
  border-radius: 0;
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
}
.tk-hero-top { display: flex; justify-content: space-between; align-items: baseline; }
.tk-hero-no { font-size: var(--fs-small); color: var(--ub-silver); letter-spacing: 0.08em; }
.tk-hero-label { font-size: 11px; color: var(--ub-silver); letter-spacing: 0.08em; }
.tk-hero-title { display: block; margin-top: var(--sp-3); color: var(--ub-paper); }
.tk-hero-tags { display: block; margin-top: var(--sp-1); font-size: var(--fs-body); color: var(--ub-silver); }
.tk-hero-row { display: flex; align-items: baseline; justify-content: space-between; margin-top: var(--sp-3); }
.tk-hero-price { font-size: 22px; color: var(--ub-paper); }
.tk-hero-seat { font-size: var(--fs-small); color: var(--ub-silver); }
.tk-perf { height: 0; margin: var(--sp-3) calc(var(--sp-3) * -1); border-top: 1px dashed var(--ub-line); }
.tk-hero-foot { display: flex; justify-content: space-between; align-items: baseline; }
.tk-hero-fine { font-size: 11px; color: var(--ub-silver); letter-spacing: 0.08em; }
.tk-hero-tear { font-size: var(--fs-small); color: var(--ub-paper); letter-spacing: 0.08em; }

.tk-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: var(--sp-5) 0 var(--sp-1);
}
.tk-head-title { font-family: var(--ub-serif); font-weight: 600; font-size: 20px; color: var(--ub-paper); }
.tk-head-count { font-size: var(--fs-small); color: var(--ub-silver); }

/* 余下票根：无圆角、细边、左侧存根 + 纵向齿线 */
.tk-stack { padding-top: var(--sp-3); }
.tk-ticket {
  display: flex;
  align-items: stretch;
  min-height: 92px;
  margin-bottom: var(--sp-2);
  border: 1px solid var(--ub-line);
  border-radius: 0;
}
.tk-stub {
  width: 56px;
  flex: none;
  border-right: 1px dashed var(--ub-line);
  padding: var(--sp-2) 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
}
.tk-stub-no { font-size: var(--fs-num); color: var(--ub-paper); }
.tk-stub-label { font-size: 11px; color: var(--ub-silver); letter-spacing: 0.08em; }
.tk-body {
  flex: 1;
  min-width: 0;
  padding: var(--sp-2);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.tk-body-line { display: flex; align-items: baseline; justify-content: space-between; }
.tk-title {
  font-family: var(--ub-serif);
  font-weight: 600;
  font-size: 18px;
  color: var(--ub-paper);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: var(--sp-1);
}
.tk-price { font-size: var(--fs-num); color: var(--ub-paper); flex: none; }
.tk-body-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; }
.tk-tags { font-size: var(--fs-small); color: var(--ub-silver); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tk-stamp { display: flex; align-items: center; flex: none; }
.tk-dot { width: 5px; height: 5px; margin-right: 6px; background-color: var(--ub-stamp); }
.tk-stamp-text { font-size: 11px; color: var(--ub-stamp); }
.tk-open { font-family: var(--ub-mono); font-size: var(--fs-small); color: var(--ub-silver); }

.tk-state { padding: var(--sp-5) 0; display: flex; flex-direction: column; align-items: flex-start; }
.tk-state-text { font-family: var(--ub-serif); font-size: 20px; color: var(--ub-paper); margin-bottom: var(--sp-2); }
.tk-btn {
  min-height: var(--tap-min);
  padding: 0 var(--sp-3);
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-btn);
  color: var(--ub-paper);
  font-size: var(--fs-body);
  display: flex;
  align-items: center;
  background-color: transparent;
}

.tk-skeleton { padding-top: var(--sp-3); }
.tk-sk-hero { height: 210px; border: 1px solid var(--ub-line); opacity: 0.45; }
.tk-sk-ticket { height: 92px; margin-top: var(--sp-2); border: 1px solid var(--ub-line); opacity: 0.35; }

.tk-foot-rule { margin-top: var(--sp-5); }
.tk-foot-note { display: block; margin-top: var(--sp-2); }
</style>
