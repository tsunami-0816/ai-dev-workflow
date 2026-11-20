<template>
  <!-- 批次 2：三版首页共用同一份数据与交互，仅版式不同；v=A/B/C 由 H5 query 指定 -->
  <LedgerVariant
    v-if="variant === 'A'"
    :list="list"
    :hero="hero"
    :loading="loading"
    :error-msg="errorMsg"
    @retry="retry"
    @open="goDetail"
  />
  <ContactSheetVariant
    v-else-if="variant === 'B'"
    :list="list"
    :loading="loading"
    :error-msg="errorMsg"
    @retry="retry"
    @open="goDetail"
  />
  <TicketVariant
    v-else
    :list="list"
    :hero="hero"
    :loading="loading"
    :error-msg="errorMsg"
    @retry="retry"
    @open="goDetail"
  />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad, onPullDownRefresh, onReachBottom } from '@dcloudio/uni-app'
import { fetchPackages } from '@/api'
import type { PackageVO } from '@/api/types'
import LedgerVariant from './variants/LedgerVariant.vue'
import ContactSheetVariant from './variants/ContactSheetVariant.vue'
import TicketVariant from './variants/TicketVariant.vue'

const list = ref<PackageVO[]>([])
const loading = ref(true)
const errorMsg = ref('')
const variant = ref<'A' | 'B' | 'C'>('A')

const PAGE_SIZE = 12
const pageSize = ref(PAGE_SIZE) // 支持 ?size=N 覆盖（分页自测/演示用，默认 12）
const page = ref(1)
const total = ref(0)
const hasMore = ref(false)
const loadingMore = ref(false)

const hero = computed<PackageVO | null>(() => (list.value.length ? list.value[0] : null))

/** 首页列表：第一页覆盖，后续页追加（T-303 验收：滚到底继续加载） */
async function load(reset = true): Promise<void> {
  if (reset) {
    loading.value = true
    page.value = 1
    errorMsg.value = ''
  } else {
    loadingMore.value = true
  }
  const res = await fetchPackages(page.value, pageSize.value)
  if (res.code === 0 && res.data) {
    const fresh = res.data.list
    if (reset) {
      list.value = fresh
    } else {
      const seen = new Set(list.value.map((p) => p.id))
      list.value = list.value.concat(fresh.filter((p) => !seen.has(p.id)))
    }
    total.value = res.data.total
    hasMore.value = list.value.length < res.data.total
  } else if (reset) {
    errorMsg.value = res.msg || '加载失败'
  }
  loading.value = false
  loadingMore.value = false
}

onLoad((options?: Record<string, string>) => {
  const v = String(options?.v || '').toUpperCase()
  if (v === 'B' || v === 'C') variant.value = v
  const s = Number(options?.size)
  if (Number.isInteger(s) && s >= 1 && s <= 50) pageSize.value = s
  load()
})

onPullDownRefresh(() => {
  load().finally(() => uni.stopPullDownRefresh())
})

onReachBottom(() => {
  if (!hasMore.value || loading.value || loadingMore.value) return
  page.value += 1
  load(false)
})

function retry(): void {
  load()
}

function goDetail(p: PackageVO): void {
  uni.navigateTo({ url: '/pages/package/detail?id=' + p.id })
}
</script>
