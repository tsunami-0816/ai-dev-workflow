// 批次 2：三版首页截图 + 结构断言（375 宽，真实 H5 + 真实接口数据）
// 结果：evidence/design_variants/{A,B,C}.png + variants.json
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require('puppeteer-core')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const OUTDIR = path.resolve('evidence/design_variants')

const versions = [
  {
    key: 'A',
    name: '账本单列',
    tap: '.row',
    expect: () => ({
      rows: document.querySelectorAll('.row').length,
      heroPrice: document.querySelector('.hero-price')?.textContent?.trim() || '',
      photoBleedRight: !!document.querySelector('.hero-photo'),
      listPrices: [...document.querySelectorAll('.row-price')].map((n) => n.textContent.trim())
    })
  },
  {
    key: 'B',
    name: '接触印样栅格',
    tap: '.cs-cell',
    expect: () => ({
      cells: document.querySelectorAll('.cs-cell').length,
      plate: !!document.querySelector('.cs-plate'),
      platePrice: document.querySelector('.cs-plate-price')?.textContent?.trim() || '',
      gridPrice: [...document.querySelectorAll('.cs-price')].map((n) => n.textContent.trim())
    })
  },
  {
    key: 'C',
    name: '票根堆叠',
    tap: '.tk-ticket',
    expect: () => ({
      tickets: document.querySelectorAll('.tk-ticket').length,
      hero: !!document.querySelector('.tk-hero'),
      heroPrice: document.querySelector('.tk-hero-price')?.textContent?.trim() || '',
      ticketPrices: [...document.querySelectorAll('.tk-price')].map((n) => n.textContent.trim())
    })
  }
]

;(async () => {
  fs.mkdirSync(OUTDIR, { recursive: true })
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const out = []

  for (const v of versions) {
    const page = await browser.newPage()
    await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2 })
    const url = `${BASE}/#/pages/index/index?v=${v.key}`
    let status = 'ok'
    let data = {}
    try {
      const resp = await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 })
      await new Promise((r) => setTimeout(r, 1600))
      data = await page.evaluate(
        (fnSource) => {
          const fn = eval('(' + fnSource + ')')
          const metrics = fn()
          const de = document.documentElement
          metrics.httpStatus = 0
          metrics.scrollWidth = de.scrollWidth
          metrics.clientWidth = de.clientWidth
          metrics.docHeight = de.scrollHeight
          metrics.horizontalOverflow = de.scrollWidth > de.clientWidth
          // 截图专用：隐藏固定 tabBar，避免全页截图里压在首屏底部
          const tab = document.querySelector('.uni-tabbar')
          if (tab) tab.style.display = 'none'
          return metrics
        },
        v.expect.toString()
      )
      data.httpStatus = resp ? resp.status() : 0
      const file = path.join(OUTDIR, `${v.key}.png`)
      await page.screenshot({ path: file, fullPage: true })
      data.screenshot = file

      // 交互：点第一行/第一格/第一张票根，必须真的进详情页
      const first = await page.$(v.tap)
      if (first) {
        await first.click()
        await new Promise((r) => setTimeout(r, 900))
        data.tapHash = await page.evaluate(() => window.location.hash)
        data.tapNavigates = data.tapHash.includes('/pages/package/detail')
      }

      // C10：414 宽同样不得横向溢出
      const p2 = await browser.newPage()
      await p2.setViewport({ width: 414, height: 896, deviceScaleFactor: 1 })
      await p2.goto(url, { waitUntil: 'networkidle0', timeout: 30000 })
      await new Promise((r) => setTimeout(r, 1200))
      data.w414 = await p2.evaluate(() => {
        const de = document.documentElement
        return { scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, docHeight: de.scrollHeight, horizontalOverflow: de.scrollWidth > de.clientWidth }
      })
      await p2.close()
    } catch (e) {
      status = 'fail'
      data = { error: e.message }
    }
    out.push({ version: v.key, layout: v.name, url, status, ...data })
    await page.close()
  }

  fs.writeFileSync(path.resolve('evidence/design_variants/variants.json'), JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
})().catch((e) => {
  console.error('VARIANTS_FAIL', e.message)
  process.exit(1)
})
