'use strict';

/**
 * 云函数配置（T-206）。
 * 入参：无（读环境变量）。出参：配置对象。异常：CF_TIMEOUT_MS / CF_RETRY 非数字时回落默认值。
 *
 * 密钥纪律：APP_SECRET / MP_APPSECRET 只从环境变量读，永不写入代码、日志、响应。
 */

const DEFAULT_BACKEND = 'http://127.0.0.1:8092';
const DEFAULT_SECRET = 'dev-only-hmac-secret-change-me'; // 与后端 application.yml 默认值一致，仅本地 dev

function readInt(name, def) {
  const n = Number.parseInt(process.env[name], 10);
  return Number.isFinite(n) && n > 0 ? n : def;
}

function stripSlash(v) {
  return String(v || '').replace(/\/+$/, '');
}

module.exports = {
  backendBase: stripSlash(process.env.CF_BACKEND_BASE || process.env.BACKEND_BASE || DEFAULT_BACKEND),
  appSecret: process.env.APP_SECRET || DEFAULT_SECRET,
  // T-206：3s 超时（小于后端 Tomcat connectionTimeout 5s，避免叠加双写，靠幂等兜底）
  timeoutMs: readInt('CF_TIMEOUT_MS', 3000),
  // T-206：非 2xx / 超时 / 网络错误重试 1 次
  retry: readInt('CF_RETRY', 1),
  port: readInt('CF_PORT', 8093),
  openidPort: readInt('OPENID_PORT', 8094),
  host: process.env.CF_HOST || '127.0.0.1',
  mode: String(process.env.CF_MODE || 'http').toLowerCase(),
  maxBodyBytes: readInt('CF_MAX_BODY_BYTES', 1024 * 1024),
  mpAppId: process.env.MP_APPID || '',
  mpAppSecret: process.env.MP_APPSECRET || '',
  wxApiBase: stripSlash(process.env.WX_API_BASE || 'https://api.weixin.qq.com'),
  // 只用于健康检查输出「是否显式配置」，不输出密钥内容
  secretConfigured: Boolean(process.env.APP_SECRET)
};
