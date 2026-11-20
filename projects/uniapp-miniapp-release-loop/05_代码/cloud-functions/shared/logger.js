'use strict';

/**
 * 结构化单行日志（T-206）。stdout 一请求一行，便于脚本 grep。
 * 禁止写入：token 明文、APP_SECRET、MP_APPSECRET、请求体全文。
 */

/**
 * 输出一行 JSON 日志。
 * @param {object} fields 白名单字段：action/code/elapsedMs/attempts/backendStatus/traceId/msg
 * @returns {void}
 */
function logEvent(fields) {
  const line = Object.assign({ ts: new Date().toISOString() }, fields);
  process.stdout.write(JSON.stringify(line) + '\n');
}

module.exports = { logEvent };
