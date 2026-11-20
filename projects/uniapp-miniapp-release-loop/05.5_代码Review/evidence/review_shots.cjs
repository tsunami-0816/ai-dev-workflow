// 5.5 独立 Review 临时证据脚本（不进产品代码）：首页 + 详情页截图 + 溢出/分页实测
const path = require('node:path')
const fs = require('node:fs')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const OUT = __dirname

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })

  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })
  await page.goto('http://127.0.0.1:5186/', { waitUntil: 'networkidle0', timeout: 40000 })
  await sleep(3000)

  const home = await page.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    scrollHeight: document.documentElement.scrollHeight,
    title: (document.querySelector('.hero-title') || {}).textContent || '',
    price: (document.querySelector('.hero-price') || {}).textContent || ''
  }))
  await page.screenshot({ path: path.join(OUT, 'review_home_390.png'), fullPage: true })

  // 滚到底：验证是否触发「加载更多」（不点任何按钮，只滚动）
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await sleep(1500)
  const afterScroll = await page.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    scrollHeight: document.documentElement.scrollHeight
  }))

  // 进详情页
  await page.evaluate(() => {
    const row = document.querySelector('.row')
    if (row) row.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
  await sleep(2500)
  const detail = await page.evaluate(() => ({
    url: location.href,
    title: (document.querySelector('.title') || {}).textContent || '',
    price: (document.querySelector('.price') || {}).textContent || '',
    tags: Array.from(document.querySelectorAll('.tag')).map((t) => t.textContent),
    photoNote: (document.querySelector('.photo-note') || {}).textContent || '',
    fold: Boolean(document.querySelector('.fold')),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth
  }))
  await page.screenshot({ path: path.join(OUT, 'review_detail_390.png'), fullPage: true })

  // 375 宽复测（D-30）
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  await page.goto('http://127.0.0.1:5186/', { waitUntil: 'networkidle0', timeout: 40000 })
  await sleep(2500)
  const w375 = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth
  }))
  await page.screenshot({ path: path.join(OUT, 'review_home_375.png'), fullPage: true })

  fs.writeFileSync(
    path.join(OUT, 'review_shots.json'),
    JSON.stringify({ home, afterScroll, detail, w375 }, null, 2),
    'utf8'
  )
  console.log(JSON.stringify({ home, afterScroll, detail, w375 }, null, 2))
  await browser.close()
})().catch((e) => {
  console.error('REVIEW_SHOTS_FAIL', e.message)
  process.exit(1)
})
