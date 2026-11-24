import { ref, watch, onMounted, type Ref } from 'vue'

/** 三态（T25f）：loading / ready / empty / error */
export type LoadState = 'loading' | 'ready' | 'empty' | 'error'

/**
 * 视图通用数据装载：三态管理 + 筛选器 1s 防抖（§5.5）。
 * watchSource 变化后防抖 1000ms 再拉数（初次挂载立即拉）。
 */
export function useViewData<T>(
  fetcher: () => Promise<T>,
  watchSource: Ref<unknown> | (() => unknown),
  opts: { debounce?: number; isEmpty?: (d: T) => boolean } = {},
) {
  const state = ref<LoadState>('loading')
  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref('')
  const debounceMs = opts.debounce ?? 1000
  let timer: ReturnType<typeof setTimeout> | undefined
  let seq = 0

  async function load() {
    const mySeq = ++seq
    state.value = 'loading'
    try {
      const result = await fetcher()
      if (mySeq !== seq) return // 过期响应丢弃（防抖期间又发起新请求）
      data.value = result
      const empty = Array.isArray(result) ? result.length === 0 : opts.isEmpty ? opts.isEmpty(result) : result == null
      state.value = empty ? 'empty' : 'ready'
    } catch (e) {
      if (mySeq !== seq) return
      error.value = e instanceof Error ? e.message : String(e)
      state.value = 'error'
    }
  }

  function debouncedLoad() {
    clearTimeout(timer)
    timer = setTimeout(load, debounceMs)
  }

  onMounted(load)
  watch(watchSource, debouncedLoad, { deep: true })

  return { state, data, error, reload: load }
}
