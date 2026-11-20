// 5.5 R2 复审 · Q-014 独立验证：口令错误是否落在「口令」字段级红字（而非表单级提示）
// 运行：node r2_login_field_err.cjs  → 产出 r2_login_field_err.json + r2_login_field_err.png
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')
const path = require('node:path')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const EV = __dirname
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

;(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new' })
  const page = await browser.newPage()
  await page.setViewport({ width: 375, height: 844, deviceScaleFactor: 1 })
  await page.goto(BASE + '/#/pages/login/index', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1500)

  await page.evaluate(() => {
    const setVal = (el, v) => {
      el.focus(); el.value = v
      el.dispatchEvent(new Event('input', { bubbles: true }))
      el.dispatchEvent(new Event('change', { bubbles: true }))
    }
    const inputs = [...document.querySelectorAll('input.uni-input-input')]
    setVal(inputs[0], 'demo')
    setVal(inputs[1], 'wrong-password-r2')
  })
  await page.click('.btn-primary')
  await sleep(2000)

  const out = await page.evaluate(() => {
    const fields = [...document.querySelectorAll('.field')]
    const labelOf = (f) => (f.querySelector('.label')?.textContent || '').trim()
    const errOf = (f) => (f.querySelector('.err-field')?.textContent || '').trim()
    return {
      fields: fields.map((f) => ({ label: labelOf(f), fieldErr: errOf(f) })),
      formErr: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()).join(' | '),
      token: localStorage.getItem('ub_token') || ''
    }
  })
  await page.screenshot({ path: path.join(EV, 'r2_login_field_err.png') })
  out.pass = out.fields.some((f) => f.label === '口令' && f.fieldErr.length > 0) && !out.token
  fs.writeFileSync(path.join(EV, 'r2_login_field_err.json'), JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
  process.exit(out.pass ? 0 : 1)
})().catch((e) => {
  console.error('LOGIN_ERR_FAIL', e.message)
  process.exit(1)
})
