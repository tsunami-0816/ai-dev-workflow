// 第 6 步阶段一：H5 布局/语义/动效观测（一次性诊断脚本，不入交付）
// 用法：node 06_冒烟/scripts/probe_step6_ui.cjs   → 输出 06_冒烟/evidence/step6_ui_probe.json
const fs = require('fs')
const path = require('path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const URL = 'http://127.0.0.1:5186/'
const WIDTHS = [375, 390, 414, 1440]

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const out = {}
  for (const w of WIDTHS) {
    const page = await browser.newPage()
    await page.setViewport({ width: w, height: w > 1000 ? 900 : 812, deviceScaleFactor: 1 })
    await page.goto(URL, { waitUntil: 'networkidle0', timeout: 30000 })
    await new Promise((r) => setTimeout(r, 3000))
    out[w] = await page.evaluate(() => {
      const de = document.documentElement
      const body = document.body
      // 内容页容器：uni 的 page 根节点
      const uniPage = document.querySelector('uni-page-body') || body
      const children = Array.from(uniPage.children).filter((el) => el.getBoundingClientRect().height > 0)
      const first = children[0]
      const rect = first ? first.getBoundingClientRect() : null
      return {
        viewport: window.innerWidth,
        scrollWidth: de.scrollWidth,
        clientWidth: de.clientWidth,
        horizontalOverflow: de.scrollWidth - de.clientWidth,
        contentLeft: rect ? Math.round(rect.x) : null,
        contentRight: rect ? Math.round(rect.right) : null,
        marginLeft: rect ? Math.round(rect.x) : null,
        marginRight: rect ? Math.round(window.innerWidth - rect.right) : null,
        h1Count: document.querySelectorAll('h1').length,
        buttonCountFirstScreen: Array.from(document.querySelectorAll('button')).filter((b) => {
          const r = b.getBoundingClientRect()
          return r.top < window.innerHeight && r.height > 0
        }).length,
        runningAnimations: document.getAnimations().map((a) => (a.animationName || a.transitionProperty || 'unknown')),
        cssVarGutter: getComputedStyle(de).getPropertyValue('--gutter').trim() || null
      }
    })
    await page.screenshot({ path: path.join(__dirname, '..', 'evidence', `step6_home_${w}.png`) })
    await page.close()
  }
  await browser.close()
  const target = path.join(__dirname, '..', 'evidence', 'step6_ui_probe.json')
  fs.writeFileSync(target, JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  console.log('saved ->', target)
})().catch((e) => { console.error(e); process.exit(1) })
