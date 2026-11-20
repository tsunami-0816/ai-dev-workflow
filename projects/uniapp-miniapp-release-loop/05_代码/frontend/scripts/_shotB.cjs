const puppeteer = require('puppeteer-core');
(async () => {
 const b = await puppeteer.launch({executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe', headless:'new'});
 const p = await b.newPage();
 await p.setViewport({width:375,height:812,deviceScaleFactor:2});
 await p.goto('http://127.0.0.1:5186/#/pages/index/index?v=B',{waitUntil:'networkidle0'});
 await new Promise(r=>setTimeout(r,1200));
 await p.evaluate(()=>{const t=document.querySelector('.uni-tabbar'); if(t)t.style.display='none';});
 await p.screenshot({path:'evidence/design_variants/_B_viewport.png'});
 await p.screenshot({path:'evidence/design_variants/_B_fullpage_nodev.png', fullPage:true});
 await b.close();
})();
