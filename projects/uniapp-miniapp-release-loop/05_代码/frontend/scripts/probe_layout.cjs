// 临时诊断脚本（不进交付）：测量 .row-price 的真实布局与计算样式
const puppeteer = require('puppeteer-core')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 900, deviceScaleFactor: 1 })
  await page.goto('http://127.0.0.1:5186/', { waitUntil: 'networkidle0', timeout: 30000 })
  await new Promise((r) => setTimeout(r, 4000))

  const info = await page.evaluate(() => {
    const pick = (sel) => {
      const e = document.querySelector(sel)
      if (!e) return { sel, missing: true }
      const r = e.getBoundingClientRect()
      const c = getComputedStyle(e)
      return {
        sel,
        text: (e.textContent || '').trim().slice(0, 20),
        rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        display: c.display,
        position: c.position,
        color: c.color,
        fontSize: c.fontSize,
        visibility: c.visibility,
        opacity: c.opacity,
        overflow: c.overflow,
        zIndex: c.zIndex
      }
    }
    return {
      row: pick('.row'),
      rowMain: pick('.row-main'),
      rowLine: pick('.row-line'),
      rowLead: pick('.row-lead'),
      price: pick('.row-price'),
      priceSpan: pick('.row-price span'),
      rowNo: pick('.row-no')
    }
  })

  console.log(JSON.stringify(info, null, 2))
  await page.screenshot({ path: 'evidence/puppeteer_home.png', fullPage: false })
  await browser.close()
})().catch((e) => {
  console.error('PROBE_FAIL', e.message)
  process.exit(1)
})
