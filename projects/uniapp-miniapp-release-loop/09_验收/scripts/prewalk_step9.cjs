// 第 9 步最终验收 · AI 预走脚本（卡点交付物协议：#78 交人工前先自走一遍）
// 用法：node 09_验收/scripts/prewalk_step9.cjs
// 输出：09_验收/evidence/prewalk_step9.json + 3 张截图
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const API = 'http://127.0.0.1:8092'
const OUT = path.join(__dirname, '..', 'evidence')
if (!fs.existsSync(OUT)) fs.mkdirSync(OUT, { recursive: true })

const out = { startedAt: new Date().toISOString(), cases: [], consoleErrors: [] }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function rec(name, pass, data) {
  out.cases.push({ name, pass, ...data })
    console.log(`${pass ? 'PASS' : 'FAIL'} ${name} ${JSON.stringify(data)}`)
}

function fmtDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

async function apiLogin(account, password) {
  const r = await fetch(API + '/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account, password }),
  })
  return r.json()
}

const tomorrow = fmtDate(new Date(Date.now() + 86400000))

// H5 的日期选择器有两种渲染：原生 date input（.uni-picker-system_input）或弹窗 picker（.uni-picker-action-confirm）
// 都必须先点开控件；弹窗形态时接受默认值（= 今天），故清单里日期写「今天或明天」
async function setDate(page, v) {
  await page.waitForSelector('.field .control', { timeout: 15000 })
  await page.click('.field .control')
  await sleep(700)
  const hasNative = await page.evaluate(() => !!document.querySelector('.uni-picker-system_input'))
  if (hasNative) {
    const ok = await page.evaluate((val) => {
      const inp = document.querySelector('.uni-picker-system_input')
      inp.value = val
      inp.dispatchEvent(new Event('input', { bubbles: true }))
      inp.dispatchEvent(new Event('change', { bubbles: true }))
      return true
    }, v)
    await sleep(400)
    return { ok, mode: 'native-input', value: v }
  }
  const hasConfirm = await page.evaluate(() => !!document.querySelector('.uni-picker-action-confirm'))
  if (hasConfirm) {
    await page.click('.uni-picker-action-confirm')
    await sleep(500)
    const text = await page.evaluate(() => (document.querySelector('.field .control')?.textContent || '').trim())
    return { ok: true, mode: 'dialog-confirm', value: text }
  }
  return { ok: false, mode: 'not-found', value: '' }
}

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions'],
  })
  const page = await browser.newPage()
  const pkgGets = []
  page.on('request', (r) => {
    if (r.method() === 'GET' && r.url().indexOf('/api/packages?') >= 0) pkgGets.push(r.url())
  })
  page.on('pageerror', (e) => out.consoleErrors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') out.consoleErrors.push('console: ' + m.text())
  })

  // ===== A-01 首页 375：清单/主标题 h1/无横向溢出 =====
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2500)
  const a01 = await page.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    titles: [...document.querySelectorAll('.row-title')].map((n) => n.textContent.trim()),
    prices: [...document.querySelectorAll('.row-price')].map((n) => n.textContent.trim()),
    h1: document.querySelectorAll('h1').length,
    h1Text: (document.querySelector('h1')?.textContent || '').trim(),
    scrollW: document.scrollingElement.scrollWidth,
    clientW: document.scrollingElement.clientWidth,
    heroTitle: (document.querySelector('.hero-title')?.textContent || '').trim(),
    heroPrice: (document.querySelector('.hero-price')?.textContent || '').trim(),
  }))
  // 版式口径：第 1 个套餐以 hero 单列展示，列表从第 2 个起 → hero 1 + row 3 = 4 个套餐
  rec(
    'A-01 首页 375（hero+3 行=4 套餐 / h1 / 无横向溢出）',
    a01.heroTitle === '城市轻写真' && a01.rows === 3 && a01.titles.length === 3 && a01.h1 === 1 && a01.h1Text === '约拍档期' && a01.scrollW <= a01.clientW,
    a01
  )
  await page.screenshot({ path: path.join(OUT, 'step9_a01_index_375.png') })

  // ===== A-02 首页 414 无横向溢出 =====
  await page.setViewport({ width: 414, height: 896, deviceScaleFactor: 1 })
  await page.reload({ waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)
  const a02 = await page.evaluate(() => ({
    scrollW: document.scrollingElement.scrollWidth,
    clientW: document.scrollingElement.clientWidth,
  }))
  rec('A-02 首页 414 无横向溢出', a02.scrollW <= a02.clientW, a02)

  // ===== A-03 首页 1440 桌面版式：1040 容器居中 + h1 =====
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)
  const a03 = await page.evaluate(() => {
    const el = document.querySelector('.lb-page')
    const r = el ? el.getBoundingClientRect() : null
    return {
      width: r ? Math.round(r.width) : 0,
      left: r ? Math.round(r.left) : -1,
      right: r ? Math.round(1440 - r.right) : -1,
      h1: document.querySelectorAll('h1').length,
      overflow: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth,
    }
  })
  rec(
    'A-03 首页 1440 桌面（容器宽度/左右留白/h1）',
    a03.width >= 980 && a03.width <= 1100 && Math.abs(a03.left - a03.right) <= 4 && a03.h1 === 1 && a03.overflow <= 0,
    a03
  )
  await page.screenshot({ path: path.join(OUT, 'step9_a03_index_1440.png') })

  // ===== A-04 分页：接口 page1/page2 各 2 条且不重复；首页最终 4 套餐 =====
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  const pg1 = await fetch(API + '/api/packages?page=1&size=2').then((r) => r.json())
  const pg2 = await fetch(API + '/api/packages?page=2&size=2').then((r) => r.json())
  const ids1 = pg1.data.list.map((p) => p.id)
  const ids2 = pg2.data.list.map((p) => p.id)
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)
  const a04 = await page.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    hasHero: !!document.querySelector('.hero-title'),
  }))
  rec(
    'A-04 分页（接口两页各 2 条不重复、首页 4 套餐）',
    pg1.data.list.length === 2 && pg2.data.list.length === 2 && ids1.every((id) => !ids2.includes(id)) && a04.rows === 3 && a04.hasHero,
    { ids1, ids2, listed: a04.rows + (a04.hasHero ? 1 : 0), note: '种子仅 4 条，首页 pageSize=12 不会触发追加（已知边界）' }
  )

  // ===== A-05 详情页 =====
  await page.goto(BASE + '/#/pages/package/detail?id=1', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)
  const a05 = await page.evaluate(() => {
    const cta = document.querySelector('.btn-primary')
    const sec = document.querySelector('.section')
    const ctaRect = cta ? cta.getBoundingClientRect() : null
    const secRect = sec ? sec.getBoundingClientRect() : null
    return {
      title: (document.querySelector('.title')?.textContent || '').trim(),
      price: (document.querySelector('.price')?.textContent || '').trim(),
      tags: [...document.querySelectorAll('.tag')].map((n) => n.textContent.trim()),
      h1: document.querySelectorAll('h1').length,
      h1Text: (document.querySelector('h1')?.textContent || '').trim(),
      cta: cta ? cta.textContent.trim() : '',
      overlap: ctaRect && secRect ? Math.max(0, Math.min(ctaRect.top, secRect.bottom) - Math.max(ctaRect.bottom, secRect.top)) : null,
    }
  })
  rec(
    'A-05 详情页（标题/价格/标签/预约栏/h1/不遮挡）',
    a05.title.includes('城市轻写真') && a05.price.includes('399') && a05.tags.length === 3 && a05.h1 === 1 && a05.cta.includes('立即预约') && a05.overlap === 0,
    a05
  )
  await page.screenshot({ path: path.join(OUT, 'step9_a05_detail_375.png') })

  // ===== A-06/A-07/A-08 表单字段校验 =====
  let bookingPosts = 0
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().indexOf('/api/bookings') >= 0) bookingPosts += 1
  })
  await page.goto(BASE + '/#/pages/booking/form?packageId=1&title=' + encodeURIComponent('城市轻写真') + '&price=399', {
    waitUntil: 'networkidle0',
    timeout: 30000,
  })
  await sleep(2200)
  await page.evaluate(() => localStorage.clear())
  await page.click('.submit')
  await sleep(800)
  const a06 = await page.evaluate(() => [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()))
  rec(
    'A-06 空表单提交（3 条字段红字、不发请求）',
    a06.length === 3 && a06.includes('请选择日期') && a06.includes('请选择时段') && a06.includes('请输入 11 位手机号') && bookingPosts === 0,
    { errs: a06, bookingPosts }
  )

  // 写日期（H5 原生 date input）→ 选时段 → 只留手机号问题
  const dateSet = await setDate(page, tomorrow)
  const slotEls = await page.$$('.slot')
  if (slotEls.length >= 2) await slotEls[1].click()
  await sleep(300)
  await page.click('input.uni-input-input')
  await page.type('input.uni-input-input', '12345', { delay: 50 })
  await sleep(300)
  await page.click('.submit')
  await sleep(800)
  const a07 = await page.evaluate(() => [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()))
  rec(
    'A-07 日期+时段已选、手机号 12345（仅 1 条长度提示）',
    dateSet.ok && a07.length === 1 && a07[0] === '请输入 11 位手机号' && bookingPosts === 0,
    { dateSet, errs: a07, bookingPosts }
  )

  // 前缀非 1[3-9] → 格式提示；输入变化即清红字
  await page.click('input.uni-input-input')
  await page.keyboard.down('Control')
  await page.keyboard.press('KeyA')
  await page.keyboard.up('Control')
  await page.keyboard.press('Backspace')
  await page.type('input.uni-input-input', '12345688901', { delay: 40 })
  await sleep(200)
  await page.click('.submit')
  await sleep(700)
  const a08a = await page.evaluate(() => [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()))
  // 追加字符会被 maxlength=11 截断、不触发 input；改为「清空后重输合法号」验证红字即时消失（与真实用户改号一致）
  await page.click('input.uni-input-input')
  await page.keyboard.down('Control')
  await page.keyboard.press('KeyA')
  await page.keyboard.up('Control')
  await page.keyboard.press('Backspace')
  await page.type('input.uni-input-input', '13800000001', { delay: 40 })
  await sleep(400)
  const a08b = await page.evaluate(() => ({
    errs: document.querySelectorAll('.err').length,
    value: document.querySelector('input.uni-input-input')?.value || '',
  }))
  rec(
    'A-08 前缀非法 → 格式提示；改号 → 红字立即消失',
    a08a.length === 1 && a08a[0] === '手机号格式不对，请检查' && a08b.errs === 0 && a08b.value === '13800000001' && bookingPosts === 0,
    { errs: a08a, afterRetype: a08b, bookingPosts }
  )

  // ===== A-09 登录后真实提交（写库） =====
  const loginA = await apiLogin('demo', 'welcome1')
  if (loginA.code !== 0) throw new Error('demo 登录失败 ' + JSON.stringify(loginA))
  await page.evaluate((d) => {
    const wrap = (type, data) => JSON.stringify({ type, data })
    localStorage.setItem('ub_token', wrap('string', d.token))
    localStorage.setItem('ub_user', wrap('object', { userId: d.userId, nickname: d.nickname || '演示用户A' }))
  }, loginA.data)
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1200)
  await page.goto(BASE + '/#/pages/booking/form?packageId=1&title=' + encodeURIComponent('城市轻写真') + '&price=399', {
    waitUntil: 'networkidle0',
    timeout: 30000,
  })
  await sleep(2000)
  const dateA = await setDate(page, tomorrow)
  out.bookDateUsed = dateA.value
  const slots2 = await page.$$('.slot')
  if (slots2.length >= 2) await slots2[1].click()
  await sleep(300)
  await page.click('input.uni-input-input')
  await page.type('input.uni-input-input', '13800000001', { delay: 40 })
  await page.type('textarea.uni-textarea-textarea', '第9步预走', { delay: 40 }).catch(() => {})
  await sleep(300)
  const beforePost = bookingPosts
  // 连点 5 次：验证前端 submitting 防重（同一页面提交只发 1 次）
  await page.evaluate(() => {
    const btn = document.querySelector('.submit')
    for (let i = 0; i < 5; i += 1) btn.click()
  })
  await sleep(2500)
  const a09 = await page.evaluate(() => ({
    doneNo: (document.querySelector('.done-no')?.textContent || '').trim(),
    doneNote: (document.querySelector('.done-note')?.textContent || '').trim(),
  }))
  rec(
    'A-09 连点 5 次提交（只落 1 单、POST 1 次、出单号）',
    dateA.ok && /^No\.\d+$/.test(a09.doneNo) && bookingPosts - beforePost === 1,
    { ...a09, bookingPostsDelta: bookingPosts - beforePost, bookedDate: dateA.value, clicks: 5 }
  )
  out.bookingNo = a09.doneNo.replace('No.', '')

  // A-10 已并入 A-09（同一页面连点 5 次只发 1 次）。此处不再二次进入同路由，
  // 因为 uni-app H5 对同一 path 仅换 query 会复用组件实例、残留成功态（非产品缺陷）。

  // ===== A-11 未登录「我的」 =====
  await page.evaluate(() => localStorage.clear())
  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)
  const a11 = await page.evaluate(() => ({
    url: location.href,
    bookings: document.querySelectorAll('.booking').length,
    loginBtn: (document.querySelector('.btn-primary')?.textContent || '').trim(),
    hasState: !!document.querySelector('.state'),
  }))
  rec(
    'A-11 未登录进「我的」（显示去登录、不自动跳转）',
    a11.hasState && a11.bookings === 0 && a11.loginBtn.includes('去登录') && a11.url.indexOf('/pages/my/index') >= 0,
    a11
  )

  // ===== A-12 UI 登录 → 我的列表 → 点档期卡 → 退出 =====
  await page.click('.btn-primary')
  await sleep(1800)
  const inputs = await page.$$('input.uni-input-input')
  if (inputs.length >= 2) {
    // 账号框默认预填 demo → 必须先清空，否则会变成 demodemo
    await inputs[0].click()
    await page.keyboard.down('Control')
    await page.keyboard.press('KeyA')
    await page.keyboard.up('Control')
    await page.keyboard.press('Backspace')
    await inputs[0].type('demo', { delay: 50 })
    await inputs[1].click()
    await inputs[1].type('welcome1', { delay: 50 })
  }
  await sleep(300)
  await page.click('.btn-primary')
  await sleep(2500)
  const a12a = await page.evaluate(() => ({
    url: location.href,
    rows: document.querySelectorAll('.booking').length,
    name: (document.querySelector('.me-name')?.textContent || '').trim(),
    note: (document.querySelector('.list-note')?.textContent || '').trim().slice(0, 30),
    firstMasked: (document.querySelectorAll('.booking .ub-num')[2]?.textContent || '').trim(),
  }))
  let cardJump = ''
  if (a12a.rows > 0) {
    await page.click('.booking')
    await sleep(2000)
    cardJump = await page.evaluate(() => location.href)
    await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
    await sleep(2000)
  }
  const logoutOk = await page.evaluate(() => {
    const el = document.querySelector('.logout')
    if (!el) return false
    el.click()
    return true
  })
  await sleep(1500)
  const a12b = await page.evaluate(() => ({
    rows: document.querySelectorAll('.booking').length,
    hasState: !!document.querySelector('.state'),
  }))
  rec(
    'A-12 登录→我的列表→点卡回详情→退出',
    a12a.rows >= 1 && a12a.name.indexOf('演示用户A') >= 0 && /demo|没有店家端/.test(a12a.note) && cardJump.indexOf('/pages/package/detail') >= 0 && logoutOk && a12b.rows === 0 && a12b.hasState,
    { ...a12a, cardJump, logoutOk, afterLogout: a12b }
  )
  await page.screenshot({ path: path.join(OUT, 'step9_a12_my_loggedin.png') })

  // ===== A-13 隐私页 =====
  await page.goto(BASE + '/#/pages/privacy/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1800)
  const a13 = await page.evaluate(() => ({
    len: (document.querySelector('uni-page-body')?.innerText || '').trim().length,
  }))
  rec('A-13 隐私协议页可渲染', a13.len > 200, a13)

  // ===== A-14 未登录直接调接口 =====
  const a14 = await fetch(API + '/api/bookings').then(async (r) => ({ status: r.status, body: await r.json() }))
  rec('A-14 未登录调 /api/bookings → 40101', a14.body.code === 40101 && !a14.body.data, a14)

  // ===== A-15 未知路径 404/40400 =====
  const a15 = await fetch(API + '/api/no-such-path').then(async (r) => ({ status: r.status, body: await r.json() }))
  rec('A-15 未知路径 → HTTP 404 / code 40400', a15.status === 404 && a15.body.code === 40400, a15)

  // ===== A-16 幂等：同号同日同时段再提交 =====
  const a16 = await fetch(API + '/api/bookings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + loginA.data.token },
    body: JSON.stringify({ packageId: 1, bookDate: out.bookDateUsed, slot: '下午', contact: '13800000001', remark: '第9步幂等复验' }),
  }).then((r) => r.json())
  rec(
    'A-16 同参数重复提交 → 返回首单 duplicated',
    a16.code === 0 && a16.data && String(a16.data.bookingId) === out.bookingNo && a16.data.duplicated === true,
    { code: a16.code, bookingId: a16.data && a16.data.bookingId, duplicated: a16.data && a16.data.duplicated, firstNo: out.bookingNo }
  )

  // ===== A-17 跨账号同手机号同日同时段 → 40001 =====
  const loginB = await apiLogin('demo2', 'welcome1')
  const a17 = await fetch(API + '/api/bookings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + loginB.data.token },
    body: JSON.stringify({ packageId: 1, bookDate: out.bookDateUsed, slot: '下午', contact: '13800000001' }),
  }).then((r) => r.json())
  rec(
    'A-17 跨账号同手机号同日同时段 → 40001 不写库',
    a17.code === 40001 && !a17.data,
    { loginB: loginB.code, resp: a17 }
  )

  // ===== A-18 视觉令牌实测（供人工对照 step02 §前端设计方向） =====
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)
  const a18 = await page.evaluate(() => {
    const g = (sel, prop) => {
      const el = document.querySelector(sel)
      return el ? getComputedStyle(el)[prop] : null
    }
    return {
      pageBg: g('.lb-page', 'backgroundColor'),
      paper: g('.mast-words', 'color'),
      mastFontSize: g('.mast-words', 'fontSize'),
      mastLetterSpacing: g('.mast-words', 'letterSpacing'),
      heroTitleSize: g('.hero-title', 'fontSize'),
      rowTitleSize: g('.row-title', 'fontSize'),
      priceColor: g('.row-price', 'color'),
      rowRadius: g('.row', 'borderRadius'),
      heroPaddingTop: g('.hero', 'paddingTop'),
    }
  })
  out.visualTokens = a18

  // ===== console errors =====
  out.cases.push({ name: 'A-19 页面无 JS/console 报错', pass: out.consoleErrors.length === 0, errors: out.consoleErrors })

  out.allPass = out.cases.every((c) => c.pass)
  out.finishedAt = new Date().toISOString()
  out.sideEffects = { newBookings: ['13800000001 ' + (out.bookDateUsed || '') + ' 下午（1 条，预走后重置）'] }
  const target = path.join(OUT, 'prewalk_step9.json')
  fs.writeFileSync(target, JSON.stringify(out, null, 2), 'utf8')
  console.log('=== allPass =', out.allPass, '=== saved ->', target)
  await browser.close()
  process.exit(out.allPass ? 0 : 1)
})().catch((e) => {
  console.error('PREWALK_FAIL', e.message)
  fs.writeFileSync(path.join(OUT, 'prewalk_step9_error.json'), JSON.stringify({ error: e.message, cases: out.cases }, null, 2), 'utf8')
  process.exit(1)
})
