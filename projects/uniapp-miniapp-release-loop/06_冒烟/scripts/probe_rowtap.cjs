// 第 6 步：点清单行 → 价格跳动 300ms → 进详情（Q-021 回归）
// 用法：node 06_冒烟/scripts/probe_rowtap.cjs  → 06_冒烟/evidence/step6_rowtap.json
const fs = require('fs')
const path = require('path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(3000)

  const before = await page.evaluate(() => ({
    price: document.querySelector('.row .row-price')?.textContent?.trim() || '',
    rows: document.querySelectorAll('.row').length,
    url: location.href
  }))

  await page.click('.row .row-line')
  // 抓跳动中间值（约 150ms 处）
  await sleep(150)
  const mid = await page.evaluate(() => document.querySelector('.row .row-price')?.textContent?.trim() || '')
  await sleep(600)
  const after = await page.evaluate(() => ({
    url: location.href,
    hasBookBtn: !!document.querySelector('.btn-primary'),
    title: document.querySelector('.ub-title')?.textContent?.trim() || '',
    price: document.querySelector('.hero-price')?.textContent?.trim() || ''
  }))

  const result = {
    before, midTickPrice: mid, after,
    tickChanged: before.price !== mid,
    navigated: after.url.indexOf('pages/package/detail') >= 0,
    pass: before.rows > 0 && after.url.indexOf('pages/package/detail') >= 0 && after.hasBookBtn
  }
  fs.writeFileSync(path.join(__dirname, '..', 'evidence', 'step6_rowtap.json'), JSON.stringify(result, null, 2), 'utf8')
  console.log(JSON.stringify(result, null, 2))
  await browser.close()
  process.exit(result.pass ? 0 : 1)
})().catch((e) => { console.error(e); process.exit(1) })
