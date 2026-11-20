'use strict';

/**
 * 签名与标识生成（T-206 / D-16）。
 * 与后端 SignatureFilter 同口径：X-Sign = hex(HMAC-SHA256(rawBody + "|" + X-Timestamp, APP_SECRET))，小写。
 */

const crypto = require('node:crypto');

/**
 * 计算请求签名。
 * @param {string} rawBody 原始请求体字符串（GET 传空串）
 * @param {string|number} ts 秒级时间戳
 * @param {string} secret 共享密钥 APP_SECRET
 * @returns {string} 64 位小写 hex
 */
function hmacHex(rawBody, ts, secret) {
  return crypto
    .createHmac('sha256', String(secret))
    .update(String(rawBody) + '|' + String(ts), 'utf8')
    .digest('hex');
}

/**
 * 生成防重放 nonce：32 位 hex，满足后端 [A-Za-z0-9_-]{8,64}。
 * @returns {string}
 */
function makeNonce() {
  return crypto.randomBytes(16).toString('hex');
}

/**
 * 生成追踪号：cf-xxxxxxxx（8 位 hex）。
 * @returns {string}
 */
function makeTraceId() {
  return 'cf-' + crypto.randomBytes(4).toString('hex');
}

module.exports = { hmacHex, makeNonce, makeTraceId };
