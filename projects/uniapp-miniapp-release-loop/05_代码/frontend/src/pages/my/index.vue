<template>
  <view class="ub-page">
    <view class="mast">
      <view class="ub-rule" />
      <view class="mast-row">
        <text class="ub-num mast-no">No.02</text>
        <text class="mast-words">我的 · 档期</text>
      </view>
    </view>

    <!-- 未登录：只给入口，不自动跳转，避免 tab 页与登录页互相弹 -->
    <view v-if="!loggedIn" class="state">
      <text class="ub-title">还没有登录</text>
      <text class="ub-small state-sub">登录后，你约过的档期会记在这里</text>
      <button class="btn-primary" @tap="openLogin">去登录</button>
    </view>

    <template v-else>
      <view class="me">
        <text class="me-name">{{ user ? user.nickname : '客人' }}</text>
        <text class="logout" @tap="logout">退出</text>
      </view>
      <view class="ub-rule" />

      <view v-if="loading" class="state">
        <text class="ub-small">正在翻你的册子…</text>
      </view>

      <view v-else-if="errorMsg" class="state">
        <text class="state-text">{{ errorMsg }}</text>
        <button class="btn-ghost" @tap="reload">重新加载</button>
      </view>

      <view v-else-if="list.length" class="list">
        <view v-for="b in list" :key="b.id" class="booking">
          <view class="b-top">
            <text class="ub-num b-no">No.{{ b.id }}</text>
            <text class="b-status" :class="statusClass(b.status)">{{ b.statusText }}</text>
          </view>
          <text class="b-title">{{ b.packageTitle }}</text>
          <view class="b-meta">
            <text class="ub-num">{{ b.bookDate }}</text>
            <text class="b-sep">·</text>
            <text class="ub-num">{{ b.slot }}</text>
            <text class="b-sep">·</text>
            <text class="ub-num">{{ b.contactMasked }}</text>
          </view>
        </view>
      </view>

      <view v-else class="state">
        <text class="state-text">还没有约过档期</text>
        <text class="ub-small state-sub">回册子挑一本，记下你的那一档</text>
        <button class="btn-primary" @tap="goHome">去看档期</button>
      </view>
    </template>

    <view class="legal">
      <text class="legal-link" @tap="openPrivacy">隐私协议</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom, onShow } from '@dcloudio/uni-app'
import { fetchMyBookings, logoutApi } from '@/api'
import type { BookingItem } from '@/api/types'
import { clearSession, getSessionUser, hasToken, type SessionUser } from '@/utils/auth'

const loggedIn = ref(false)
const user = ref<SessionUser | null>(null)
const list = ref<BookingItem[]>([])
const loading = ref(false)
const errorMsg = ref('')

const PAGE_SIZE = 20
const page = ref(1)
const total = ref(0)
const hasMore = ref(false)
const loadingMore = ref(false)

/** 我的档期：第一页覆盖，后续页追加（预约数 > 20 时滚到底继续加载） */
async function load(reset = true): Promise<void> {
  if (!hasToken()) return
  if (reset) {
    loading.value = true
    page.value = 1
    errorMsg.value = ''
  } else {
    loadingMore.value = true
  }
  const res = await fetchMyBookings(page.value, PAGE_SIZE)
  if (res.code === 0 && res.data) {
    const fresh = res.data.list
    if (reset) {
      list.value = fresh
    } else {
      const seen = new Set(list.value.map((b) => b.id))
      list.value = list.value.concat(fresh.filter((b) => !seen.has(b.id)))
    }
    total.value = res.data.total
    hasMore.value = list.value.length < res.data.total
  } else if (res.code === 40101 || res.code === 40103) {
    clearSession()
    loggedIn.value = false
    user.value = null
    errorMsg.value = ''
  } else if (reset) {
    errorMsg.value = res.msg || '加载失败'
  }
  loading.value = false
  loadingMore.value = false
}

function sync(): void {
  loggedIn.value = hasToken()
  user.value = getSessionUser()
  if (loggedIn.value) load()
}

onLoad(() => {
  sync()
})

onShow(() => {
  sync()
})

onPullDownRefresh(() => {
  if (!hasToken()) {
    uni.stopPullDownRefresh()
    return
  }
  load().finally(() => uni.stopPullDownRefresh())
})

onReachBottom(() => {
  if (!hasToken() || !hasMore.value || loading.value || loadingMore.value) return
  page.value += 1
  load(false)
})

function reload(): void {
  load()
}

function openLogin(): void {
  uni.navigateTo({ url: '/pages/login/index' })
}

async function logout(): Promise<void> {
  await logoutApi()
  clearSession()
  loggedIn.value = false
  user.value = null
  list.value = []
  uni.showToast({ title: '已退出', icon: 'none' })
}

function goHome(): void {
  uni.switchTab({ url: '/pages/index/index' })
}

function openPrivacy(): void {
  uni.navigateTo({ url: '/pages/privacy/index' })
}

function statusClass(status: number): string {
  if (status === 0) return 'wait'
  if (status === 1) return 'ok'
  return 'done'
}
</script>

<style scoped>
.ub-page {
  min-height: 100vh;
  padding: 0 var(--gutter) 64px;
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

.me {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--sp-3) 0;
}

.me-name {
  font-family: var(--ub-serif);
  font-weight: 600;
  font-size: 22px;
  color: var(--ub-paper);
}

.logout {
  font-size: var(--fs-small);
  color: var(--ub-silver);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.legal {
  padding: var(--sp-5) 0 var(--sp-4);
  border-top: 1px solid var(--ub-line);
  margin-top: var(--sp-5);
}
.legal-link {
  font-size: var(--fs-small);
  color: var(--ub-silver);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.list {
  padding-top: var(--sp-1);
}

.booking {
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--ub-line);
}

.b-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.b-no {
  font-size: var(--fs-small);
  color: var(--ub-silver);
}

.b-status {
  font-size: var(--fs-small);
}

.b-status.wait {
  color: var(--ub-stamp);
}

.b-status.ok {
  color: var(--ub-paper);
}

.b-status.done {
  color: var(--ub-silver);
}

.b-title {
  display: block;
  margin-top: var(--sp-1);
  font-family: var(--ub-serif);
  font-weight: 600;
  font-size: 17px;
  color: var(--ub-paper);
}

.b-meta {
  display: flex;
  align-items: center;
  margin-top: 2px;
}

.b-meta .ub-num {
  font-size: var(--fs-small);
  color: var(--ub-silver);
}

.b-sep {
  margin: 0 6px;
  color: var(--ub-silver);
  font-size: var(--fs-small);
}

.state {
  padding: var(--sp-5) 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.state-text {
  font-family: var(--ub-serif);
  font-size: 20px;
  color: var(--ub-paper);
  margin-bottom: var(--sp-1);
}

.state-sub {
  margin-bottom: var(--sp-3);
}

.btn-primary {
  width: 100%;
  max-width: 240px;
  height: 48px;
  background-color: var(--ub-paper);
  color: var(--ub-ground);
  border-radius: var(--radius-btn);
  display: flex;
  align-items: center;
  justify-content: center;
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
