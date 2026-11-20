# 云函数 · apiProxy / getOpenid（T-206）

> 零第三方依赖，只用 Node 内置 `http/https/crypto`（架构 §10 预设动作③：降低部署面）。
> 当前进度：本机 http 模式已落地并自测（证据 `evidence/smoke_cf.txt`）；云开发模式代码同源，未开通环境故未做真机验证（C07–C09 外部依赖）。

## 1. 目录

```
05_代码/cloud-functions/
├─ package.json              # 无 dependencies，仅 scripts
├─ .env.example              # 环境变量模板（真密钥不进 git）
├─ shared/
│   ├─ config.js             # 环境变量集中读取
│   ├─ signer.js             # HMAC-SHA256 加签 / nonce / traceId
│   ├─ errors.js             # 错误码 + HTTP 状态映射（与后端 ErrorCode 同值）
│   ├─ routes.js             # action 白名单 + payload 校验
│   ├─ httpClient.js         # 内置 http/https，超时 + 响应上限 + 错误分类
│   ├─ proxyHandler.js       # 核心：校验→加签→调用→重试→统一响应
│   └─ logger.js             # 单行 JSON 日志（不含密钥/token）
├─ apiProxy/
│   ├─ index.js              # 云开发入口 exports.main
│   └─ localServer.js        # 本机 http 8093
├─ getOpenid/
│   ├─ index.js              # code2session → openid
│   └─ localServer.js        # 本机 http 8094
├─ test/
│   ├─ mockWxServer.js       # 微信接口 mock（8095，仅自测解析路径）
│   └─ hangServer.js         # 永不响应假后端（8096，验超时降级）
└─ evidence/                 # 冒烟原始输出
```

## 2. 启动

```powershell
cd 05_代码/cloud-functions
# 主实例（apiProxy → 后端 8092）
node apiProxy/localServer.js
# 需要小程序 code 换 openid 时（缺 MP_APPSECRET 会明确报 50001，不伪造）
node getOpenid/localServer.js

# 或用一键脚本拉起（含依赖容器 + 后端 + 云函数）
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -Smoke
```

环境变量见 `.env.example`。密钥纪律：`APP_SECRET` 必须与后端一致；`MP_APPSECRET` 只在服务端环境变量，**永不**进前端、日志、截图、文档正文。

## 3. 调用协议（前端 → 云函数）

同一份 event 结构，两种模式只是传输不同：

```js
// cloud 模式
wx.cloud.callFunction({ name: 'apiProxy', data: { action, payload, token } })

// http 模式（开发者工具需勾「不校验合法域名、TLS 版本及 HTTPS 证书」）
uni.request({ url: 'http://127.0.0.1:8093/', method: 'POST', data: { action, payload, token } })
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `action` | 是 | `packages` / `packageDetail` / `login` / `logout` / `createBooking` / `myBookings` |
| `payload` | 是 | 仅允许下表字段；出现未知字段直接 40001（防越权参数混入） |
| `token` | 除登录/套餐外 | 裸 JWT（不带 `Bearer ` 前缀） |

| action | 后端接口 | payload 允许字段 | 需 token |
|---|---|---|---|
| packages | `GET /api/packages` | `page`(1~1000,默认1)、`size`(1~50,默认10) | 否 |
| packageDetail | `GET /api/packages/{id}` | `id` 正整数 | 否 |
| login | `POST /api/auth/login` | `account`+`password` 或 `openid`；`nickname` 可选 | 否 |
| logout | `POST /api/auth/logout` | 无 | 是 |
| createBooking | `POST /api/bookings` | `packageId`、`bookDate`(YYYY-MM-DD 真实日期)、`slot`(上午/下午/晚间)、`contact`(手机号)、`remark`(≤255) | 是 |
| myBookings | `GET /api/bookings` | `page`、`size` | 是 |

响应（成功与失败同结构，HTTP 状态按 code 映射）：

```json
{"code":0,"msg":"ok","data":{...},"traceId":"cf-9a3f21c0","elapsedMs":37}
```

> 字段差异登记：第一轮架构 §6.5 写的是 `message/traceId/elapsedMs`，落地统一为 `msg`（与后端 `{code,msg,data}` 一致），避免前端维护两套字段。已记入 `05_代码/backend/后端开发实现文档.md` §6。

## 4. 代理链路约束

| 项 | 实现 |
|---|---|
| 签名 | `X-Sign = hex(HMAC-SHA256(rawBody + "|" + X-Timestamp, APP_SECRET))`，与后端 `SignatureFilter` 同口径；GET 的 rawBody 为空串 |
| 通道标识 | 固定带 `X-Client: cloud`，后端因此强制校验签名 |
| 防重放 | 每次尝试生成新 `X-Nonce`（32 位 hex）+ 新 `X-Timestamp`；重试绝不复用 |
| 超时 | 单次 3s（`CF_TIMEOUT_MS`），小于后端 Tomcat 5s，重试靠 T-402 幂等兜底 |
| 重试 | 网络错误 / 超时 / 后端 5xx 重试 1 次；4xx 不重试 |
| 降级提示 | 重试耗尽 → `50002`「网络不稳定，请重试」 |
| 请求体上限 | 1MB（`CF_MAX_BODY_BYTES`），超限 413 + 40001 |

## 5. 错误码

与后端 `ErrorCode` 同值：40001/40002/40101/40102/40103/40301/40400/40401/42901/50000/50001/50002。
云函数本地新增语义（不新增码位）：
- 未知 action / 未知字段 / 字段格式错 → 40001（msg 指明字段或 action，前端可直接红字）
- 后端不可达、超时、持续 5xx → 50002
- 后端返回非 JSON / 缺 `code` / 其它内部异常 → 50001
- `getOpenid` 缺 `MP_APPID` / `MP_APPSECRET` → 50001（msg 明确「云开发未配置」）

## 6. 自测

```powershell
python scripts\smoke_cf.py
```

脚本自己拉起临时实例（8095 mock 微信 / 8096 挂起后端 / 8097 错密钥 / 8098 挂起后端代理），跑完自动关闭；8093 若已在监听则复用。输出落 `evidence/smoke_cf.txt`。
