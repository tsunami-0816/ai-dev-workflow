<template>
  <view class="ub-page">
    <view class="mast">
      <view class="ub-rule" />
      <view class="mast-row">
        <text class="ub-num mast-no">登录</text>
        <text class="mast-words">进来 · 坐</text>
      </view>
    </view>

    <text class="ub-title title">进来坐</text>
    <text class="ub-small sub">登录后，提交的档期会记在「我的」</text>

    <view v-if="h5Mode" class="form">
      <view class="field">
        <text class="label">账号</text>
        <input
          class="control"
          v-model="account"
          maxlength="32"
          placeholder="演示账号 demo"
          placeholder-class="placeholder"
        />
        <text v-if="errors.account" class="err-field">{{ errors.account }}</text>
      </view>

      <view class="field">
        <text class="label">口令</text>
        <input
          class="control"
          v-model="password"
          :password="true"
          maxlength="64"
          placeholder="演示口令 welcome1"
          placeholder-class="placeholder"
        />
        <text v-if="errors.password" class="err-field">{{ errors.password }}</text>
      </view>

      <text v-if="errMsg" class="err">{{ errMsg }}</text>

      <button class="btn-primary" :disabled="busy" @tap="loginPassword">
        {{ busy ? '正在核对口令…' : '登录' }}
      </button>
      <text class="ub-small demo">演示账号 demo / welcome1（仅本地 seed）</text>
    </view>

    <view v-else class="form">
      <button class="btn-primary" :disabled="busy" @tap="loginWeixin">
        {{ busy ? '正在取微信凭证…' : '微信一键登录' }}
      </button>
      <text v-if="errMsg" class="err">{{ errMsg }}</text>
      <text class="ub-small demo">
        小程序登录需服务端配置 MP_APPSECRET；未配置时会明确报错，可先用 H5 演示账号。
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { exchangeOpenid, loginByOpenid, loginByPassword } from '@/api'
import type { LoginData } from '@/api/types'
import { saveSession } from '@/utils/auth'
import { isH5 } from '@/utils/env'

const h5Mode = ref(isH5())
const account = ref('demo')
const password = ref('')
const busy = ref(false)
const errMsg = ref('')
/** 字段级红字（T-208）：账号/口令各自就地提示，服务端错误仍走表单级 errMsg */
const errors = reactive({ account: '', password: '' })
let redirect = ''

onLoad((query) => {
  const r = (query as Record<string, string> | undefined)?.redirect
  redirect = r ? decodeURIComponent(r) : ''
})

function afterLogin(data: LoginData): void {
  saveSession(data.token, {
    userId: data.userId,
    nickname: data.nickname || '客人'
  })
  if (redirect) {
    const path = redirect.startsWith('/') ? redirect : '/' + redirect
    if (path.indexOf('/pages/my/') === 0) {
      uni.switchTab({ url: '/pages/my/index' })
      return
    }
    uni.redirectTo({
      url: path,
      fail: () => uni.switchTab({ url: '/pages/index/index' })
    })
    return
  }
  uni.switchTab({ url: '/pages/my/index' })
}

async function loginPassword(): Promise<void> {
  if (busy.value) return
  errMsg.value = ''
  errors.account = ''
  errors.password = ''
  if (!account.value.trim()) {
    errors.account = '请输入账号'
    return
  }
  if (!password.value) {
    errors.password = '请输入口令'
    return
  }
  busy.value = true
  const res = await loginByPassword(account.value.trim(), password.value)
  busy.value = false
  if (res.code === 0 && res.data) {
    afterLogin(res.data)
    return
  }
  // 40101 凭证错误落到口令字段；其余错误（网络/服务）保留表单级提示
  if (res.code === 40101) {
    errors.password = res.msg || '口令不正确'
    return
  }
  errMsg.value = res.msg || '登录失败'
}

function loginWeixin(): void {
  if (busy.value) return
  errMsg.value = ''
  busy.value = true
  uni.login({
    provider: 'weixin',
    success: (res) => {
      if (!res.code) {
        busy.value = false
        errMsg.value = '没有取到微信登录凭证'
        return
      }
      exchangeOpenid(res.code).then(async (openRes) => {
        if (openRes.code !== 0 || !openRes.data) {
          busy.value = false
          errMsg.value = openRes.msg || '微信登录失败'
          return
        }
        const loginRes = await loginByOpenid(openRes.data.openid)
        busy.value = false
        if (loginRes.code === 0 && loginRes.data) {
          afterLogin(loginRes.data)
        } else {
          errMsg.value = loginRes.msg || '登录失败'
        }
      })
    },
    fail: () => {
      busy.value = false
      errMsg.value = '微信登录调用失败'
    }
  })
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

.title {
  display: block;
  margin-top: var(--sp-4);
}

.sub {
  display: block;
  margin-top: var(--sp-1);
}

.form {
  margin-top: var(--sp-3);
}

.field {
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--ub-line);
}

.label {
  display: block;
  font-size: var(--fs-small);
  color: var(--ub-silver);
  letter-spacing: 0.08em;
  margin-bottom: var(--sp-1);
}

.control {
  background-color: transparent;
  border: none;
  width: 100%;
  height: var(--tap-min);
  font-size: var(--fs-body);
  color: var(--ub-paper);
}

.placeholder {
  color: var(--ub-silver);
}

.err {
  display: block;
  margin-top: var(--sp-2);
  font-size: var(--fs-small);
  color: var(--ub-stamp);
}

.err-field {
  display: block;
  margin-top: 2px;
  font-size: var(--fs-small);
  color: var(--ub-stamp);
}

.btn-primary {
  width: 100%;
  height: 48px;
  margin-top: var(--sp-4);
  background-color: var(--ub-paper);
  color: var(--ub-ground);
  border-radius: var(--radius-btn);
  font-size: var(--fs-body);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.demo {
  display: block;
  margin-top: var(--sp-2);
}

/* #ifdef H5 */
/* ---- 桌面版（≥900px）：登录收窄成 640，按钮不横贯整屏 ---- */
@media (min-width: 900px) {
  .ub-page { max-width: 640px; }
  .title { font-size: 40px; }
  .btn-primary { width: 320px; }
}
/* #endif */
</style>
