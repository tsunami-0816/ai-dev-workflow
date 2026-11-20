'use strict';

/**
 * 本机 http 模式入口（T-206 双模式之 http / D-17）。
 * 用途：无云开发环境或本机联调时，小程序（开发者工具）把请求打到 127.0.0.1:8093，行为与云上一致。
 * 启动：node apiProxy/localServer.js   （环境变量见 05_代码/cloud-functions/.env.example）
 * 仅监听 127.0.0.1，不对外暴露。
 */

const http = require('node:http');
const config = require('../shared/config');
const { handle } = require('../shared/proxyHandler');
const { fail, httpStatusFor, CODES } = require('../shared/errors');

const startedAt = Date.now();

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload), 'utf8');
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': String(body.length),
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

/**
 * 健康检查。
 * - 不带 probe：只报本进程状态（不打扰后端）
 * - 带 probe=1：真实转发一次 packages，用于验证「云函数 → 后端」签名链路是否对齐
 */
async function healthz(req, res) {
  const url = new URL(req.url, 'http://127.0.0.1');
  const base = {
    status: 'UP',
    service: 'apiProxy',
    mode: config.mode,
    port: config.port,
    backend: config.backendBase,
    secretConfigured: config.secretConfigured,
    timeoutMs: config.timeoutMs,
    retry: config.retry,
    uptimeSec: Math.floor((Date.now() - startedAt) / 1000)
  };
  if (url.searchParams.get('probe') === '1') {
    const r = await handle({ action: 'packages', payload: { page: 1, size: 1 } });
    base.backendProbe = { code: r.code, msg: r.msg, elapsedMs: r.elapsedMs, traceId: r.traceId };
  }
  sendJson(res, 200, base);
}

function readBody(req, limit) {
  return new Promise((resolve) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size <= limit) chunks.push(chunk); // 超限只丢弃，不中断连接，便于返回明确的 413
    });
    req.on('end', () => {
      resolve({ size, text: size <= limit ? Buffer.concat(chunks).toString('utf8') : null });
    });
    req.on('error', () => resolve({ size, text: null }));
  });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && (req.url === '/healthz' || req.url.startsWith('/healthz?'))) {
      await healthz(req, res);
      return;
    }

    if (req.method === 'POST' && (req.url === '/' || req.url === '/apiProxy')) {
      const body = await readBody(req, config.maxBodyBytes);
      if (body.text === null) {
        sendJson(res, 413, fail(CODES.PARAM_INVALID, '请求体过大（上限 ' + config.maxBodyBytes + ' 字节）'));
        return;
      }
      if (body.size === 0) {
        sendJson(res, 400, fail(CODES.PARAM_INVALID, '请求体不能为空'));
        return;
      }
      let event;
      try {
        event = JSON.parse(body.text);
      } catch (err) {
        sendJson(res, 400, fail(CODES.PARAM_INVALID, '请求体不是合法 JSON'));
        return;
      }
      const result = await handle(event);
      sendJson(res, httpStatusFor(result.code), result);
      return;
    }

    if (req.method === 'GET' && req.url === '/') {
      sendJson(res, 200, {
        service: 'apiProxy',
        usage: 'POST / {action, payload, token}；GET /healthz[?probe=1]'
      });
      return;
    }

    sendJson(res, 404, fail(CODES.NOT_FOUND, '路径不存在'));
  } catch (err) {
    sendJson(res, 500, fail(CODES.SERVICE_ERROR, '云函数内部异常'));
  }
});

server.listen(config.port, config.host, () => {
    process.stdout.write(
    JSON.stringify({
      ts: new Date().toISOString(),
      service: 'apiProxy',
      event: 'listen',
      host: config.host,
      port: config.port,
      backend: config.backendBase,
      mode: config.mode
    }) + '\n'
  );
});

function shutdown() {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
