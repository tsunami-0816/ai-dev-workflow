<template>
  <view class="ub-page">
    <!-- 成功态：拆到 BookingDone.vue，保持本页文件长度在规范内 -->
    <BookingDone v-if="done" :done="done" @my="goMy" @home="backHome" />

    <template v-else>
      <view class="mast">
        <view class="ub-rule" />
        <view class="mast-row">
          <text class="ub-num mast-no">预约</text>
          <text class="mast-words">填表 · 确认</text>
        </view>
      </view>

      <view class="pkg">
        <text class="pkg-title">{{ packageTitle || '套餐' }}</text>
        <text class="ub-num pkg-price" v-if="price">¥{{ price }}</text>
      </view>

      <view class="ub-rule" />

      <view class="form">
        <view class="field">
          <text class="label">日期</text>
          <picker mode="date" :start="minDate" :end="maxDate" :value="bookDate" @change="onDate">
            <view class="control">
              <text :class="bookDate ? 'value' : 'placeholder'">{{ bookDate || '选择今天起 30 天内' }}</text>
            </view>
          </picker>
          <text v-if="errors.date" class="err">{{ errors.date }}</text>
        </view>

        <view class="field">
          <text class="label">时段</text>
          <view class="slots">
            <view
              v-for="s in slots"
              :key="s"
              class="slot"
              :class="{ active: slot === s }"
              @tap="pickSlot(s)"
            >
              <text>{{ s }}</text>
            </view>
          </view>
          <text v-if="errors.slot" class="err">{{ errors.slot }}</text>
        </view>

        <view class="field">
          <text class="label">联系人</text>
          <input
            class="control input"
            type="number"
            maxlength="11"
            v-model="contact"
            placeholder="11 位手机号"
            placeholder-class="placeholder"
            @input="onContactInput"
          />
          <text v-if="errors.contact" class="err">{{ errors.contact }}</text>
        </view>

        <view class="field">
          <text class="label">备注</text>
          <textarea
            class="control textarea"
            v-model="remark"
            maxlength="255"
            placeholder="想拍什么、几个人（选填）"
            placeholder-class="placeholder"
          />
          <text class="counter ub-small">{{ remark.length }}/255</text>
        </view>
      </view>

      <button class="btn-primary submit" :class="{ busy: submitting }" :disabled="submitting" @tap="submit">
        {{ submitting ? '正在记档…' : '确认这一档' }}
      </button>
      <text class="ub-small tip">提交即表示同意隐私协议占位条款（演示用）</text>
    </template>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { createBooking } from '@/api'
import type { BookingCreateData } from '@/api/types'
import { hasToken, goLogin } from '@/utils/auth'
import BookingDone from '@/components/BookingDone.vue'

const slots = ['上午', '下午', '晚间']

const packageId = ref(0)
const packageTitle = ref('')
const price = ref('')

const bookDate = ref('')
const slot = ref('')
const contact = ref('')
const remark = ref('')

const errors = reactive({ date: '', slot: '', contact: '' })
const submitting = ref(false)
const done = ref<BookingCreateData | null>(null)

function fmt(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const now = new Date()
const minDate = fmt(now)
const maxDate = fmt(new Date(now.getTime() + 30 * 86400000))

onLoad((query) => {
  const q = (query || {}) as Record<string, string>
  packageId.value = Number(q.packageId || 0)
  packageTitle.value = q.title ? decodeURIComponent(q.title) : ''
  price.value = q.price || ''
  if (!packageId.value) {
    uni.showToast({ title: '缺少套餐编号', icon: 'none' })
  }
})

function onDate(e: unknown): void {
  const detail = (e as { detail?: { value?: string } }).detail
  bookDate.value = detail?.value || ''
  errors.date = ''
}

function pickSlot(s: string): void {
  slot.value = s
  errors.slot = ''
}

// 用户边改边看：输入变化即撤掉上一次的红字，避免「已经改了还在报错」的错觉
function onContactInput(): void {
  if (errors.contact) errors.contact = ''
}

function validate(): boolean {
  errors.date = ''
  errors.slot = ''
  errors.contact = ''
  if (!bookDate.value) errors.date = '请选择日期'
  if (!slot.value) errors.slot = '请选择时段'
  const phone = contact.value.trim()
  if (phone.length !== 11) errors.contact = '请输入 11 位手机号'
  else if (!/^1[3-9]\d{9}$/.test(phone)) errors.contact = '手机号格式不对，请检查'
  return !errors.date && !errors.slot && !errors.contact
}

function loginRedirect(): string {
  return '/pages/booking/form?packageId=' + packageId.value +
    '&title=' + encodeURIComponent(packageTitle.value) +
    '&price=' + price.value
}

async function submit(): Promise<void> {
  if (submitting.value) return
  if (!packageId.value) {
    uni.showToast({ title: '请从套餐页进入', icon: 'none' })
    return
  }
  if (!validate()) return

  // #ifdef MP-WEIXIN
  // 未同意隐私协议时不落库：只允许浏览，不允许提交个人信息。
  if (uni.getStorageSync('ub_privacy_agreed') !== '1') {
    uni.showModal({
      title: '隐私协议',
      content: '预约需要先同意隐私协议。你可以在协议页查看我们收集与保存哪些信息。',
      confirmText: '查看协议',
      cancelText: '先不约',
      success: (r) => {
        if (r.confirm) uni.navigateTo({ url: '/pages/privacy/index' })
      }
    })
    return
  }
  // #endif

  if (!hasToken()) {
    goLogin(loginRedirect())
    return
  }

  submitting.value = true
  const res = await createBooking({
    packageId: packageId.value,
    bookDate: bookDate.value,
    slot: slot.value,
    contact: contact.value,
    remark: remark.value.trim() || undefined
  })
  submitting.value = false

  if (res.code === 0 && res.data) {
    done.value = res.data
    return
  }
  if (res.code === 40101 || res.code === 40103) {
    goLogin(loginRedirect())
    return
  }
  if (res.code === 40002) {
    errors.date = '只能预约今天起 30 天内的档期'
    return
  }
  if (res.code === 40001) {
    const msg = res.msg || '参数不合法'
    if (msg.includes('contact')) errors.contact = msg.replace('contact ', '')
    else if (msg.includes('bookDate')) errors.date = msg.replace('bookDate ', '')
    else if (msg.includes('slot')) errors.slot = msg.replace('slot ', '')
    else if (msg.includes('packageId')) uni.showToast({ title: '套餐无效，请重新选择', icon: 'none' })
    else uni.showToast({ title: msg, icon: 'none' })
    return
  }
  uni.showToast({ title: res.msg || '提交失败', icon: 'none' })
}

function goMy(): void {
  uni.switchTab({ url: '/pages/my/index' })
}

function backHome(): void {
  uni.switchTab({ url: '/pages/index/index' })
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

.pkg {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: var(--sp-3) 0;
}

.pkg-title {
  font-family: var(--ub-serif);
  font-weight: 600;
  font-size: 20px;
  color: var(--ub-paper);
}

.pkg-price {
  font-size: var(--fs-num);
  color: var(--ub-paper);
}

.form {
  padding-top: var(--sp-1);
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
  margin-bottom: var(--sp-2);
}

.control {
  background-color: transparent;
  border: none;
  width: 100%;
  min-height: var(--tap-min);
  display: flex;
  align-items: center;
  font-size: var(--fs-body);
  color: var(--ub-paper);
}

.input {
  height: var(--tap-min);
}

.textarea {
  background-color: transparent;
  border: none;
  height: 88px;
  line-height: 1.6;
}

.value {
  color: var(--ub-paper);
}

.placeholder {
  color: var(--ub-silver);
}

.slots {
  display: flex;
}

.slot {
  min-width: 88px;
  min-height: var(--tap-min);
  margin-right: var(--sp-1);
  border: 1px solid var(--ub-line);
  border-radius: var(--radius-tag);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ub-silver);
  font-size: var(--fs-body);
}

.slot.active {
  border-color: var(--ub-paper);
  color: var(--ub-paper);
}

.err {
  display: block;
  margin-top: var(--sp-1);
  font-size: var(--fs-small);
  color: var(--ub-stamp);
}

.counter {
  display: block;
  text-align: right;
  margin-top: var(--sp-1);
}

.submit {
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

.submit.busy {
  opacity: 0.6;
}

.tip {
  display: block;
  margin-top: var(--sp-2);
  text-align: center;
}

.btn-primary {
  width: 100%;
  height: 48px;
  background-color: var(--ub-paper);
  color: var(--ub-ground);
  border-radius: var(--radius-btn);
  display: flex;
  align-items: center;
  justify-content: center;
}

/* #ifdef H5 */
/* ---- 桌面版（≥900px）：表单收窄成阅读宽度，按钮不再横贯整屏 ---- */
@media (min-width: 900px) {
  .ub-page { max-width: 680px; }
  .submit { width: 320px; }
  .tip { text-align: left; }
}
/* #endif */
</style>
