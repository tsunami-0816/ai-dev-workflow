'use strict';

/**
 * getOpenid 云函数（T-206）：code → 微信 code2session → openid。
 * 安全：MP_APPSECRET 只在服务端环境变量；session_key 不返回前端；错误信息不回显含 secret 的 URL。
 */

const config = require('../shared/config');
const { requestWithRetry, classifyError } = require('../shared/httpClient');
const { ok, fail, CODES } = require('../shared/errors');
const { makeTraceId } = require('../shared/signer');
const { logEvent } = require('../shared/logger');

const CODE_RE = /^[A-Za-z0-9_-]{10,128}$/;
const CODE_INVALID_ERRORS = [40029, 40163, 41008]; // 40029 无效 code / 40163 code 已使用 / 41008 缺 code

/**
 * 用 wx.login 的 code 换 openid。
 * @param {{code?:string}} event 入参：小程序 wx.login 返回的 code
 * @returns {Promise<{code:number,msg:string,data:*,traceId:string,elapsedMs:number}>}
 */
async function handle(event) {
  const started = Date.now();
  const traceId = makeTraceId();
  const ev = event && typeof event === 'object' ? event : {};
  const elapsed = () => Date.now() - started;

  if (!config.mpAppId) {
    logEvent({ action: 'getOpenid', code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), traceId });
    return fail(CODES.SERVICE_ERROR, '云开发未配置：缺少 MP_APPID', traceId, elapsed());
  }
  if (!config.mpAppSecret) {
    logEvent({ action: 'getOpenid', code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), traceId });
    return fail(CODES.SERVICE_ERROR, '云开发未配置：缺少 MP_APPSECRET', traceId, elapsed());
  }
  if (typeof ev.code !== 'string' || !CODE_RE.test(ev.code)) {
    logEvent({ action: 'getOpenid', code: CODES.PARAM_INVALID, elapsedMs: elapsed(), traceId });
    return fail(CODES.PARAM_INVALID, 'code 格式不合法', traceId, elapsed());
  }

  const url =
    config.wxApiBase +
    '/sns/jscode2session?appid=' +
    encodeURIComponent(config.mpAppId) +
    '&secret=' +
    encodeURIComponent(config.mpAppSecret) +
    '&js_code=' +
    encodeURIComponent(ev.code) +
    '&grant_type=authorization_code';

  let res;
  try {
    res = await requestWithRetry({ url, method: 'GET', timeoutMs: config.timeoutMs }, config.retry);
  } catch (err) {
    const kind = classifyError(err);
    logEvent({ action: 'getOpenid', code: CODES.UPSTREAM_TIMEOUT, elapsedMs: elapsed(), attempts: err.attempts, kind, traceId });
    if (kind === 'timeout' || kind === 'network') {
      return fail(CODES.UPSTREAM_TIMEOUT, '网络不稳定，请重试', traceId, elapsed());
    }
    return fail(CODES.SERVICE_ERROR, '微信登录服务请求失败', traceId, elapsed());
  }

  let parsed;
  try {
    parsed = JSON.parse(res.body);
  } catch (err) {
    logEvent({ action: 'getOpenid', code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), backendStatus: res.status, traceId });
    return fail(CODES.SERVICE_ERROR, '微信登录服务返回非 JSON 响应', traceId, elapsed());
  }

  if (parsed.errcode) {
    const wxCode = Number(parsed.errcode);
    if (CODE_INVALID_ERRORS.includes(wxCode)) {
      logEvent({ action: 'getOpenid', code: CODES.PARAM_INVALID, elapsedMs: elapsed(), wxCode, traceId });
      return fail(CODES.PARAM_INVALID, '登录凭证无效或已使用，请重新登录', traceId, elapsed());
    }
    logEvent({ action: 'getOpenid', code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), wxCode, traceId });
    return fail(CODES.SERVICE_ERROR, '微信登录服务异常（errcode ' + wxCode + '）', traceId, elapsed());
  }

  if (typeof parsed.openid !== 'string' || parsed.openid.length === 0) {
    logEvent({ action: 'getOpenid', code: CODES.SERVICE_ERROR, elapsedMs: elapsed(), traceId });
    return fail(CODES.SERVICE_ERROR, '微信登录服务未返回 openid', traceId, elapsed());
  }

  const out = ok(
    { openid: parsed.openid, unionid: parsed.unionid || null, isNewSession: Boolean(parsed.session_key) },
    traceId,
    elapsed()
  );
  logEvent({ action: 'getOpenid', code: out.code, elapsedMs: out.elapsedMs, attempts: res.attempts, traceId });
  return out;
}

module.exports = { handle };
