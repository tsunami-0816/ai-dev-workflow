import { createRouter, createWebHashHistory } from 'vue-router'
import TrendView from '../views/TrendView.vue'
import CompareView from '../views/CompareView.vue'
import ChangesView from '../views/ChangesView.vue'
import HealthView from '../views/HealthView.vue'

// 4 页签（T25a）；internal-tool 无登录体系（§5.3），无路由守卫，避免守卫死循环白屏
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/trend' },
    { path: '/trend', name: 'trend', component: TrendView, meta: { title: '价格走势' } },
    { path: '/compare', name: 'compare', component: CompareView, meta: { title: '平台对比' } },
    { path: '/changes', name: 'changes', component: ChangesView, meta: { title: 'TOP 变动' } },
    { path: '/health', name: 'health', component: HealthView, meta: { title: '采集健康度' } },
  ],
})
