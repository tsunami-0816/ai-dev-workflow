'use strict';

/**
 * apiProxy 核心：action 白名单 → 组请求 → HMAC 加签 → 3s 超时 → 重试 1 次 → 统一错误码（T-206 / D-16）。
 * 双模式共用本 handler：云开发入口 exports.main，本机 http 入口 localServer.js。
 */

const config = require('./config');
const { ROUTES } = require('./routes');
const { hmacHex, makeNonce, makeTraceId } = require('./signer');
const { requestOnce, classifyError } = require('./httpClient');
const { ok, fail, CODES } = require('./errors');
const { logEvent } = require('./logger');

/**
 * 处理一次代理请求。
 * @param {{action?:string,payload?:object,token?:string}} event 入参：前端透传的 action / payload / token（裸 JWT）
 * @returns {Promise<{code:number,msg:string,data:*,traceId:string,elapsedMs:number}>} 统一响应
 */
async function handle(event) {
  const started = Date.now();
  const traceId = makeTraceId();
  const elapsed = () => Date.now() - started;
  const ev = event && typeof event === 'object' ? event : {};

  const action = typeof ev.action === 'string' ? ev.action : '';
  const payload = ev.payload === undefined ? {} : ev.payload;
  const token = typeof ev.token === 'string' ? ev.token : '';

  const route = ROUTES[action];
  if (!route) {
    logEvent({ action: action || '(empty)', code: CODES.PARAM_INVALID, elapsedMs: elapsed(), attempts: 0, traceId });
    return fail(CODES.PARAM_INVALID, '未知 action: ' + (action || '(空)'), traceId, elapsed());
  }

  const checked = route.validate(payload, token);
  if (!checked.ok) {
    logEvent({ action, code: checked.code, elapsedMs: elapsed(), attempts: 0, traceId });
    return fail(checked.code, checked.msg, traceId, elapsed());
  }

  const url = config.backendBase + checked.value.path;
  const rawBody = checked.value.body ? JSON.stringify(checked.value.body) : '';
  let attempts = 0;
  let lastStatus = 0;

  for (let i = 0; i <= config.retry; i += 1) {
    const ts = Math.floor(Date.now() / 1000);
    const nonce = makeNonce(); // 每次尝试都必须换 nonce，否则后端按重放拒绝（40102）
    const headers = {
      'Content-Type': 'application/json; charset=utf-8',
      Accept: 'application/json',
      'X-Client': 'cloud',
      'X-Timestamp': String(ts),
      'X-Nonce': nonce,
      'X-Sign': hmacHex(rawBody, ts, config.appSecret)
    };
    if (token) headers.Authorization = 'Bearer ' + token;

    attempts = i + 1;
    try {
      const res = await requestOnce({ url, method: route.method, body: rawBody, headers, timeoutMs: config.timeoutMs });
      lastStatus = res.status;
      // 5xx 视为上游抖动，重试 1 次（最后一次不再重试）
      if (res.status >= 500 && i < config.retry) continue;

      let parsed;
      try {
        parsed = JSON.parse(res.body);
      } catch (err) {
        logEvent({ action, code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), attempts, backendStatus: lastStatus, traceId });
        return fail(CODES.SERVICE_ERROR, '后端返回非 JSON 响应', traceId, elapsed());
      }
      if (!parsed || typeof parsed.code !== 'number') {
        logEvent({ action, code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), attempts, backendStatus: lastStatus, traceId });
        return fail(CODES.SERVICE_ERROR, '后端响应缺少 code 字段', traceId, elapsed());
      }

      const out = {
        code: parsed.code,
        msg: parsed.msg || (parsed.code === 0 ? 'ok' : '服务开小差了，请稍后重试'),
        data: parsed.data === undefined ? null : parsed.data,
        traceId,
        elapsedMs: elapsed()
      };
      logEvent({ action, code: out.code, elapsedMs: out.elapsedMs, attempts, backendStatus: lastStatus, traceId });
      return out;
    } catch (err) {
      const kind = classifyError(err);
      if (kind !== 'timeout' && kind !== 'network') {
        logEvent({ action, code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), attempts, traceId });
        return fail(CODES.SERVICE_ERROR, '后端请求失败', traceId, elapsed());
      }
      // timeout / network：继续循环（有剩余重试时）
    }
  }

  const timeoutMsg = '网络不稳定，请重试';
  logEvent({ action, code: CODES.UPSTREAM_TIMEOUT, elapsedMs: elapsed(), attempts, backendStatus: lastStatus, traceId });
  return fail(CODES.UPSTREAM_TIMEOUT, timeoutMsg, traceId, elapsed());
}

module.exports = { handle };
