// 第 9 步 · 走查现场只读渲染探针（2026-11-25 重起现场用）
// 只读：不登录、不下单、不写库；只验证 H5 首页/详情/我的三页能渲染、接口 200、console 0 报错
// 用法：node 09_验收/scripts/render_probe_readonly.cjs
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require(path.join(__dirname, '..', '..', '05_代码', 'frontend', 'node_modules', 'puppeteer-core'))

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const API = 'http://127.0.0.1:8092'
const OUT = path.join(__dirname, '..', 'evidence')
const STAMP = process.argv[2] || '20261125'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const out = { stamp: STAMP, startedAt: new Date().toISOString(), cases: [], consoleErrors: [], posts: [] }

function rec(name, pass, data) {
  out.cases.push({ name, pass, ...data })
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name} ${JSON.stringify(data)}`)
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--disable-gpu', '--no-sandbox'],
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2 })
  page.on('pageerror', (e) => out.consoleErrors.push('pageerror: ' + e.message))
  page.on('console', (m) => { if (m.type() === 'error') out.consoleErrors.push('console: ' + m.text()) })
  page.on('request', (r) => { if (r.method() !== 'GET') out.posts.push(r.method() + ' ' + r.url()) })

  // 1) 首页 375
  await page.goto(BASE + '/#/pages/index/index', { waitUntil: 'networkidle0', timeout: 40000 })
  await sleep(2500)
  const a1 = await page.evaluate(() => ({
    title: (document.querySelector('h1')?.textContent || '').trim(),
    text: (document.body.innerText || '').replace(/\s+/g, ' '),
    overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
  }))
  const pkgTitles = ['城市轻写真', '复古胶片', '情侣纪实', '个人写真·夜场']
  rec('R-01 首页渲染（375·4 套餐文案齐）',
    !!a1.title && !a1.overflowX && pkgTitles.every((t) => a1.text.includes(t)),
    { title: a1.title, overflowX: a1.overflowX, text: a1.text.slice(0, 80) })
  await page.screenshot({ path: path.join(OUT, `step9_render_probe_${STAMP}_index_375.png`) })

  // 2) 详情 id=1
  await page.goto(BASE + '/#/pages/package/detail?id=1', { waitUntil: 'networkidle0', timeout: 40000 })
  await sleep(2200)
  const a2 = await page.evaluate(() => ({
    title: (document.querySelector('.title')?.textContent || document.querySelector('h2')?.textContent || '').trim(),
    price: (document.querySelector('.price')?.textContent || '').trim(),
    cta: (document.querySelector('.btn-primary')?.textContent || '').trim(),
    h1: document.querySelectorAll('h1').length,
  }))
  rec('R-02 详情页渲染（id=1）', a2.cta.includes('立即预约') && a2.h1 === 1, a2)
  await page.screenshot({ path: path.join(OUT, `step9_render_probe_${STAMP}_detail_375.png`) })

  // 3) 我的（未登录态）
  await page.evaluate(() => localStorage.clear())
  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 40000 })
  await sleep(2200)
  const a3 = await page.evaluate(() => ({
    loginBtn: (document.querySelector('.btn-primary')?.textContent || '').trim(),
    bookings: document.querySelectorAll('.booking').length,
  }))
  rec('R-03 我的页未登录态', a3.loginBtn.includes('去登录') && a3.bookings === 0, a3)
  await page.screenshot({ path: path.join(OUT, `step9_render_probe_${STAMP}_my_375.png`) })

  // 4) 接口与云函数（纯 GET）
  const pk = await (await fetch(API + '/api/packages')).json()
  rec('R-04 /api/packages', pk.code === 0 && pk.data.total >= 4, { code: pk.code, total: pk.data.total })
  const hz = await (await fetch('http://127.0.0.1:8093/healthz?probe=1')).json()
  rec('R-05 云函数 8093 探针', hz.status === 'UP' && hz.backendProbe.code === 0, { status: hz.status, code: hz.backendProbe.code })

  rec('R-06 console 报错 0', out.consoleErrors.length === 0, { count: out.consoleErrors.length })
  rec('R-07 全程无写请求（只读）', out.posts.filter((p) => p.indexOf('/api/bookings') >= 0 || p.startsWith('POST')).length === 0, { posts: out.posts.slice(0, 5) })

  out.finishedAt = new Date().toISOString()
  out.summary = {
    total: out.cases.length,
    passed: out.cases.filter((c) => c.pass).length,
    failed: out.cases.filter((c) => !c.pass).length,
  }
  fs.writeFileSync(path.join(OUT, `step9_render_probe_${STAMP}.json`), JSON.stringify(out, null, 2))
  console.log('SUMMARY', JSON.stringify(out.summary))
  await browser.close()
  process.exit(out.summary.failed === 0 ? 0 : 1)
}

main().catch((e) => { console.error('PROBE_ERROR', e.message); process.exit(2) })
