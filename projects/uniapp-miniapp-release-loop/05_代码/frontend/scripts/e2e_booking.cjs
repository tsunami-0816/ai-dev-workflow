// 5B E2E：H5 登录 → 预约表单提交 → 我的列表（真实后端 8092）
const puppeteer = require('puppeteer-core')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const out = { steps: [] }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  page.on('console', (m) => console.log('[console]', m.type(), m.text()))
  page.on('response', (r) => {
    const u = r.url()
    if (u.indexOf('/api/') >= 0) console.log('[api]', r.status(), r.request().method(), u)
  })
  page.on('requestfailed', (r) => {
    if (r.url().indexOf('/api/') >= 0) console.log('[api-fail]', r.url(), r.failure() && r.failure().errorText)
  })
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })

  // 1) 登录
  await page.goto(BASE + '/#/pages/login/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)
  // 用原生 input 事件驱动 uni-input 的 v-model（type 在 uni-input 上不稳定）
  const filled = await page.evaluate(() => {
    const setVal = (el, v) => {
      el.focus()
      el.value = v
      el.dispatchEvent(new Event('input', { bubbles: true }))
      el.dispatchEvent(new Event('change', { bubbles: true }))
    }
    const inputs = [...document.querySelectorAll('input.uni-input-input')]
    if (inputs.length < 2) return { ok: false, count: inputs.length }
    setVal(inputs[0], 'demo')
    setVal(inputs[1], 'welcome1')
    return { ok: true, values: inputs.map((el) => el.value) }
  })
  if (!filled.ok) throw new Error('login inputs not found: ' + filled.count)
  await page.click('.btn-primary')
  await sleep(2500)

  const afterLogin = await page.evaluate(() => ({
    url: location.href,
    storageKeys: Object.keys(localStorage),
    token: localStorage.getItem('ub_token') || '',
    meName: document.querySelector('.me-name')?.textContent?.trim() || '',
    err: document.querySelector('.err')?.textContent?.trim() || ''
  }))
  out.steps.push({ step: 'login', ...afterLogin, tokenLen: afterLogin.token.length })
  await page.screenshot({ path: 'evidence/e2e_1_after_login.png' })

  // 2) 预约表单
  await page.goto(
    BASE + '/#/pages/booking/form?packageId=1&title=' + encodeURIComponent('城市轻写真') + '&price=399',
    { waitUntil: 'networkidle0', timeout: 30000 }
  )
  await sleep(2000)

  // 日期：点触发区，弹层确认
  await page.click('.field .control')
  await sleep(800)
  const pickerInfo = await page.evaluate(() => {
    const confirm = document.querySelector('.uni-picker-action-confirm')
    const picker = document.querySelector('.uni-picker-container, .uni-picker')
    return { hasPicker: !!picker, hasConfirm: !!confirm }
  })
  if (pickerInfo.hasConfirm) {
    await page.click('.uni-picker-action-confirm')
    await sleep(600)
  }
  const dateValue = await page.evaluate(() => document.querySelector('.field .control')?.textContent?.trim() || '')

  // 时段：下午
  const slots = await page.$$('.slot')
  if (slots.length >= 2) await slots[1].click()

  // 手机号：JS 设值 + 原生 input 事件
  const contactProbe = await page.evaluate(() => {
    const all = [...document.querySelectorAll('input.uni-input-input')]
    const el = all.find((e) => (e.type || 'text') !== 'password' && (e.type || '') !== 'date') || all[0]
    if (!el) return { ok: false, count: all.length }
    el.focus()
    el.value = '13800000001'
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
    return { ok: true, count: all.length, value: el.value, types: all.map((e) => e.type || 'text') }
  })

  await page.screenshot({ path: 'evidence/e2e_2_form_filled.png' })
  await page.click('.submit')
  await sleep(4500)

  const submitResult = await page.evaluate(() => ({
    doneNo: document.querySelector('.done-no')?.textContent?.trim() || '',
    doneNote: document.querySelector('.done-note')?.textContent?.trim() || '',
    err: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()).join(' | ')
  }))
  out.steps.push({
    step: 'submit',
    picker: pickerInfo,
    dateValue,
    contactProbe,
    ...submitResult
  })
  await page.screenshot({ path: 'evidence/e2e_3_submitted.png' })

  // 3) 我的列表
  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2500)
  const myList = await page.evaluate(() => ({
    count: document.querySelectorAll('.booking').length,
    first: document.querySelector('.booking')?.innerText?.replace(/\s+/g, ' ').trim() || '',
    loggedIn: !!document.querySelector('.me-name')
  }))
  out.steps.push({ step: 'myList', ...myList })
  await page.screenshot({ path: 'evidence/e2e_4_my.png' })

  require('node:fs').writeFileSync('evidence/e2e_result.json', JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
})().catch((e) => {
  console.error('E2E_FAIL', e.message)
  process.exit(1)
})
