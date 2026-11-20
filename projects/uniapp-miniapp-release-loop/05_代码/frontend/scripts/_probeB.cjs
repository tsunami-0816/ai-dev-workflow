const puppeteer = require('puppeteer-core');
(async () => {
 const b = await puppeteer.launch({executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', headless:'new'});
 const p = await b.newPage();
 await p.setViewport({width:375,height:812,deviceScaleFactor:1});
 await p.goto('http://127.0.0.1:5186/#/pages/index/index?v=B',{waitUntil:'networkidle0'});
 await new Promise(r=>setTimeout(r,1200));
 console.log(await p.evaluate(() => {
   const e = document.elementFromPoint(10,5);
   const body = document.body;
   const pg = document.querySelector('uni-page-body');
   const cs = document.querySelector('.cs-page');
   return {
     scrollY: window.scrollY,
     topEl: e ? e.className + '|' + e.tagName : 'none',
     bodyBg: getComputedStyle(body).backgroundColor,
     pageBg: getComputedStyle(document.querySelector('uni-page')||body).backgroundColor,
     csTop: cs.getBoundingClientRect().top,
     csBg: getComputedStyle(cs).backgroundColor,
     uniPageBodyTop: pg ? pg.getBoundingClientRect().top : null,
     uniPageBodyBg: pg ? getComputedStyle(pg).backgroundColor : null,
     docTop: document.documentElement.getBoundingClientRect().top
   };
 }));
 await b.close();
})();
