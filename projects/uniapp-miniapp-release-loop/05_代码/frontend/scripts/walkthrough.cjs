// 5B 走查脚本（H5 五页）：逐页截图 + 关键元素断言，结果写 evidence/walkthrough.json
const fs = require('node:fs')
const path = require('node:path')
const puppeteer = require('puppeteer-core')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'

const cases = [
  { name: 'home', url: BASE + '/', expect: (d) => ({
    rows: d.querySelectorAll('.row').length,
    prices: [...d.querySelectorAll('.row-price')].map((n) => n.textContent.trim()),
    heroPrice: d.querySelector('.hero-price')?.textContent?.trim() || '',
    tabBarItems: d.querySelectorAll('.uni-tabbar__label').length
  }) },
  { name: 'login', url: BASE + '/#/pages/login/index', expect: (d) => ({
    title: d.querySelector('.title')?.textContent?.trim() || '',
    account: d.querySelector('input')?.value || '',
    passwordInput: !!d.querySelector('input[type=password]'),
    btn: d.querySelector('.btn-primary')?.textContent?.trim() || ''
  }) },
  { name: 'detail', url: BASE + '/#/pages/package/detail?id=1', expect: (d) => ({
    title: d.querySelector('.title')?.textContent?.trim() || '',
    price: d.querySelector('.price')?.textContent?.trim() || '',
    tags: [...d.querySelectorAll('.tag')].map((n) => n.textContent.trim()),
    fold: d.querySelector('.fold')?.textContent?.trim() || '',
    cta: d.querySelector('.btn-primary')?.textContent?.trim() || ''
  }) },
  { name: 'form', url: BASE + '/#/pages/booking/form?packageId=1&title=%E5%9F%8E%E5%B8%82%E8%BD%BB%E5%86%99%E7%9C%9F&price=399', expect: (d) => ({
    pkg: d.querySelector('.pkg-title')?.textContent?.trim() || '',
    slots: [...d.querySelectorAll('.slot')].map((n) => n.textContent.trim()),
    submit: d.querySelector('.submit')?.textContent?.trim() || '',
    datePicker: !!d.querySelector('.control')
  }) },
  { name: 'my', url: BASE + '/#/pages/my/index', expect: (d) => ({
    loggedOut: !!d.querySelector('.state'),
    loginBtn: d.querySelector('.btn-primary')?.textContent?.trim() || ''
  }) }
]

;(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-first-run', '--disable-extensions']
  })
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })

  const out = []
  for (const c of cases) {
    let status = 'ok'
    let payload = {}
    try {
      const resp = await page.goto(c.url, { waitUntil: 'networkidle0', timeout: 30000 })
      await new Promise((r) => setTimeout(r, 2500))
      payload = await page.evaluate(
        (fnSource) => {
          const fn = eval('(' + fnSource + ')')
          return fn(document)
        },
        c.expect.toString()
      )
      payload.httpStatus = resp ? resp.status() : 0
      await page.screenshot({ path: `evidence/walk_${c.name}.png` })
    } catch (e) {
      status = 'fail'
      payload = { error: e.message }
    }
    out.push({ page: c.name, url: c.url, status, ...payload })
  }

  const file = path.resolve('evidence/walkthrough.json')
  fs.writeFileSync(file, JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
})().catch((e) => {
  console.error('WALK_FAIL', e.message)
  process.exit(1)
})
