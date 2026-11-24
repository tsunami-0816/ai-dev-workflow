// 第 6 步阶段二补充预跑：S4 展开/收起、S5 字段级校验、S8 未登录「我的」、S10 隐私页
// 用法：node 06_冒烟/scripts/e2e_stage2_remainder.cjs   → 06_冒烟/evidence/step6_stage2_probe.json
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const out = { cases: [] }
const consoleErrors = []

function rec(name, pass, data) {
  out.cases.push({ name, pass, ...data })
  console.log(pass ? 'PASS' : 'FAIL', name, JSON.stringify(data))
}

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message))
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push('console: ' + m.text())
  })

  // —— S4 详情页：展开/收起 + 预约栏存在 ——
  await page.goto(BASE + '/#/pages/package/detail?id=1', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)
  const before = await page.evaluate(() => {
    const fold = document.querySelector('.fold')
    const summary = document.querySelector('.summary')
    const body = document.querySelector('.section') || document.querySelector('uni-page-body')
    const cta = document.querySelector('.btn-primary')
    const ctaRect = cta ? cta.getBoundingClientRect() : null
    const bodyRect = body ? body.getBoundingClientRect() : null
    const overlap =
      ctaRect && bodyRect
        ? Math.max(0, Math.min(ctaRect.top, bodyRect.bottom) - Math.max(ctaRect.bottom, bodyRect.top))
        : null
    return {
      title: document.querySelector('.title')?.textContent?.trim() || '',
      price: document.querySelector('.price')?.textContent?.trim() || '',
      tags: [...document.querySelectorAll('.tag')].map((n) => n.textContent.trim()),
      summaryLen: summary ? summary.textContent.trim().length : 0,
      foldText: fold ? fold.textContent.trim() : '',
      hasFold: !!fold,
      ctaText: cta ? cta.textContent.trim() : '',
      ctaBottom: ctaRect ? Math.round(ctaRect.bottom) : null,
      viewportH: window.innerHeight,
      // 说明区与预约栏纵向重叠像素（0=未遮挡）
      overlapPx: overlap
    }
  })
  let afterFold = { foldText: '', bodyLen: 0 }
  if (before.hasFold) {
    await page.click('.fold')
    await sleep(700)
    afterFold = await page.evaluate(() => ({
      foldText: document.querySelector('.fold')?.textContent?.trim() || '',
      bodyLen: (document.querySelector('uni-page-body')?.innerText || '').length
    }))
  }
  rec(
    'S4 详情页内容',
    before.title === '城市轻写真' &&
      before.price.indexOf('399') >= 0 &&
      before.tags.length === 3 &&
      before.ctaText.indexOf('立即预约') >= 0 &&
      before.overlapPx === 0,
    {
      before,
      // 折叠分支可达性：needFold = summary.length > 52（detail.vue:57）；种子数据 29–34 字 → 不可达
      foldBranchReachable: before.summaryLen > 52,
      foldBranchNote: before.summaryLen > 52 ? '说明超 52 字，应出现折叠按钮' : '说明仅 ' + before.summaryLen + ' 字（≤52），按设计不出现折叠按钮',
      afterFold,
      judged: ['标题=城市轻写真', '价格含 399', '标签=3', '预约栏含「立即预约」', '说明区与预约栏纵向重叠=0']
    }
  )
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_s4_detail_expanded.png') })

  // —— S5 表单字段级校验（未登录也应先校验字段，不发请求） ——
  let bookingPosts = 0
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().indexOf('/api/bookings') >= 0) bookingPosts += 1
  })
  await page.goto(
    BASE + '/#/pages/booking/form?packageId=1&title=' + encodeURIComponent('城市轻写真') + '&price=399',
    { waitUntil: 'networkidle0', timeout: 30000 }
  )
  await sleep(2000)
  await page.evaluate(() => localStorage.removeItem('ub_token'))
  await page.click('.submit')
  await sleep(900)
  const emptyErrs = await page.evaluate(() => ({
    errs: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()),
    url: location.href
  }))
  rec(
    'S5-a 空表单提交',
    emptyErrs.errs.length === 3 &&
      emptyErrs.errs.includes('请选择日期') &&
      emptyErrs.errs.includes('请选择时段') &&
      emptyErrs.errs.includes('请输入 11 位手机号') &&
      bookingPosts === 0,
    { ...emptyErrs, bookingPosts }
  )

  // 先补齐日期 + 时段，再只留非法手机号 → 仅手机号一条红字（用真实键入，确保 uni-input 的 v-model 生效）
  await page.click('.field .control')
  await sleep(700)
  const hasConfirm = await page.evaluate(() => !!document.querySelector('.uni-picker-action-confirm'))
  if (hasConfirm) await page.click('.uni-picker-action-confirm')
  await sleep(600)
  const slotEls = await page.$$('.slot')
  if (slotEls.length >= 2) await slotEls[1].click()
  await sleep(300)
  await page.click('input.uni-input-input')
  await sleep(300)
  await page.type('input.uni-input-input', '12345', { delay: 60 })
  await sleep(300)
  const typedPhone = await page.evaluate(() => ({
    value: document.querySelector('input.uni-input-input')?.value || '',
    dateValue: document.querySelector('.field .control')?.textContent?.trim() || '',
    activeSlot: document.querySelector('.slot.active')?.textContent?.trim() || ''
  }))
  await page.click('.submit')
  await sleep(900)
  const phoneErrs = await page.evaluate(() => ({
    errs: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim())
  }))
  rec(
    'S5-b 非法手机号',
    phoneErrs.errs.length === 1 && phoneErrs.errs[0] === '请输入 11 位手机号',
    { ...phoneErrs, typedPhone, bookingPosts }
  )
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_s5_field_errors.png') })

  // —— S8 未登录进「我的」 ——
  await page.evaluate(() => localStorage.clear())
  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)
  const myOut = await page.evaluate(() => ({
    url: location.href,
    hasState: !!document.querySelector('.state'),
    loginBtn: document.querySelector('.btn-primary')?.textContent?.trim() || '',
    bookingRows: document.querySelectorAll('.booking').length,
    bodyText: (document.querySelector('uni-page-body')?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 80)
  }))
  rec(
    'S8 未登录「我的」',
    myOut.hasState && myOut.bookingRows === 0 && myOut.url.indexOf('/pages/my/index') >= 0 && myOut.loginBtn.indexOf('去登录') >= 0,
    myOut
  )
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_s8_my_loggedout.png') })

  // —— S10 隐私协议页 ——
  await page.goto(BASE + '/#/pages/privacy/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)
  const priv = await page.evaluate(() => ({
    url: location.href,
    textLen: (document.querySelector('uni-page-body')?.innerText || '').trim().length,
    head: (document.querySelector('uni-page-body')?.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60)
  }))
  rec('S10 隐私协议页', priv.textLen > 200 && priv.url.indexOf('/pages/privacy/index') >= 0, priv)
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_s10_privacy.png') })

  // —— S2 下拉刷新：代码级证据（H5 无真实手指手势，手感留给用户） ——
  const s2 = {
    pagesJsonEnablePullDownRefresh: fs
      .readFileSync(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'src', 'pages.json'), 'utf8')
      .includes('"enablePullDownRefresh": true'),
    indexHasHandler: fs
      .readFileSync(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'src', 'pages', 'index', 'index.vue'), 'utf8')
      .includes('onPullDownRefresh'),
    myHasHandler: fs
      .readFileSync(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'src', 'pages', 'my', 'index.vue'), 'utf8')
      .includes('onPullDownRefresh'),
    note: 'H5 下拉手势由用户手感判定；本项只证代码挂接'
  }
  rec('S2 下拉刷新（代码级）', s2.pagesJsonEnablePullDownRefresh && s2.indexHasHandler && s2.myHasHandler, s2)

  out.consoleErrors = consoleErrors
  out.allPass = out.cases.every((c) => c.pass)
  const target = path.join(__dirname, '..', 'evidence', 'step6_stage2_probe.json')
  fs.writeFileSync(target, JSON.stringify(out, null, 2), 'utf8')
  console.log('=== allPass =', out.allPass, '=== saved ->', target)
  await browser.close()
  process.exit(out.allPass ? 0 : 1)
})().catch((e) => {
  console.error('STAGE2_FAIL', e.message)
  process.exit(1)
})
