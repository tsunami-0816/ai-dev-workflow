// 第 9 步视觉验收①：按 step02 §12 设计方向逐项读取实测值，产出对照表
const path = require('node:path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))
const fs = require('node:fs')
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const OUT = path.join(__dirname, '..', 'evidence')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new', args: ['--no-first-run'] })
  const page = await browser.newPage()
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2200)

  const tokens = await page.evaluate(() => {
    const cs = (sel, props) => {
      const el = document.querySelector(sel)
      if (!el) return null
      const s = getComputedStyle(el)
      return Object.fromEntries(props.map((p) => [p, s[p]]))
    }
    const rect = (sel) => {
      const el = document.querySelector(sel)
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left) }
    }
    return {
      ground: cs('.lb-page', ['backgroundColor']),
      paper: cs('.ub-title', ['color']) || cs('.hero-title', ['color']),
      silver: cs('.mast-words', ['color']),
      stamp: cs('.stamp-text', ['color']),
      titleFont: cs('.hero-title', ['fontFamily', 'fontWeight', 'fontSize', 'lineHeight', 'letterSpacing']),
      bodyFont: cs('.hero-sub', ['fontFamily', 'fontWeight', 'fontSize', 'lineHeight']),
      numFont: cs('.row-no', ['fontFamily', 'fontWeight', 'fontSize', 'fontVariantNumeric']),
      btnRadius: cs('.btn-primary', ['borderRadius']),
      rowRadius: cs('.row', ['borderRadius']),
      rowBox: rect('.row'),
      heroBox: rect('.hero'),
      pagePadLeft: cs('.lb-page', ['paddingLeft', 'paddingRight']),
      touchBtn: rect('.btn-primary') || rect('.row'),
      gradients: [...document.querySelectorAll('*')].filter((el) => {
        const b = getComputedStyle(el).backgroundImage
        return b && b.indexOf('gradient') >= 0
      }).length,
      shadowCount: [...document.querySelectorAll('*')].filter((el) => {
        const b = getComputedStyle(el).boxShadow
        return b && b !== 'none'
      }).length,
    }
  })
  tokens.h1 = await page.evaluate(() => document.querySelectorAll('h1').length)
  tokens.motion = await page.evaluate(() => {
    const el = document.querySelector('.ub-rule')
    return el ? getComputedStyle(el).animationName + ' / ' + getComputedStyle(el).animationDuration : 'none'
  })
  tokens.reducedMotionRule = await page.evaluate(() => {
    const sheets = [...document.styleSheets]
    let found = false
    for (const s of sheets) {
      try {
        for (const r of s.cssRules) if (r.conditionText && r.conditionText.includes('prefers-reduced-motion')) found = true
      } catch (e) {}
    }
    return found
  })

  const target = path.join(OUT, 'step9_visual_tokens.json')
  fs.writeFileSync(target, JSON.stringify(tokens, null, 2), 'utf8')
  console.log(JSON.stringify(tokens, null, 2))
  console.log('saved ->', target)
  await browser.close()
})().catch((e) => { console.error('TOKENS_FAIL', e.message); process.exit(1) })
