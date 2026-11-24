// Q-025：详情页长说明（>52 字）展开/收起分支（临时套餐由 pytest 造，用完删）
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')
const path = require('node:path')

const EDGE = process.env.EDGE_BIN || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = process.env.H5_URL || 'http://127.0.0.1:5186'
const PKG = process.env.PKG_ID || '9001'
const OUT = path.resolve(__dirname, '../../evidence/ui_fold.json')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })
  await page.goto(`${BASE}/#/pages/package/detail?id=${PKG}`, { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)

  const before = await page.evaluate(() => {
    const fold = document.querySelector('.fold')
    const summary = document.querySelector('.summary')
    return {
      foldVisible: !!fold,
      foldText: fold ? fold.textContent.trim() : '',
      clamped: summary ? summary.classList.contains('clamp') : null,
      summaryLen: summary ? summary.textContent.trim().length : 0,
      title: document.querySelector('.title')?.textContent?.trim() || ''
    }
  })

  let after = { foldText: '', clamped: null }
  if (before.foldVisible) {
    await page.click('.fold')
    await sleep(500)
    after = await page.evaluate(() => {
      const fold = document.querySelector('.fold')
      const summary = document.querySelector('.summary')
      return { foldText: fold ? fold.textContent.trim() : '',
        clamped: summary ? summary.classList.contains('clamp') : null,
        text: summary ? summary.textContent.trim() : '' }
    })
  }
  await page.screenshot({ path: path.resolve(__dirname, '../../evidence/ui_fold.png') })

  const out = { pkg: PKG, before, after,
    pass: before.foldVisible && before.foldText === '展开' && before.clamped === true &&
          after.foldText === '收起' && after.clamped === false }
  fs.mkdirSync(path.dirname(OUT), { recursive: true })
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out))
  await browser.close()
  process.exit(out.pass ? 0 : 1)
})().catch((e) => { console.error('UI_FOLD_FAIL', e.message); process.exit(1) })
