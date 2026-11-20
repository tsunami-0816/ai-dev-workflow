'use strict';

/**
 * 极简 HTTP 客户端（T-206）。只用 Node 内置 http/https，不引第三方包（架构 §10 预设动作 ③）。
 * 能力：超时（socket idle）、响应体上限 2MB、错误分类（timeout / network / other）、按次数重试。
 */

const http = require('node:http');
const https = require('node:https');

const MAX_RESP_BYTES = 2 * 1024 * 1024;

/**
 * 错误 → 可判定类别。
 * @param {Error} err
 * @returns {'timeout'|'network'|'other'}
 */
function classifyError(err) {
  if (!err) return 'other';
  if (err.code === 'CF_TIMEOUT') return 'timeout';
  if (err.code === 'CF_RESP_TOO_LARGE') return 'other';
  // ECONNREFUSED / ENOTFOUND / ECONNRESET / EHOSTUNREACH / ETIMEDOUT / EPIPE 等
  return 'network';
}

/**
 * 单次请求（不含重试）。
 * @param {{url:string,method?:string,body?:string,headers?:object,timeoutMs?:number}} opts
 * @returns {Promise<{status:number,body:string,headers:object}>}
 */
function requestOnce(opts) {
  const { url, method = 'GET', body = '', headers = {}, timeoutMs = 3000 } = opts;

  return new Promise((resolve, reject) => {
    let target;
    try {
      target = new URL(url);
    } catch (err) {
      const e = new Error('后端地址不合法');
      e.code = 'CF_BAD_URL';
      reject(e);
      return;
    }

    const lib = target.protocol === 'https:' ? https : http;
    const payload = body ? Buffer.from(body, 'utf8') : null;
    const reqHeaders = Object.assign({}, headers);
    if (payload) reqHeaders['Content-Length'] = String(payload.length);

    const req = lib.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || (target.protocol === 'https:' ? 443 : 80),
        path: target.pathname + (target.search || ''),
        method,
        headers: reqHeaders
      },
      (res) => {
        const chunks = [];
        let size = 0;
        res.on('data', (chunk) => {
          size += chunk.length;
          if (size > MAX_RESP_BYTES) {
            const e = new Error('后端响应体超过 2MB');
            e.code = 'CF_RESP_TOO_LARGE';
            req.destroy(e);
            return;
          }
          chunks.push(chunk);
        });
        res.on('end', () => {
          resolve({
            status: res.statusCode || 0,
            body: Buffer.concat(chunks).toString('utf8'),
            headers: res.headers || {}
          });
        });
      }
    );

    req.setTimeout(timeoutMs, () => {
      const e = new Error('请求后端超时');
      e.code = 'CF_TIMEOUT';
      req.destroy(e);
    });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

/**
 * 带重试的请求：仅 timeout / network 重试，重试次数默认 1（T-206 验收口径）。
 * 说明：5xx 是否重试由调用方决定（handler 需要先读响应体再判断），本函数只管传输层。
 * @param {object} opts requestOnce 参数
 * @param {number} retry 重试次数（0 = 不重试）
 * @returns {Promise<{status:number,body:string,headers:object,attempts:number}>}
 */
async function requestWithRetry(opts, retry = 1) {
  let lastErr = null;
  let attempts = 0;
  for (let i = 0; i <= retry; i += 1) {
    attempts = i + 1;
    try {
      const res = await requestOnce(opts);
      return Object.assign(res, { attempts });
    } catch (err) {
      lastErr = err;
      if (err.code === 'CF_BAD_URL') break;
    }
  }
  const err = lastErr || new Error('未知传输错误');
  err.attempts = attempts;
  throw err;
}

module.exports = { requestOnce, requestWithRetry, classifyError };
