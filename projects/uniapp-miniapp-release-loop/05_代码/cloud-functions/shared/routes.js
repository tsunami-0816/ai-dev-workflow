'use strict';

/**
 * action 白名单与入参校验（T-206 / D-16「参数白名单校验」）。
 * 原则：只允许已知字段进入后端；多余字段直接 40001，避免前端塞 userId 之类的越权参数。
 */

const { CODES } = require('./errors');

const SLOTS = ['上午', '下午', '晚间'];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const PHONE_RE = /^1[3-9]\d{9}$/;
const JWT_RE = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;

function bad(msg, code) {
  return { ok: false, code: code || CODES.PARAM_INVALID, msg };
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function extraKey(obj, allowed) {
  return Object.keys(obj).find((k) => !allowed.includes(k));
}

function asInt(v, min, max) {
  let n;
  if (typeof v === 'number' && Number.isInteger(v)) n = v;
  else if (typeof v === 'string' && /^\d+$/.test(v)) n = Number.parseInt(v, 10);
  else return null;
  if (!Number.isInteger(n) || n < min || n > max) return null;
  return n;
}

function isIsoDate(s) {
  if (typeof s !== 'string' || !DATE_RE.test(s)) return false;
  const d = new Date(s + 'T00:00:00Z');
  if (Number.isNaN(d.getTime())) return false;
  return d.toISOString().slice(0, 10) === s;
}

function checkToken(token) {
  if (typeof token !== 'string' || token.length === 0) {
    return bad('登录态缺失，请先登录', CODES.UNAUTHORIZED);
  }
  if (token.length > 4096 || /\s/.test(token) || !JWT_RE.test(token)) {
    return bad('登录态格式不合法', CODES.UNAUTHORIZED);
  }
  return { ok: true, value: token };
}

function pageOf(payload) {
  const page = payload.page === undefined ? 1 : asInt(payload.page, 1, 1000);
  const size = payload.size === undefined ? 10 : asInt(payload.size, 1, 50);
  if (page === null) return bad('page 需为 1~1000 的整数');
  if (size === null) return bad('size 需为 1~50 的整数');
  return { ok: true, value: { page, size } };
}

/**
 * 动作路由表。每项：
 * - method / auth
 * - allowed: payload 允许字段
 * - validate(payload, token) → {ok:true, value:{path, body}} | {ok:false, code, msg}
 */
const ROUTES = {
  packages: {
    method: 'GET',
    auth: false,
    allowed: ['page', 'size'],
    validate(payload) {
      if (!isPlainObject(payload)) return bad('payload 必须是对象');
      const extra = extraKey(payload, this.allowed);
      if (extra) return bad('不支持的字段: ' + extra);
      const p = pageOf(payload);
      if (!p.ok) return p;
      return {
        ok: true,
        value: { path: '/api/packages?page=' + p.value.page + '&size=' + p.value.size, body: null }
      };
    }
  },

  packageDetail: {
    method: 'GET',
    auth: false,
    allowed: ['id'],
    validate(payload) {
      if (!isPlainObject(payload)) return bad('payload 必须是对象');
      const extra = extraKey(payload, this.allowed);
      if (extra) return bad('不支持的字段: ' + extra);
      const id = asInt(payload.id, 1, 1000000000);
      if (id === null) return bad('id 需为正整数');
      return { ok: true, value: { path: '/api/packages/' + id, body: null } };
    }
  },

  login: {
    method: 'POST',
    auth: false,
    allowed: ['account', 'password', 'openid', 'nickname'],
    validate(payload) {
      if (!isPlainObject(payload)) return bad('payload 必须是对象');
      const extra = extraKey(payload, this.allowed);
      if (extra) return bad('不支持的字段: ' + extra);
      const body = {};
      if (payload.account !== undefined) {
        if (typeof payload.account !== 'string' || payload.account.length > 32) {
          return bad('account 需为不超过 32 字的字符串');
        }
        body.account = payload.account;
      }
      if (payload.password !== undefined) {
        if (typeof payload.password !== 'string' || payload.password.length > 64) {
          return bad('password 需为不超过 64 字的字符串');
        }
        body.password = payload.password;
      }
      if (payload.openid !== undefined) {
        if (typeof payload.openid !== 'string' || !/^[A-Za-z0-9_-]{10,64}$/.test(payload.openid)) {
          return bad('openid 格式不合法');
        }
        body.openid = payload.openid;
      }
      if (payload.nickname !== undefined) {
        if (typeof payload.nickname !== 'string' || payload.nickname.length > 64) {
          return bad('nickname 需为不超过 64 字的字符串');
        }
        body.nickname = payload.nickname;
      }
      if (body.openid) {
        return { ok: true, value: { path: '/api/auth/login', body } };
      }
      if (!body.account) return bad('account 与 openid 至少提供一个');
      if (!body.password) return bad('password 不能为空');
      return { ok: true, value: { path: '/api/auth/login', body } };
    }
  },

  logout: {
    method: 'POST',
    auth: true,
    allowed: [],
    validate(payload, token) {
      if (payload !== undefined && payload !== null && !isPlainObject(payload)) {
        return bad('payload 必须是对象');
      }
      const extra = extraKey(payload || {}, this.allowed);
      if (extra) return bad('不支持的字段: ' + extra);
      const t = checkToken(token);
      if (!t.ok) return t;
      return { ok: true, value: { path: '/api/auth/logout', body: {} } };
    }
  },

  createBooking: {
    method: 'POST',
    auth: true,
    allowed: ['packageId', 'bookDate', 'slot', 'contact', 'remark'],
    validate(payload, token) {
      if (!isPlainObject(payload)) return bad('payload 必须是对象');
      const extra = extraKey(payload, this.allowed);
      if (extra) return bad('不支持的字段: ' + extra);
      const t = checkToken(token);
      if (!t.ok) return t;

      const packageId = asInt(payload.packageId, 1, 1000000000);
      if (packageId === null) return bad('packageId 需为正整数');
      if (!isIsoDate(payload.bookDate)) return bad('bookDate 需为真实存在的 YYYY-MM-DD 日期');
      if (typeof payload.slot !== 'string' || !SLOTS.includes(payload.slot)) {
        return bad('slot 需为 上午/下午/晚间 之一');
      }
      if (typeof payload.contact !== 'string' || !PHONE_RE.test(payload.contact)) {
        return bad('contact 手机号格式不正确');
      }
      if (payload.remark !== undefined && payload.remark !== null) {
        if (typeof payload.remark !== 'string' || payload.remark.length > 255) {
          return bad('remark 需为不超过 255 字的字符串');
        }
      }

      const body = { packageId, bookDate: payload.bookDate, slot: payload.slot, contact: payload.contact };
      if (typeof payload.remark === 'string') body.remark = payload.remark;
      return { ok: true, value: { path: '/api/bookings', body } };
    }
  },

  myBookings: {
    method: 'GET',
    auth: true,
    allowed: ['page', 'size'],
    validate(payload, token) {
      if (!isPlainObject(payload)) return bad('payload 必须是对象');
      const extra = extraKey(payload, this.allowed);
      if (extra) return bad('不支持的字段: ' + extra);
      const t = checkToken(token);
      if (!t.ok) return t;
      const p = pageOf(payload);
      if (!p.ok) return p;
      return {
        ok: true,
        value: { path: '/api/bookings?page=' + p.value.page + '&size=' + p.value.size, body: null }
      };
    }
  }
};

module.exports = { ROUTES, SLOTS };
