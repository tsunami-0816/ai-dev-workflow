// 5B E2E · Q-008/D-15：连点 5 次提交，只允许 1 次 POST /api/bookings（真实后端 8092）
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')
const path = require('node:path')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const EV = path.resolve(__dirname, '../../../05.5_代码Review/evidence')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })

  const posts = []
  page.on('request', (r) => {
    if (r.method() === 'POST' && r.url().indexOf('/api/bookings') >= 0) posts.push(r.url())
  })

  // 1) 登录拿 token
  await page.goto(BASE + '/#/pages/login/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1500)
  const filled = await page.evaluate(() => {
    const setVal = (el, v) => {
      el.focus()
      el.value = v
      el.dispatchEvent(new Event('input', { bubbles: true }))
      el.dispatchEvent(new Event('change', { bubbles: true }))
    }
    const inputs = [...document.querySelectorAll('input.uni-input-input')]
    if (inputs.length < 2) return false
    setVal(inputs[0], 'demo')
    setVal(inputs[1], 'welcome1')
    return true
  })
  if (!filled) throw new Error('login inputs not found')
  await page.click('.btn-primary')
  await sleep(2200)
  const token = await page.evaluate(() => localStorage.getItem('ub_token') || '')
  if (!token) throw new Error('login failed: no token')

  // 2) 表单：选日期(默认今天) + 上午 + 手机号
  await page.goto(
    BASE + '/#/pages/booking/form?packageId=2&title=' + encodeURIComponent('复古胶片') + '&price=499',
    { waitUntil: 'networkidle0', timeout: 30000 }
  )
  await sleep(1600)
  await page.click('.field .control')
  await sleep(700)
  const hasConfirm = await page.evaluate(() => !!document.querySelector('.uni-picker-action-confirm'))
  if (hasConfirm) {
    await page.click('.uni-picker-action-confirm')
    await sleep(500)
  }
  const slotEls = await page.$$('.slot')
  if (slotEls.length >= 1) await slotEls[0].click()
  await page.evaluate(() => {
    const all = [...document.querySelectorAll('input.uni-input-input')]
    const el = all.find((e) => (e.type || 'text') !== 'password') || all[0]
    el.focus()
    el.value = '13800000005'
    el.dispatchEvent(new Event('input', { bubbles: true }))
    el.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await page.screenshot({ path: path.join(EV, 'e2e_click5_form.png') })

  // 3) 连点 5 次（不等动画，模拟真实手抖）
  for (let i = 0; i < 5; i += 1) {
    await page.click('.submit').catch(() => {})
  }
  await sleep(4500)

  const result = await page.evaluate(() => ({
    doneNo: document.querySelector('.done-no')?.textContent?.trim() || '',
    doneNote: document.querySelector('.done-note')?.textContent?.trim() || '',
    err: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()).join(' | '),
    busyText: document.querySelector('.submit')?.textContent?.trim() || ''
  }))
  await page.screenshot({ path: path.join(EV, 'e2e_click5_result.png') })

  const out = { clicks: 5, postCount: posts.length, ...result, pass: posts.length === 1 && !!result.doneNo }
  fs.writeFileSync(path.join(EV, 'e2e_click5.json'), JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
  process.exit(out.pass ? 0 : 1)
})().catch((e) => {
  console.error('E2E_CLICK5_FAIL', e.message)
  process.exit(1)
})
