// D-26 H5 隐私页走查：协议页可渲染 + 「我的」页入口可跳转
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require('puppeteer-core')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const OUT = path.resolve('evidence/privacy_h5.png')
const JSON_OUT = path.resolve('evidence/privacy_walkthrough.json')

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  })
  try {
    const page = await browser.newPage()
    await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2 })

    await page.goto(BASE + '/#/pages/privacy/index', { waitUntil: 'networkidle0', timeout: 30000 })
    await new Promise((r) => setTimeout(r, 600))
    const privacy = await page.evaluate(() => ({
      title: document.querySelector('.ub-title')?.textContent?.trim() || '',
      sections: document.querySelectorAll('.section').length,
      bodyLen: document.body.innerText.length,
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      scrollX: window.scrollX,
      pageLeft: document.querySelector('.ub-page')?.getBoundingClientRect().left,
      titleLeft: document.querySelector('.ub-title')?.getBoundingClientRect().left
    }))
    await page.evaluate(() => window.scrollTo(0, 0))
    await new Promise((r) => setTimeout(r, 200))
    await page.screenshot({ path: OUT, fullPage: true })

    await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
    await new Promise((r) => setTimeout(r, 400))
    const hasLink = await page.evaluate(() => !!document.querySelector('.legal-link'))
    if (hasLink) {
      await page.click('.legal-link')
      await new Promise((r) => setTimeout(r, 500))
    }
    const hash = await page.evaluate(() => location.hash)
    const result = { privacy, hasLink, hash, navigates: hash.includes('/pages/privacy/index'), screenshot: OUT }
    fs.writeFileSync(JSON_OUT, JSON.stringify(result, null, 2))
    console.log(JSON.stringify(result, null, 2))
  } finally {
    await browser.close()
  }
})().catch((e) => {
  console.error(e)
  process.exit(1)
})
