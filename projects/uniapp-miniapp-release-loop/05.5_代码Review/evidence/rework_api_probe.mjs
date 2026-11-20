// 5.5 返工验收探针（Q-004 openid 信任链 / Q-011 跨账号幂等 / 基本链路）
// 用法：node rework_api_probe.mjs   （需 8092 已启动）
import { createHmac, randomBytes } from 'node:crypto';

const BASE = 'http://127.0.0.1:8092';
const SECRET = process.env.APP_SECRET || 'dev-only-hmac-secret-change-me';
const results = [];

function sign(body, ts) {
  return createHmac('sha256', SECRET).update(body + '|' + ts).digest('hex');
}

async function call(path, { method = 'GET', body = null, token = '', cloud = false } = {}) {
  const raw = body ? JSON.stringify(body) : '';
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  if (cloud) {
    const ts = String(Math.floor(Date.now() / 1000));
    headers['X-Client'] = 'cloud';
    headers['X-Timestamp'] = ts;
    headers['X-Nonce'] = randomBytes(8).toString('hex');
    headers['X-Sign'] = sign(raw, ts);
  }
  const res = await fetch(BASE + path, { method, headers, body: raw || undefined });
  let json = null;
  try { json = await res.json(); } catch { /* 非 JSON */ }
  return { status: res.status, json };
}

function record(name, ok, detail) {
  results.push({ name, ok, detail });
  console.log((ok ? 'PASS' : 'FAIL') + ' | ' + name + ' | ' + detail);
}

(async () => {
  // 1) 基础只读链路
  const pkgs = await call('/api/packages?page=1&size=10');
  record('GET /api/packages', pkgs.status === 200 && pkgs.json.code === 0 && pkgs.json.data.total === 4,
    `status=${pkgs.status} total=${pkgs.json?.data?.total}`);

  const detail = await call('/api/packages/2');
  record('GET /api/packages/2', detail.status === 200 && detail.json.code === 0, `status=${detail.status}`);

  // 2) H5 账号登录（两次，用于跨账号幂等）
  const a = await call('/api/auth/login', { method: 'POST', body: { account: 'demo', password: 'welcome1' } });
  const tokenA = a.json?.data?.token || '';
  record('POST login demo', a.status === 200 && a.json.code === 0 && !!tokenA,
    `status=${a.status} userId=${a.json?.data?.userId}`);

  const b = await call('/api/auth/login', { method: 'POST', body: { account: 'demo2', password: 'welcome1' } });
  const tokenB = b.json?.data?.token || '';
  record('POST login demo2', b.status === 200 && b.json.code === 0 && !!tokenB,
    `status=${b.status} userId=${b.json?.data?.userId}`);

  // 3) 幂等：同账号重复提交 → duplicated=true
  const today = new Date();
  const d = new Date(today.getTime() + 2 * 86400000);
  const bookDate = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const payload = { packageId: 1, bookDate, slot: '下午', contact: '13900003333', remark: 'REWORK-5.5 主账号' };

  const first = await call('/api/bookings', { method: 'POST', body: payload, token: tokenA });
  record('POST booking (demo first)', first.status === 200 && first.json.code === 0 && first.json.data.duplicated === false,
    `status=${first.status} bookingId=${first.json?.data?.bookingId} dup=${first.json?.data?.duplicated}`);

  const again = await call('/api/bookings', { method: 'POST', body: payload, token: tokenA });
  record('POST booking (demo repeat → duplicated)',
    again.status === 200 && again.json.code === 0 && again.json.data.duplicated === true &&
    again.json.data.bookingId === first.json?.data?.bookingId,
    `status=${again.status} bookingId=${again.json?.data?.bookingId} dup=${again.json?.data?.duplicated}`);

  // 4) 跨账号：demo2 用同一手机号/日期/时段 → 必须 40001，且不得拿到他人单号
  const cross = await call('/api/bookings', { method: 'POST', body: payload, token: tokenB });
  record('POST booking (demo2 same contact → 40001, 不返回他人单)',
    cross.status === 400 && cross.json.code === 40001 && !cross.json.data,
    `status=${cross.status} code=${cross.json?.code} msg=${cross.json?.msg}`);

  // 5) Q-004：H5 直连 openid 登录（无签名）→ 40102，不建号
  const fakeOpenid = 'oREWORKFake' + Math.random().toString(36).slice(2, 10);
  const h5Openid = await call('/api/auth/login', { method: 'POST', body: { openid: fakeOpenid } });
  record('POST login openid 无签名 → 40102',
    h5Openid.status === 401 && h5Openid.json.code === 40102,
    `status=${h5Openid.status} code=${h5Openid.json?.code} msg=${h5Openid.json?.msg}`);

  // 6) Q-004 正向：带云函数签名的 openid 登录 → 200 并建号
  const cloudOpenid = await call('/api/auth/login', { method: 'POST', body: { openid: fakeOpenid }, cloud: true });
  record('POST login openid 带云签名 → 200 建号',
    cloudOpenid.status === 200 && cloudOpenid.json.code === 0 && !!cloudOpenid.json.data?.token,
    `status=${cloudOpenid.status} userId=${cloudOpenid.json?.data?.userId}`);

  // 7) 云签名错值 → 40102（签名过滤器仍生效）
  const ts = String(Math.floor(Date.now() / 1000));
  const bad = await fetch(BASE + '/api/packages?page=1&size=1', {
    headers: { 'X-Client': 'cloud', 'X-Timestamp': ts, 'X-Nonce': randomBytes(8).toString('hex'), 'X-Sign': 'deadbeef' }
  });
  const badJson = await bad.json().catch(() => null);
  record('GET packages 云签名错误 → 40102', bad.status === 401 && badJson?.code === 40102,
    `status=${bad.status} code=${badJson?.code}`);

  // 8) 未登录访问我的
  const noToken = await call('/api/bookings');
  record('GET /api/bookings 无 token → 401', noToken.status === 401 && noToken.json.code === 40101,
    `status=${noToken.status} code=${noToken.json?.code}`);

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\nTOTAL=${results.length} FAIL=${failed}`);
  process.exit(failed === 0 ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
