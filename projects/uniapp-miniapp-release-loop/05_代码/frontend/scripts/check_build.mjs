// 双端产物校验（T-103）：H5 有 index.html；小程序 app.json 页数 = pages.json 页数，且 tabBar 2 项
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const fails = []

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'))
}

const srcPagesPath = path.join(root, 'src/pages.json')
if (!fs.existsSync(srcPagesPath)) fails.push('缺少 src/pages.json')
const expectedPages = fails.length ? 0 : readJson(srcPagesPath).pages.length

const h5Index = path.join(root, 'dist/build/h5/index.html')
if (!fs.existsSync(h5Index)) fails.push('缺少 dist/build/h5/index.html（先跑 npm run build:h5）')

const mpAppPath = path.join(root, 'dist/build/mp-weixin/app.json')
if (!fs.existsSync(mpAppPath)) {
  fails.push('缺少 dist/build/mp-weixin/app.json（先跑 npm run build:mp-weixin）')
} else {
  const app = readJson(mpAppPath)
  const pages = Array.isArray(app.pages) ? app.pages.length : 0
  if (pages !== expectedPages) fails.push(`小程序页数 ${pages} ≠ pages.json ${expectedPages}`)
  const tabs = Array.isArray(app.tabBar?.list) ? app.tabBar.list.length : 0
  if (tabs !== 2) fails.push(`tabBar 项数 ${tabs} ≠ 2`)
}

console.log(`H5 入口：${fs.existsSync(h5Index) ? 'OK' : 'MISSING'}`)
console.log(`小程序页数：期望 ${expectedPages}`)
if (fails.length) {
  for (const f of fails) console.error('FAIL ' + f)
  process.exit(1)
}
console.log('PASS 双端产物校验通过')
