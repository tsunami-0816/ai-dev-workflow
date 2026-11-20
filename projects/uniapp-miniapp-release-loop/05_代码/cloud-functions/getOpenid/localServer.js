'use strict';

/**
 * getOpenid 本机 http 入口（T-206 / D-17 双模式的本地等价物）。
 * 启动：node getOpenid/localServer.js   默认 127.0.0.1:8094（端口来自 OPENID_PORT）
 * 注意：真实 code2session 需要 MP_APPID + MP_APPSECRET；缺失时返回明确 50001，不会伪造 openid。
 */

const http = require('node:http');
const config = require('../shared/config');
const { handle } = require('./index');
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

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'GET' && req.url === '/healthz') {
      sendJson(res, 200, {
        status: 'UP',
        service: 'getOpenid',
        port: config.openidPort,
        wxApiBase: config.wxApiBase,
        appIdConfigured: Boolean(config.mpAppId),
        appSecretConfigured: Boolean(config.mpAppSecret),
        uptimeSec: Math.floor((Date.now() - startedAt) / 1000)
      });
      return;
    }

    if (req.method === 'POST' && req.url === '/') {
      const chunks = [];
      let size = 0;
      let tooBig = false;
      req.on('data', (chunk) => {
        size += chunk.length;
        if (size > 64 * 1024) tooBig = true;
        else chunks.push(chunk);
      });
      req.on('end', async () => {
        if (tooBig) {
          sendJson(res, 413, fail(CODES.PARAM_INVALID, '请求体过大'));
          return;
        }
        let event;
        try {
          event = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        } catch (err) {
          sendJson(res, 400, fail(CODES.PARAM_INVALID, '请求体不是合法 JSON'));
          return;
        }
        const result = await handle(event);
        sendJson(res, httpStatusFor(result.code), result);
      });
      return;
    }

    sendJson(res, 404, fail(CODES.NOT_FOUND, '路径不存在'));
  } catch (err) {
    sendJson(res, 500, fail(CODES.SERVICE_ERROR, 'getOpenid 内部异常'));
  }
});

server.listen(config.openidPort, config.host, () => {
  process.stdout.write(
    JSON.stringify({
      ts: new Date().toISOString(),
      service: 'getOpenid',
      event: 'listen',
      host: config.host,
      port: config.openidPort,
      wxApiBase: config.wxApiBase
    }) + '\n'
  );
});

function shutdown() {
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(0), 3000).unref();
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
