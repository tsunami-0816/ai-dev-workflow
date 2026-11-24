// 第 6 步：桌面版式（H5 ≥900px）回归探针
// 用法：node 06_冒烟/scripts/probe_desktop_layout.cjs → 06_冒烟/evidence/step6_desktop_probe.json
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const out = { cases: [] }
const consoleErrors = []

function rec(name, pass, data) {
  out.cases.push({ name, pass, ...data })
  console.log(pass ? 'PASS' : 'FAIL', name, JSON.stringify(data))
}

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  page.on('pageerror', (e) => consoleErrors.push('pageerror: ' + e.message))

  const measure = async (url, sel, wait = 2200) => {
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 })
    await sleep(wait)
    return page.evaluate((s) => {
      const el = document.querySelector(s)
      const r = el ? el.getBoundingClientRect() : null
      return {
        exists: !!el,
        left: r ? Math.round(r.left) : null,
        right: r ? Math.round(r.right) : null,
        width: r ? Math.round(r.width) : null,
        viewport: window.innerWidth,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
      }
    }, sel)
  }

  // ---- 375：手机版式必须保持原样（内容贴边、无居中收窄） ----
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 1 })
  const m375 = await measure(BASE + '/#/pages/index/index', '.lb-page')
  const rows375 = await page.evaluate(() => document.querySelectorAll('.row').length)
  rec('375 手机版式未被改动', m375.width === 375 && m375.left === 0 && rows375 === 3 && m375.overflow === 0, { m375, rows375 })

  // ---- 1440：首页居中 1040，首项图位 380 不再出血 ----
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  const idx = await measure(BASE + '/#/pages/index/index', '.lb-page')
  const hero = await page.evaluate(() => {
    const p = document.querySelector('.hero-photo').getBoundingClientRect()
    const c = document.querySelector('.lb-page').getBoundingClientRect()
    return {
      photoLeft: Math.round(p.left), photoRight: Math.round(p.right), photoWidth: Math.round(p.width), photoHeight: Math.round(p.height),
      containerRight: Math.round(c.right),
      rowTitleSize: getComputedStyle(document.querySelector('.row-title')).fontSize,
      rowCount: document.querySelectorAll('.row').length
    }
  })
  rec('1440 首页居中 1040 + 图位归位', idx.width >= 1000 && idx.width <= 1045 && Math.abs(idx.left - (1440 - idx.width) / 2) <= 2 && hero.photoWidth === 380 && hero.photoRight <= idx.right + 1 && hero.rowTitleSize === '22px' && idx.overflow === 0, { idx, hero })
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_desktop_index_1440.png') })

  // ---- 1440 详情：左文右图，预约栏落到右下 ----
  await page.goto(BASE + '/#/pages/package/detail?id=1', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)
  const detail = await page.evaluate(() => {
    const c = document.querySelector('.ub-page').getBoundingClientRect()
    const t = document.querySelector('.title').getBoundingClientRect()
    const p = document.querySelector('.photo').getBoundingClientRect()
    const b = document.querySelector('.bar').getBoundingClientRect()
    const bar = document.querySelector('.bar')
    return {
      container: [Math.round(c.left), Math.round(c.right)],
      titleLeft: Math.round(t.left), titleRight: Math.round(t.right),
      photoLeft: Math.round(p.left), photoWidth: Math.round(p.width), photoHeight: Math.round(p.height),
      photoRatio: +(p.width / p.height).toFixed(2),
      barPosition: getComputedStyle(bar).position,
      barRight: Math.round(b.right), barWidth: Math.round(b.width),
      display: getComputedStyle(document.querySelector('.ub-page')).display,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth
    }
  })
  rec(
    '1440 详情左文右图（4:5）+ 预约栏静态右下',
    detail.display === 'grid' && detail.photoLeft > detail.titleRight && Math.abs(detail.photoRatio - 0.8) <= 0.03 && detail.barPosition === 'static' && detail.barRight <= detail.container[1] && detail.barRight >= detail.container[1] - 60 && detail.barWidth === 360 && detail.overflow === 0,
    detail
  )
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_desktop_detail_1440.png') })

  // ---- 1440 我的：列表双栏（用真实登录 token，避免 401 退成未登录） ----
  const loginRes = await fetch('http://127.0.0.1:8092/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: 'demo', password: 'welcome1' })
  }).then((r) => r.json())
  if (loginRes.code !== 0) throw new Error('probe login failed: ' + JSON.stringify(loginRes))
  await page.evaluate((d) => {
    // uni H5 的 Storage 用 {type,data} 信封，写裸字符串会被 getStorageSync 判成无效值
    const wrap = (type, data) => JSON.stringify({ type, data })
    localStorage.setItem('ub_token', wrap('string', d.token))
    localStorage.setItem('ub_user', wrap('object', { userId: d.userId, nickname: d.nickname || '演示用户A' }))
  }, loginRes.data)
  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2600)
  const my = await page.evaluate(() => {
    const cards = [...document.querySelectorAll('.booking')]
    const xs = [...new Set(cards.map((c) => Math.round(c.getBoundingClientRect().left)))]
    const page = document.querySelector('.ub-page').getBoundingClientRect()
    return { cards: cards.length, columns: xs.length, xs, pageWidth: Math.round(page.width), overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth }
  })
  rec('1440 我的列表双栏', my.columns === 2 && my.pageWidth <= 1045 && my.overflow === 0, my)
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_desktop_my_1440.png') })

  // ---- 1440 表单：收窄 680 ----
  await page.goto(BASE + '/#/pages/booking/form?packageId=1&title=' + encodeURIComponent('城市轻写真') + '&price=399', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(2000)
  const form = await page.evaluate(() => {
    const p = document.querySelector('.ub-page').getBoundingClientRect()
    const s = document.querySelector('.submit').getBoundingClientRect()
    return { pageWidth: Math.round(p.width), pageLeft: Math.round(p.left), submitWidth: Math.round(s.width), overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth }
  })
  rec('1440 表单收窄 680 + 按钮 320', form.pageWidth === 680 && Math.abs(form.pageLeft - 380) <= 2 && form.submitWidth === 320 && form.overflow === 0, form)
  await page.screenshot({ path: path.join(__dirname, '..', 'evidence', 'step6_desktop_form_1440.png') })

  out.consoleErrors = consoleErrors
  out.allPass = out.cases.every((c) => c.pass)
  fs.writeFileSync(path.join(__dirname, '..', 'evidence', 'step6_desktop_probe.json'), JSON.stringify(out, null, 2), 'utf8')
  console.log('=== allPass =', out.allPass, '===')
  await browser.close()
  process.exit(out.allPass ? 0 : 1)
})().catch((e) => {
  console.error('DESKTOP_PROBE_FAIL', e.message)
  process.exit(1)
})
