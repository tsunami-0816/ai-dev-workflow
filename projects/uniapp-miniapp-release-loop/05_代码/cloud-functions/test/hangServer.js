'use strict';

/**
 * 「永不响应」的假后端（用于验证云函数 3s 超时 + 重试 1 次 → 50002）。
 * 启动：node test/hangServer.js   默认 127.0.0.1:8096（HANG_PORT 可改）
 */

const http = require('node:http');

const port = Number.parseInt(process.env.HANG_PORT, 10) || 8096;
const host = '127.0.0.1';
let accepted = 0;

const server = http.createServer(() => {
  accepted += 1; // 故意不写响应，连接挂起
});

server.listen(port, host, () => {
  process.stdout.write(JSON.stringify({ service: 'hangServer', event: 'listen', port }) + '\n');
});

process.on('SIGTERM', () => {
  process.stdout.write(JSON.stringify({ service: 'hangServer', accepted }) + '\n');
  process.exit(0);
});
