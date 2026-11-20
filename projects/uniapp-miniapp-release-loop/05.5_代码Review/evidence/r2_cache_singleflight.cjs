// 5.5 R2 复审 · Q-012 缓存单飞验证：清掉 ub:pkg:list 后并发 20 个 GET，
// 通过 MySQL Com_select 增量判断回源次数（不是只看「接口 200」）。
// 运行前请由外层 PowerShell 读取 SHOW GLOBAL STATUS LIKE 'Com_select' 前后值。
const net = require('node:net')

function redisCmd(args) {
  return new Promise((resolve, reject) => {
    const sock = net.createConnection({ host: '127.0.0.1', port: 6379 })
    const buf = Buffer.from('*' + args.length + '\r\n' + args.map((a) => '$' + Buffer.byteLength(a) + '\r\n' + a + '\r\n').join(''))
    sock.on('data', (d) => { resolve(d.toString()); sock.end() })
    sock.on('error', reject)
    sock.write(buf)
  })
}

;(async () => {
  const del = await redisCmd(['DEL', 'ub:pkg:list'])
  console.log('DEL ub:pkg:list ->', del.trim())

  const started = Date.now()
  const results = await Promise.all(
    Array.from({ length: 20 }, () => fetch('http://127.0.0.1:8092/api/packages?page=1&size=10').then((r) => r.json()))
  )
  const ok = results.filter((r) => r.code === 0 && r.data && r.data.total === 4 && r.data.list.length === 4).length
  console.log('requests=20 ok=' + ok + ' elapsedMs=' + (Date.now() - started))

  const ttl = await redisCmd(['TTL', 'ub:pkg:list'])
  console.log('TTL ub:pkg:list ->', ttl.trim())
  process.exit(ok === 20 ? 0 : 1)
})().catch((e) => { console.error('FAIL', e.message); process.exit(1) })
