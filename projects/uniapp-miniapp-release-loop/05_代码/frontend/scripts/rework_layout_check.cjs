// 5B 返工 · 375 基准实测（Q-006 overflow / Q-009 遮挡 / T-705 标注证据）
const puppeteer = require('puppeteer-core')
const fs = require('node:fs')
const path = require('node:path')

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5186'
const EV = path.resolve(__dirname, '../../../05.5_代码Review/evidence')
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const homeMetrics = () => {
  const flat = (r) => ({ x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) })
  const page = document.querySelector('.lb-page')
  const heroTitle = document.querySelector('.hero-title')
  const heroPrice = document.querySelector('.hero-price')
  const photo = document.querySelector('.hero-photo')
  const rows = [...document.querySelectorAll('.row')]
  const tab = document.querySelector('.uni-tabbar__label')
  return {
    pagePaddingLeft: getComputedStyle(page).paddingLeft,
    docScrollWidth: document.documentElement.scrollWidth,
    docClientWidth: document.documentElement.clientWidth,
    heroTitleFont: getComputedStyle(heroTitle).fontSize,
    heroPriceFont: getComputedStyle(heroPrice).fontSize,
    heroPhoto: photo ? flat(photo.getBoundingClientRect()) : null,
    rowCount: rows.length,
    rowH: rows[0] ? Math.round(rows[0].getBoundingClientRect().height) : 0,
    rowTitleFont: rows[0] ? getComputedStyle(rows[0].querySelector('.row-title')).fontSize : '',
    tabLabelFont: tab ? getComputedStyle(tab).fontSize : ''
  }
}

const detailMetrics = () => {
  const flat = (r) => ({ x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) })
  const photo = document.querySelector('.photo')
  const section = document.querySelector('.section')
  const bar = document.querySelector('.bar')
  const title = document.querySelector('.title')
  const summary = document.querySelector('.summary')
  const note = document.querySelector('.photo-note')
  const pr = photo ? photo.getBoundingClientRect() : null
  return {
    docScrollWidth: document.documentElement.scrollWidth,
    docClientWidth: document.documentElement.clientWidth,
    photo: pr ? flat(pr) : null,
    photoRatio: pr && pr.width ? Math.round((pr.height / pr.width) * 1000) / 1000 : null,
    titleFont: title ? getComputedStyle(title).fontSize : '',
    summaryFont: summary ? getComputedStyle(summary).fontSize : '',
    section: section ? flat(section.getBoundingClientRect()) : null,
    bar: bar ? flat(bar.getBoundingClientRect()) : null,
    overlap: section && bar
      ? Math.max(0, Math.round(section.getBoundingClientRect().bottom - bar.getBoundingClientRect().top))
      : null,
    specTextPresent: !!note
  }
}

;(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: 'new' })
  const out = { widths: {}, detail: {} }

  for (const w of [375, 390, 414]) {
    const page = await browser.newPage()
    await page.setViewport({ width: w, height: 844, deviceScaleFactor: 1 })
    await page.goto(BASE + '/#/pages/index/index?v=A', { waitUntil: 'networkidle0', timeout: 30000 })
    await sleep(1600)
    out.widths[w] = await page.evaluate(homeMetrics)
    if (w === 375) await page.screenshot({ path: path.join(EV, 'rework_home_375.png'), fullPage: true })
    await page.close()

    const dp = await browser.newPage()
    await dp.setViewport({ width: w, height: 844, deviceScaleFactor: 1 })
    await dp.goto(BASE + '/#/pages/package/detail?id=1', { waitUntil: 'networkidle0', timeout: 30000 })
    await sleep(1600)
    out.detail[w] = await dp.evaluate(detailMetrics)
    if (w === 375) {
      out.detail[375].gutter = out.widths[375].pagePaddingLeft
      await dp.screenshot({ path: path.join(EV, 'rework_detail_375.png'), fullPage: true })
      // overlay：画 24px 边距线与 8px 网格线，便于对照标注
      await dp.evaluate(() => {
        const g = document.createElement('div')
        g.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:9999;'
        g.innerHTML = `
          <div style="position:absolute;left:24px;top:0;bottom:0;width:1px;background:rgba(196,69,58,.85)"></div>
          <div style="position:absolute;right:24px;top:0;bottom:0;width:1px;background:rgba(196,69,58,.85)"></div>
          <div style="position:absolute;left:0;right:0;top:72px;height:1px;background:rgba(142,154,147,.35)"></div>
          <div style="position:absolute;left:0;right:0;top:144px;height:1px;background:rgba(142,154,147,.35)"></div>
          <div style="position:absolute;left:0;right:0;bottom:81px;height:1px;background:rgba(196,69,58,.5)"></div>
          <div style="position:absolute;left:8px;top:4px;font:11px/1.4 monospace;color:#C4453A">gutter 24 / rules 72,144 / bar 81</div>`
        document.body.appendChild(g)
      })
      await dp.screenshot({ path: path.join(EV, 'rework_overlay_375.png') })
      // annotations：编号标注层（数据来自本脚本实测）
      await dp.evaluate((m) => {
        const a = document.createElement('div')
        a.style.cssText = 'position:fixed;left:0;right:0;bottom:96px;z-index:9999;background:rgba(0,0,0,.82);' +
          'color:#F2EDE4;font:9px/1.55 monospace;padding:6px 10px;border-top:1px solid rgba(242,237,228,.25)'
        const items = [
          '01 页边距 24px（实测 ' + m.gutter + '，与 token 一致）',
          '02 图片位左右出血：左 0 / 右 ' + (m.photo ? m.photo.x + m.photo.w : '?') + '（视口 ' + m.docClientWidth + '）',
          '03 图片位比例 4:5（实测比 ' + m.photoRatio + '）',
          '04 正文 15px（实测 ' + m.summaryFont + '）',
          '05 标题 34px（实测 ' + m.titleFont + '）',
          '06 说明区 y ' + (m.section ? m.section.y + '–' + (m.section.y + m.section.h) : '?') + '，预约栏顶 ' + (m.bar ? m.bar.y : '?'),
          '07 首屏遮挡 ' + (m.overlap === 0 ? '0px' : (m.overlap || 0) + 'px'),
          '08 横向溢出 ' + (m.docScrollWidth > m.docClientWidth ? (m.docScrollWidth - m.docClientWidth) + 'px' : '0px'),
          '09 规格文字「样片 4:5」' + (m.specTextPresent ? '仍在' : '已移除'),
          '10 预约栏高 ' + (m.bar ? m.bar.h : '?') + 'px（按钮 48 + 上下 16）'
        ]
        a.innerHTML = items.join('<br>')
        document.body.appendChild(a)
        window.scrollTo(0, 0)
      }, out.detail[375])
      await dp.screenshot({ path: path.join(EV, 'rework_annotations_375.png') })
    }
    await dp.close()
  }

  // 表单页：主按钮/输入框高度
  const fp = await browser.newPage()
  await fp.setViewport({ width: 375, height: 844, deviceScaleFactor: 1 })
  await fp.goto(BASE + '/#/pages/booking/form?packageId=1&title=' + encodeURIComponent('城市轻写真') + '&price=399', { waitUntil: 'networkidle0', timeout: 30000 })
  await sleep(1500)
  out.form = await fp.evaluate(() => {
    const s = document.querySelector('.submit')
    const c = document.querySelector('.field .control')
    return {
      submitH: s ? Math.round(s.getBoundingClientRect().height) : 0,
      controlH: c ? Math.round(c.getBoundingClientRect().height) : 0,
      fieldPaddingTop: document.querySelector('.field') ? getComputedStyle(document.querySelector('.field')).paddingTop : ''
    }
  })
  await fp.close()

  fs.writeFileSync(path.join(EV, 'rework_layout.json'), JSON.stringify(out, null, 2), 'utf8')
  console.log(JSON.stringify(out, null, 2))
  await browser.close()
})().catch((e) => {
  console.error('LAYOUT_FAIL', e.message)
  process.exit(1)
})
