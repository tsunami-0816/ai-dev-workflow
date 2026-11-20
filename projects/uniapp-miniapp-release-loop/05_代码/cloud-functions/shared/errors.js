'use strict';

/**
 * 统一错误码与响应构造（T-206）。
 * 码值与后端 com.uniapp.booking.common.ErrorCode 保持一致，前端只需维护一张表。
 */

const CODES = {
  OK: 0,
  PARAM_INVALID: 40001,
  DATE_OUT_OF_RANGE: 40002,
  UNAUTHORIZED: 40101,
  BAD_SIGNATURE: 40102,
  TOKEN_EXPIRED: 40103,
  FORBIDDEN: 40301,
  NOT_FOUND: 40400,
  PACKAGE_NOT_FOUND: 40401,
  RATE_LIMITED: 42901,
  SERVER_ERROR: 50000,
  SERVICE_ERROR: 50001,
  UPSTREAM_TIMEOUT: 50002
};

const MESSAGES = {
  0: 'ok',
  40001: '参数不合法',
  40002: '预约日期超出可预约范围',
  40101: '未登录或登录态无效',
  40102: '签名校验失败',
  40103: '登录已过期，请重新登录',
  40301: '无权访问该数据',
  40400: '接口不存在',
  40401: '套餐不存在',
  42901: '请勿重复提交',
  50000: '服务器开小差了，请稍后重试',
  50001: '服务开小差了，请稍后重试',
  50002: '网络不稳定，请重试'
};

/**
 * 业务码 → HTTP 状态（与后端 GlobalExceptionHandler 一一对应）。
 * @param {number} code
 * @returns {number}
 */
function httpStatusFor(code) {
  switch (code) {
    case CODES.OK:
      return 200;
    case CODES.PARAM_INVALID:
    case CODES.DATE_OUT_OF_RANGE:
      return 400;
    case CODES.UNAUTHORIZED:
    case CODES.BAD_SIGNATURE:
    case CODES.TOKEN_EXPIRED:
      return 401;
    case CODES.FORBIDDEN:
      return 403;
    case CODES.NOT_FOUND:
    case CODES.PACKAGE_NOT_FOUND:
      return 404;
    case CODES.RATE_LIMITED:
      return 429;
    case CODES.UPSTREAM_TIMEOUT:
      return 504;
    default:
      return 500;
  }
}

/**
 * 构造成功响应。
 * @param {*} data
 * @param {string} traceId
 * @param {number} elapsedMs
 * @returns {{code:number,msg:string,data:*,traceId:string,elapsedMs:number}}
 */
function ok(data, traceId, elapsedMs) {
  return { code: CODES.OK, msg: 'ok', data: data === undefined ? null : data, traceId, elapsedMs };
}

/**
 * 构造失败响应。
 * @param {number} code
 * @param {string} [msg] 缺省用码表文案；前端字段级红字依赖自定义 msg
 * @param {string} traceId
 * @param {number} elapsedMs
 * @returns {{code:number,msg:string,data:null,traceId:string,elapsedMs:number}}
 */
function fail(code, msg, traceId, elapsedMs) {
  return {
    code,
    msg: msg || MESSAGES[code] || '服务开小差了，请稍后重试',
    data: null,
    traceId,
    elapsedMs
  };
}

module.exports = { CODES, MESSAGES, httpStatusFor, ok, fail };
