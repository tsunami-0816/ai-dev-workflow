// Allure 报告首页截图（报告由 python -m http.server 提供，避免 file:// XHR 限制）
const puppeteer = require('puppeteer-core')
const path = require('node:path')

const EDGE = process.env.EDGE_BIN || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const URL = process.env.ALLURE_URL || 'http://127.0.0.1:8899/'
const OUT = path.resolve(__dirname, '../../evidence/allure_overview.png')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new',
    args: ['--no-first-run', '--disable-extensions'] })
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 })
  await page.goto(URL, { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1200)
  const title = await page.title()
  const stats = await page.evaluate(() => document.body.innerText.slice(0, 500))
  await page.screenshot({ path: OUT })
  console.log(JSON.stringify({ title, stats: stats.replace(/\s+/g, ' ').slice(0, 240),
    out: OUT }))
  await browser.close()
})().catch((e) => { console.error('SCREENSHOT_FAIL', e.message); process.exit(1) })
