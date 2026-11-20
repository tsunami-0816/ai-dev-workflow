'use strict';

/**
 * 云开发入口（T-206 双模式之 cloud）。
 * 小程序端：wx.cloud.callFunction({ name:'apiProxy', data:{ action:'packages', payload:{page:1}, token } })
 */

const { handle } = require('../shared/proxyHandler');

/**
 * 云函数主入口。
 * @param {object} event 云开发透传的 data
 * @returns {Promise<object>} {code,msg,data,traceId,elapsedMs}
 */
exports.main = async (event) => handle(event || {});
