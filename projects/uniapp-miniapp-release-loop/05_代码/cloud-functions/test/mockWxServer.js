'use strict';

/**
 * 微信 code2session 本地 mock（仅用于自测 getOpenid 的解析路径，不接入真实微信）。
 * 启动：node test/mockWxServer.js   默认 127.0.0.1:8095（MOCK_WX_PORT 可改）
 * 规则：js_code 以 good 开头 → 返回固定 openid；以 bad 开头 → 返回 errcode 40029。
 */

const http = require('node:http');

const port = Number.parseInt(process.env.MOCK_WX_PORT, 10) || 8095;
const host = '127.0.0.1';

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (req.method === 'GET' && url.pathname === '/sns/jscode2session') {
    const code = url.searchParams.get('js_code') || '';
    const appid = url.searchParams.get('appid') || '';
    const body = code.startsWith('bad')
      ? { errcode: 40029, errmsg: 'invalid code' }
      : { openid: 'o_mock_' + (appid || 'app') + '_' + code.slice(0, 8), session_key: 'mock-session-key' };
    const raw = Buffer.from(JSON.stringify(body), 'utf8');
    res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': String(raw.length) });
    res.end(raw);
    return;
  }
  res.writeHead(404).end();
});

server.listen(port, host, () => {
  process.stdout.write(JSON.stringify({ service: 'mockWx', event: 'listen', port }) + '\n');
});
