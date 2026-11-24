<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import { apiState } from './api/client'

// T25a：4 页签导航 + 统一布局；T25f：503 顶部条；T32：mock 环境黄条
function retryAll() {
  // 重试最简单可靠的方式：整页刷新（当前路由为 hash 模式，刷新后回到原页签重新拉数）
  window.location.reload()
}
</script>

<template>
  <div class="app-shell">
    <!-- 503 顶部条：数据接口不可用时不白屏（§5.2 50301 前端处理） -->
    <div v-if="apiState.unavailable" class="banner banner-503" role="alert">
      <span>数据接口暂不可用（后端 5A 未就绪或该路由未实现）{{ apiState.lastOkAt ? `，最后更新 ${apiState.lastOkAt}` : '' }}。当前展示本地 stub 数据。</span>
      <button class="btn" @click="retryAll">重试</button>
    </div>
    <!-- T32 mock 环境黄条：不把 mock 数据说成真实采集 -->
    <div v-if="apiState.usingMock" class="banner banner-mock" role="status">
      mock 环境：后端 5A 契约未就绪（路由未实现或不可达），当前数据为架构 §5.4 样例 stub（# MOCK），不代表真实采集结果。
    </div>

    <header class="topbar">
      <div class="topbar-inner">
        <span class="brand">电商价格采集看板</span>
        <nav class="tabs" aria-label="主导航">
          <RouterLink to="/trend">价格走势</RouterLink>
          <RouterLink to="/compare">平台对比</RouterLink>
          <RouterLink to="/changes">TOP 变动</RouterLink>
          <RouterLink to="/health">采集健康度</RouterLink>
        </nav>
      </div>
    </header>

    <main class="content">
      <RouterView />
    </main>

    <footer class="footer">
      <!-- T32 报表页脚文案 -->
      ecom-scrape-rpa-dashboard · 内部工具 · 指标口径由后端计算（与 Excel 报表同源）·
      {{ apiState.usingMock ? '当前为 mock 环境（本地 stub 数据）' : '数据源：后端只读 API' }}
    </footer>
  </div>
</template>
