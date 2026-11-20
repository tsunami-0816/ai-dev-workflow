<template>
  <view class="cs-page">
    <view class="cs-mast">
      <view class="ub-rule" />
      <view class="cs-mast-row">
        <text class="ub-num cs-mast-no">No.02</text>
        <text class="cs-mast-words">接触印样 · 档期</text>
      </view>
    </view>

    <view v-if="loading" class="cs-skeleton">
      <view class="cs-sk-plate" />
      <view class="cs-sk-grid">
        <view v-for="n in 4" :key="n" class="cs-sk-cell" />
      </view>
    </view>

    <view v-else-if="errorMsg" class="cs-state">
      <text class="cs-state-text">{{ errorMsg }}</text>
      <button class="cs-btn" @tap="$emit('retry')">重新加载</button>
    </view>

    <template v-else>
      <!-- 满版印样：整幅色场 + 贴边小字，图占首屏 -->
      <view class="cs-plate">
        <text class="ub-num cs-plate-index">01 / {{ pad(list.length) }}</text>
        <view class="cs-plate-copy">
          <text class="ub-title cs-plate-title">周末，拍一本册子</text>
          <text class="cs-plate-sub">四个套餐 · {{ list.length }} 个档期可约</text>
          <view class="cs-plate-meta">
            <text class="ub-num cs-plate-price">{{ minPriceText }}</text>
            <text class="cs-plate-note">30 天内可约 · 到店确认</text>
          </view>
        </view>
      </view>

      <view class="cs-caption-row">
        <text class="cs-caption">接触印样 · 实拍样片位</text>
        <text class="ub-num cs-caption">4:5</text>
      </view>

      <view class="cs-head">
        <text class="cs-head-title">全部档期</text>
        <text class="ub-num cs-head-count">{{ list.length }} 档</text>
      </view>
      <view class="ub-rule" />

      <view class="cs-grid">
        <view v-for="(p, i) in list" :key="p.id" class="cs-cell" @tap="$emit('open', p)">
          <view class="cs-frame">
            <text class="ub-num cs-frame-no">{{ pad(i + 1) }}</text>
            <view v-if="i === 2" class="cs-stamp"><view class="cs-dot" /><text class="cs-stamp-text">剩 2 档</text></view>
            <text class="cs-frame-note">样片</text>
          </view>
          <view class="cs-cap">
            <view class="cs-cap-line">
              <text class="cs-name">{{ p.title }}</text>
              <text class="ub-num cs-price">{{ priceText(p.price) }}</text>
            </view>
            <text class="cs-tags">{{ tagsOf(p) }}</text>
          </view>
        </view>
      </view>

      <view class="ub-rule cs-foot-rule" />
      <text class="ub-small cs-foot-note">一个小档期 · 十张印样，四个册子</text>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PackageVO } from '@/api/types'

const props = defineProps<{ list: PackageVO[]; loading: boolean; errorMsg: string }>()
defineEmits<{ retry: []; open: [p: PackageVO] }>()

const minPriceText = computed<string>(() => {
  if (!props.list.length) return '¥399'
  return '¥' + Math.min(...props.list.map((p) => Number(p.price))).toFixed(0) + ' 起'
})

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
.cs-page {
  min-height: 100vh;
  padding: 0 var(--gutter) 96px;
  background-color: var(--ub-ground);
}

.cs-mast { padding-top: var(--sp-3); }
.cs-mast-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--sp-2) 0 var(--sp-1);
}
.cs-mast-no { color: var(--ub-silver); font-size: var(--fs-small); letter-spacing: 0.08em; }
.cs-mast-words { font-size: var(--fs-small); color: var(--ub-silver); letter-spacing: 0.08em; }

/* 首屏：满版色场，文字贴底边 */
.cs-plate {
  position: relative;
  height: 360px;
  margin: 0 calc(var(--gutter) * -1);
  padding: var(--sp-3);
  background-color: var(--ub-photo);
  border-top: 1px solid var(--ub-line);
  border-bottom: 1px solid var(--ub-line);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.cs-plate-index { font-size: var(--fs-small); color: var(--ub-silver); letter-spacing: 0.08em; }
.cs-plate-copy { display: flex; flex-direction: column; align-items: flex-start; }
.cs-plate-title { color: var(--ub-paper); }
.cs-plate-sub { margin-top: var(--sp-1); font-size: var(--fs-body); color: var(--ub-silver); }
.cs-plate-meta {
  display: flex;
  align-items: baseline;
  margin-top: var(--sp-3);
  width: 100%;
}
.cs-plate-price { color: var(--ub-paper); font-size: 22px; }
.cs-plate-note { margin-left: var(--sp-2); font-size: var(--fs-small); color: var(--ub-silver); }

.cs-caption-row {
  display: flex;
  justify-content: space-between;
  padding: var(--sp-1) 0 var(--sp-4);
}
.cs-caption { font-size: 11px; color: var(--ub-silver); letter-spacing: 0.08em; font-family: var(--ub-mono); }

.cs-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: var(--sp-3) 0 var(--sp-1);
}
.cs-head-title { font-family: var(--ub-serif); font-weight: 600; font-size: 20px; color: var(--ub-paper); }
.cs-head-count { font-size: var(--fs-small); color: var(--ub-silver); }

/* 印样格：两列，图占满格，文字在图下，不套卡片 */
.cs-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  padding-top: var(--sp-3);
}
.cs-cell { width: calc(50% - 4px); margin-bottom: var(--sp-4); }
.cs-frame {
  position: relative;
  height: 190px;
  background-color: var(--ub-photo);
  border: 1px solid var(--ub-line);
  padding: 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.cs-frame-no { font-size: 11px; color: var(--ub-silver); }
.cs-frame-note {
  font-family: var(--ub-mono);
  font-size: 11px;
  color: var(--ub-silver);
  letter-spacing: 0.08em;
  align-self: flex-end;
}
.cs-stamp { display: flex; align-items: center; }
.cs-dot { width: 5px; height: 5px; margin-right: 6px; background-color: var(--ub-stamp); }
.cs-stamp-text { font-size: 11px; color: var(--ub-stamp); }

.cs-cap {
  padding-top: var(--sp-1);
  padding-bottom: 6px;
  border-bottom: 1px solid var(--ub-line);
}
.cs-cap-line { display: flex; align-items: baseline; justify-content: space-between; }
.cs-name {
  font-family: var(--ub-serif);
  font-weight: 600;
  font-size: 14px;
  color: var(--ub-paper);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 8px;
}
.cs-price { font-size: 14px; color: var(--ub-paper); flex: none; }
.cs-tags { display: block; margin-top: 4px; font-size: 12px; color: var(--ub-silver); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.cs-state { padding: var(--sp-5) 0; display: flex; flex-direction: column; align-items: flex-start; }
.cs-state-text { font-family: var(--ub-serif); font-size: 20px; color: var(--ub-paper); margin-bottom: var(--sp-2); }
.cs-btn {
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

.cs-skeleton { padding-top: var(--sp-3); }
.cs-sk-plate { height: 360px; margin: 0 calc(var(--gutter) * -1); background-color: var(--ub-photo); opacity: 0.5; }
.cs-sk-grid { display: flex; flex-wrap: wrap; justify-content: space-between; padding-top: var(--sp-3); }
.cs-sk-cell { width: calc(50% - 4px); height: 230px; margin-bottom: var(--sp-4); background-color: var(--ub-photo); opacity: 0.35; }

.cs-foot-rule { margin-top: var(--sp-2); }
.cs-foot-note { display: block; margin-top: var(--sp-2); }
</style>
