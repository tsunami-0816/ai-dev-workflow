// 5.5 Review 证据：定位详情页横向溢出的具体元素
const path = require('node:path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'

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
  await page.goto('http://127.0.0.1:5186/#/pages/package/detail?id=3', { waitUntil: 'networkidle0', timeout: 40000 })
  await sleep(2500)

  const info = await page.evaluate(() => {
    const vw = document.documentElement.clientWidth
    const out = []
    document.querySelectorAll('*').forEach((el) => {
      const r = el.getBoundingClientRect()
      if (r.width > 0 && (r.right > vw + 0.5 || r.left < -0.5)) {
        out.push({
          tag: el.tagName.toLowerCase(),
          cls: el.className && String(el.className).slice(0, 60),
          left: Math.round(r.left),
          right: Math.round(r.right),
          width: Math.round(r.width),
          text: (el.textContent || '').trim().slice(0, 24)
        })
      }
    })
    return { vw, scrollWidth: document.documentElement.scrollWidth, offenders: out.slice(0, 20) }
  })
  console.log(JSON.stringify(info, null, 2))
  await page.screenshot({ path: path.join(__dirname, 'review_detail3_390.png'), fullPage: true })
  await browser.close()
})().catch((e) => {
  console.error('PROBE_FAIL', e.message)
  process.exit(1)
})
