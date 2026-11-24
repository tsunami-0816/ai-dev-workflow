// 手机端 375 截图留证（桌面改造后回归"手机版式不变"）
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = 'http://127.0.0.1:5186/';
const OUT = path.resolve(__dirname, '..', 'evidence');

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 375, height: 812, deviceScaleFactor: 2 });
  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise((r) => setTimeout(r, 600));
  await page.screenshot({ path: path.join(OUT, 'step6_mobile375_index.png') });

  await page.goto(BASE + '#/pages/package/detail?id=1', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise((r) => setTimeout(r, 800));
  await page.screenshot({ path: path.join(OUT, 'step6_mobile375_detail.png') });

  const info = await page.evaluate(() => ({
    w: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  console.log('captured', JSON.stringify(info));
  await browser.close();
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
