// 阶段二人工走查暴露的两处问题的回归探针：
// ① 11 位但前缀非 1[3-9] 的手机号应给「格式不对」而不是「请输入 11 位」；输入变化时旧红字立刻消失
// ② 「我的」档期卡点击后应进对应套餐详情（此前无点击）
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const BASE = 'http://127.0.0.1:5186/';
const OUT = path.resolve(__dirname, '..', 'evidence');
const API = 'http://127.0.0.1:8092';

const results = [];
function rec(name, pass, detail) {
  results.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name} ${JSON.stringify(detail)}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  let bookingPosts = 0;
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().indexOf('/api/bookings') >= 0) bookingPosts += 1;
  });

  // 真登录（demo / welcome1），写入 uni Storage 信封
  const loginRes = await fetch(API + '/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ account: 'demo', password: 'welcome1' }),
  }).then((r) => r.json());
  if (loginRes.code !== 0) throw new Error('login failed ' + JSON.stringify(loginRes));

  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 30000 });
  await page.evaluate((d) => {
    const wrap = (type, data) => JSON.stringify({ type, data });
    localStorage.setItem('ub_token', wrap('string', d.token));
    localStorage.setItem('ub_user', wrap('object', { userId: d.userId, nickname: d.nickname || '演示用户A' }));
  }, loginRes.data);

  // —— ① 手机号：11 位但前缀不对 ——
  const title = encodeURIComponent('城市轻写真');
  await page.goto(`${BASE}/#/pages/booking/form?packageId=1&title=${title}&price=399`, {
    waitUntil: 'networkidle0',
    timeout: 30000,
  });
  await sleep(2000);

  // H5 的 picker 实际是原生 input[type=date]，headless 点不开系统日历 → 直接写值并触发原生事件
  const tomorrow = new Date(Date.now() + 86400000);
  const dstr = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`;
  const dateSet = await page.evaluate((v) => {
    const inp = document.querySelector('.uni-picker-system_input');
    if (!inp) return false;
    inp.value = v;
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    inp.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }, dstr);
  await sleep(400);
  const dateOk = await page.evaluate(() => ({ ok: document.querySelector('.control')?.textContent?.trim() === document.querySelector('.uni-picker-system_input')?.value, text: document.querySelector('.control')?.textContent?.trim() }));
  rec('日期可选（原生 input 写入）', dateSet && dateOk.ok, { ...dateOk, dstr });
  await sleep(200);

  const slotEls = await page.$$('.slot');
  if (slotEls.length >= 3) await slotEls[2].click();
  await sleep(300);
  const slotState = await page.evaluate(() => ({ active: document.querySelector('.slot.active')?.textContent?.trim() || '' }));
  rec('时段可选中', slotState.active === '晚间', slotState);

  await page.click('input.uni-input-input');
  await page.type('input.uni-input-input', '12345688901', { delay: 50 });
  await sleep(200);
  await page.click('.submit');
  await sleep(700);
  const fmtErr = await page.evaluate(() => ({
    value: document.querySelector('input.uni-input-input')?.value || '',
    errs: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()),
  }));
  rec(
    '11 位但前缀非 1[3-9] → 格式错误提示',
    fmtErr.errs.length === 1 && fmtErr.errs[0] === '手机号格式不对，请检查' && fmtErr.value === '12345688901' && bookingPosts === 0,
    { ...fmtErr, bookingPosts }
  );
  await page.screenshot({ path: path.join(OUT, 'step6_phone_format_err.png') });

  // 输入变化即清红字
  await page.click('input.uni-input-input');
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await page.type('input.uni-input-input', '13800138123', { delay: 60 });
  await sleep(300);
  const afterType = await page.evaluate(() => ({
    errs: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()),
    value: document.querySelector('input.uni-input-input')?.value || '',
  }));
  rec('改输入后旧红字立即消失', afterType.errs.length === 0 && afterType.value === '13800138123', afterType);

  // 合法手机号提交成功（会新增 1 条演示预约，7.5 数据重置时清）
  await page.click('.submit');
  await sleep(1500);
  const done = await page.evaluate(() => ({
    url: location.href,
    hasDone: !!document.querySelector('.done') || !!document.querySelector('.done-no'),
    no: document.querySelector('.done-no')?.textContent?.trim() || '',
    errs: [...document.querySelectorAll('.err')].map((n) => n.textContent.trim()),
  }));
  rec('合法手机号提交成功', done.hasDone && done.errs.length === 0 && bookingPosts >= 1, { ...done, bookingPosts });
  await page.screenshot({ path: path.join(OUT, 'step6_booking_success.png') });

  // —— ② 我的档期卡可点 → 套餐详情 ——
  await page.goto(BASE + '/#/pages/my/index', { waitUntil: 'networkidle0', timeout: 30000 });
  await sleep(2600);
  const noteExists = await page.evaluate(() => !!document.querySelector('.list-note'));
  rec('我的页有待确认说明', noteExists, { noteExists });
  const firstCard = await page.$('.booking');
  if (!firstCard) throw new Error('no booking card rendered');
  const beforeClick = await page.evaluate(() => ({ url: location.href, cards: document.querySelectorAll('.booking').length }));
  await firstCard.click();
  await sleep(1500);
  const afterClick = await page.evaluate(() => ({ url: location.href }));

  rec(
    '点档期卡进套餐详情',
    afterClick.url.indexOf('/pages/package/detail') >= 0 && afterClick.url.indexOf('id=') >= 0,
    { beforeClick, afterClick }
  );
  await page.screenshot({ path: path.join(OUT, 'step6_my_card_tap.png') });

  await browser.close();
  const allPass = results.every((r) => r.pass);
  fs.writeFileSync(
    path.join(OUT, 'step6_booking_ux_probe.json'),
    JSON.stringify({ allPass, at: new Date().toISOString(), results }, null, 2),
    'utf8'
  );
  console.log('=== allPass = ' + allPass + ' ===');
  process.exit(allPass ? 0 : 1);
})().catch((e) => {
  console.error(e.message);
  process.exit(1);
});
