// 5B E2E · Q-007/D-10：首页滚到底继续加载（size 可覆盖，用于 4 条数据也能演示分页）
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

  const calls = []
  page.on('request', (r) => {
    const u = r.url()
    if (u.indexOf('/api/packages') >= 0) calls.push(u)
  })

  await page.goto(BASE + '/#/pages/index/index?v=A&size=2', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1800)
  const firstLoadCalls = calls.length

  const rowsOf = () => page.evaluate(() => ({
    rows: document.querySelectorAll('.row').length,
    hero: document.querySelector('.hero-title')?.textContent?.trim() || '',
    scrollHeight: document.documentElement.scrollHeight,
    clientHeight: document.documentElement.clientHeight
  }))

  const before = await rowsOf()

  // 滚到底两次，触发 onReachBottom（uni H5 用页面滚动距离判定）
  for (let i = 0; i < 3; i += 1) {
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await sleep(900)
  }
  const after = await rowsOf()
  await page.screenshot({ path: path.join(EV, 'e2e_pagination_bottom.png') })

  const out = {
    size: 2,
    firstLoadCalls,
    beforeRows: before.rows,
    afterRows: after.rows,
    requests: calls.map((u) => u.replace('http://127.0.0.1:8092/api/packages?', '')),
    distinctPages: [...new Set(calls.map((u) => (u.match(/page=(\d+)/) || [])[1]))],
    pass: before.rows === 1 && after.rows === 3 && new Set(calls.map((u) => (u.match(/page=(\d+)/) || [])[1])).size === 2
  }
  fs.writeFileSync(path.join(EV, 'e2e_pagination.json'), JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
  process.exit(out.pass ? 0 : 1)
})().catch((e) => {
  console.error('E2E_PAGINATION_FAIL', e.message)
  process.exit(1)
})
