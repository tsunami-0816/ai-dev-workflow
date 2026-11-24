// Q-020：我的列表滚到底分页（需 demo 账号下 >20 单，由 pytest 先造数）
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')
const path = require('node:path')

const EDGE = process.env.EDGE_BIN || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = process.env.H5_URL || 'http://127.0.0.1:5186'
const EXPECT = Number(process.env.EXPECT_MIN || 21)
const OUT = path.resolve(__dirname, '../../evidence/ui_my_pagination.json')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })
  const calls = []
  page.on('request', (r) => {
    if (r.url().indexOf('/api/bookings') >= 0) calls.push(r.url())
  })

  await page.goto(BASE + '/#/pages/login/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1500)
  const filled = await page.evaluate(() => {
    const setVal = (el, v) => {
      el.focus(); el.value = v
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

  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2500)
  const firstCount = await page.evaluate(() => document.querySelectorAll('.booking').length)

  for (let i = 0; i < 4; i += 1) {
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await sleep(1000)
  }
  const afterCount = await page.evaluate(() => document.querySelectorAll('.booking').length)
  const pages = [...new Set(calls.map((u) => (u.match(/page=(\d+)/) || [])[1]).filter(Boolean))]
  await page.screenshot({ path: path.resolve(__dirname, '../../evidence/ui_my_pagination.png') })

  const out = { expectMin: EXPECT, firstCount, afterCount, pages, requests: calls.length,
    pass: afterCount >= EXPECT && pages.length >= 2 }
  fs.mkdirSync(path.dirname(OUT), { recursive: true })
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out))
  await browser.close()
  process.exit(out.pass ? 0 : 1)
})().catch((e) => { console.error('UI_MY_PAGINATION_FAIL', e.message); process.exit(1) })
