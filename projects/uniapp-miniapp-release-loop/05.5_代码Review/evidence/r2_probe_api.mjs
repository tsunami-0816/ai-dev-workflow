// 5.5 R2 复审 · reviewer 独立探针（不复用 5A/5B 的探针脚本）
// 覆盖：Q-004 openid 信任链 / Q-011 跨账号幂等 / Q-007 分页 API / 越权与错误码
// 运行：node r2_probe_api.mjs   （后端 8092 需在跑；结果写 r2_probe_api.txt）
import fs from 'node:fs'
import crypto from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const BASE = 'http://127.0.0.1:8092'
const SECRET = 'dev-only-hmac-secret-change-me' // application.yml 默认值（无 .env 时生效）
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), 'r2_probe_api.txt')
const lines = []
const rows = []

function log(line) {
  lines.push(line)
  console.log(line)
}

function sign(body, ts) {
  return crypto.createHmac('sha256', SECRET).update(String(body) + '|' + String(ts)).digest('hex')
}

async function call(label, method, url, { body, token, cloud, cloudNoSign, badSign } = {}) {
  const headers = {}
  const raw = body === undefined ? '' : JSON.stringify(body)
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = 'Bearer ' + token
  if (cloudNoSign) {
    headers['X-Client'] = 'cloud' // 只声明来源，不带任何签名头
  } else if (cloud) {
    const ts = Math.floor(Date.now() / 1000)
    headers['X-Client'] = 'cloud'
    headers['X-Timestamp'] = String(ts)
    headers['X-Nonce'] = crypto.randomBytes(8).toString('hex')
    headers['X-Sign'] = badSign ? 'f'.repeat(64) : sign(raw, ts)
  }
  const res = await fetch(BASE + url, { method, headers, body: body === undefined ? undefined : raw })
  let json = null
  try { json = await res.json() } catch { /* 非 JSON */ }
  const rec = { label, status: res.status, code: json?.code, msg: json?.msg, data: json?.data }
  rows.push(rec)
  log(`${label} | status=${res.status} code=${json?.code} msg=${json?.msg ?? ''}`)
  return rec
}

const expect = (cond, name) => {
  rows.push({ label: 'ASSERT ' + name, ok: !!cond })
  log(`${cond ? 'PASS' : 'FAIL'} | ${name}`)
}

const today = new Date()
const inWindow = new Date(today.getTime() + 5 * 86400000)
const d = `${inWindow.getFullYear()}-${String(inWindow.getMonth() + 1).padStart(2, '0')}-${String(inWindow.getDate()).padStart(2, '0')}`

const r1 = await call('T1 openid 无签名（H5 直连）', 'POST', '/api/auth/login', { body: { openid: 'oR2PROBEfake_openid_001' } })
expect(r1.status === 401 && r1.code === 40102, 'T1 无签名 openid 必须 401/40102（此前可建号）')

const r2 = await call('T2 openid + X-Client:cloud 但无签名头', 'POST', '/api/auth/login', { body: { openid: 'oR2PROBEfake_openid_002' }, cloudNoSign: true })
expect(r2.status === 401 && r2.code === 40102, 'T2 声称 cloud 却无签名 → 40102')

const r3 = await call('T3 openid + 云签名但签名错误', 'POST', '/api/auth/login', { body: { openid: 'oR2PROBEfake_openid_003' }, cloud: true, badSign: true })
expect(r3.status === 401 && r3.code === 40102, 'T3 错签 → 40102')

const r4 = await call('T4 openid + 正确云签名', 'POST', '/api/auth/login', { body: { openid: 'oR2PROBEfake_openid_003' }, cloud: true })
expect(r4.status === 200 && r4.code === 0 && r4.data?.userId > 0, 'T4 验签通过才允许 openid 建号')

const a1 = await call('T5 login demo（账号）', 'POST', '/api/auth/login', { body: { account: 'demo', password: 'welcome1' } })
const a2 = await call('T6 login demo2（账号）', 'POST', '/api/auth/login', { body: { account: 'demo2', password: 'welcome1' } })
expect(a1.code === 0 && a2.code === 0, 'T5/T6 种子账号可登录')

const PHONE = '139' + String(Date.now()).slice(-8) // 每次运行换手机号，避免幂等键撞上一轮
const payload = { packageId: 1, bookDate: d, slot: '晚间', contact: PHONE, remark: 'R2 reviewer probe' }
const b1 = await call('T7 demo 创建预约（新手机号）', 'POST', '/api/bookings', { body: payload, token: a1.data.token })
expect(b1.code === 0 && b1.data?.duplicated === false, 'T7 首次创建成功')

const b2 = await call('T8 demo2 同手机号/同日/同时段', 'POST', '/api/bookings', { body: payload, token: a2.data.token })
expect(b2.code === 40001 && !b2.data, 'T8 跨账号不得拿到他人单（须 40001 且无 data）')

const b3 = await call('T9 demo 重复提交（同账号）', 'POST', '/api/bookings', { body: payload, token: a1.data.token })
expect(b3.code === 0 && b3.data?.duplicated === true && b3.data?.bookingId === b1.data?.bookingId, 'T9 同账号幂等返回首单')

const p2 = await call('T10 packages page=2 size=2', 'GET', '/api/packages?page=2&size=2')
expect(p2.code === 0 && p2.data?.total === 4 && p2.data?.list?.length === 2 && p2.data?.page === 2, 'T10 服务端分页第 2 页确有 2 条')

const m1 = await call('T11 bookings page=1 size=3', 'GET', '/api/bookings?page=1&size=3', { token: a1.data.token })
expect(m1.code === 0 && m1.data?.size === 3 && Array.isArray(m1.data?.list), 'T11 我的列表分页参数生效')

const m2 = await call('T12 demo2 列表不含 demo 的单', 'GET', '/api/bookings', { token: a2.data.token })
const leaked = (m2.data?.list || []).some((x) => x.id === b1.data?.bookingId)
expect(m2.code === 0 && !leaked, 'T12 demo2 列表不含 demo 的预约（越权隔离）')

const n1 = await call('T13 无 token 读我的', 'GET', '/api/bookings')
expect(n1.status === 401, 'T13 无 token → 401')
expect(n1.status !== 500 && n1.code !== 50000, 'T13 不落 50000 兜底')

const fails = rows.filter((r) => r.label.startsWith('ASSERT') && r.ok === false).length
log(`TOTAL_ASSERT=${rows.filter((r) => r.label.startsWith('ASSERT')).length} FAIL=${fails}`)
log(`FIXTURE date=${d} bookingId=${b1.data?.bookingId} openidUserId=${r4.data?.userId}`)
fs.writeFileSync(OUT, lines.join('\n') + '\n', 'utf8')
process.exit(fails === 0 ? 0 : 1)
