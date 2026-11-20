# 前端 · uniapp-booking-miniapp（5B）

> uni-app（Vue3 + TS + Vite）双端：H5（浏览器）+ 微信小程序。
> 视觉唯一来源：`02_架构设计/门面页方向稿.md`（方向 A「暗房档期」）；本目录内不写裸色值，统一取 `src/styles/tokens.css`。
> 后端：`booking-service`（8092，5A 已跑通）；小程序通道：`apiProxy` 云函数（8093）。

## 1. 运行

```powershell
cd 05_代码/frontend
npm install            # 已执行成功（556 包，见 evidence/npm_install.log）

# H5 开发（固定 5186，已在端口表登记）
npm run dev:h5

# H5 生产构建（产物 dist/build/h5）
npm run build:h5

# 小程序构建（产物 dist/build/mp-weixin，用微信开发者工具打开该目录）
npm run build:mp-weixin

# 双端产物校验（H5 index.html + app.json 页数=5 + tabBar=2）
npm run check:build
```

前置：后端 8092 已启动（`scripts/start_all.ps1` 会一并拉起 8093）。

## 2. 两端差异（D-05 / D-33 素材）

| 项 | H5 | 微信小程序 |
|---|---|---|
| 请求通道 | `uni.request` → `http://127.0.0.1:8092`（CORS 仅放行 5186） | `uni.request` → `apiProxy` 8093（HMAC 签名、3s 超时、重试 1 次） |
| 登录 | 账号 + 口令（`demo / welcome1`） | `wx.login` → `getOpenid`(8094) → `apiProxy` login |
| 合法域名 | 不需要 | 开发者工具需勾「不校验合法域名、TLS 版本及 HTTPS 证书」（`manifest.json` 已设 `urlCheck:false`） |
| 分享 | 需接入 H5 分享方案（后续） | `onShareAppMessage`（后续） |
| tabBar | 文字 tab | 文字 tab（未配图标，审核前可补 1px 线描图标） |

平台判定集中在 `src/utils/env.ts`（`#ifdef H5` / `#ifdef MP-WEIXIN`），业务代码不散落条件编译。

## 3. 页面与链路

| 页面 | 路径 | 链路 | 接口 |
|---|---|---|---|
| 首页（册子） | `pages/index/index` | 进页→加载套餐→首屏门面 + 清单→点行进详情 | `GET /api/packages` |
| 登录 | `pages/login/index` | H5 账号口令 / 小程序 code→openid→JWT | `POST /api/auth/login` |
| 套餐详情 | `pages/package/detail` | 点行→详情→说明折叠→「立即预约」 | `GET /api/packages/{id}` |
| 预约表单 | `pages/booking/form` | 选日期/时段/联系人→校验→提交→单号（或 `duplicated` 提示） | `POST /api/bookings` |
| 我的 | `pages/my/index` | 未登录引导→登录列表→状态标签→退出 | `GET /api/bookings`、`POST /api/auth/logout` |

路由守卫：受保护动作在提交时才要求登录（`goLogin` 带返回地址），tabBar「我的」页不自动跳登录，避免 H5/小程序 tab 页与登录页互相弹的死循环。

## 4. 本地账号

- H5：`demo / welcome1`（`db/init.sql` 种子；`demo2` 用于越权对照）
- 小程序：需 `MP_APPSECRET` 才能换 openid；缺失时 `getOpenid` 返回 50001「云开发未配置」，**不会伪造 openid**

## 5. 批次记录

| 批次 | 覆盖映射表 | 走通路径 | 结果 |
|---|---|---|---|
| 1 | D-01/D-02/D-03/D-04/D-05/D-06/D-09/D-10/D-13/D-14/D-15/D-21/D-30 | `build:h5` → `build:mp-weixin` → `check:build` → `vue-tsc` → H5 五页走查 → 登录→表单→提交→我的 | ✅ H5/MP exit 0、check PASS、tsc 0；`walkthrough.json` 5 页 ok；`e2e_result.json` 提交 `No.66`、我的 15 条 |
| 2 | D-10 / D-30（视觉发散，功能不变） | `?v=A/B/C` 三版首页 → 375×812 全页截图 → 414 宽溢出测量 → 每条首项点击进详情 → 用户盲挑 A → A 版主循环 2 轮 + 空上下文评审 2 轮 → `build:h5` / `build:mp-weixin` / `check:build` | ✅ 三版同一数据、无横向溢出（375/414）；用户选定 A；A 版检测 0/0/0、评审 7→8（8<9 记 deferred）；截图 `evidence/design_variants/A_review2_after.png`，记录 `设计精修记录.md` |
| 3 | D-26 / D-27（隐私与小程序上传配置） | 隐私页进 `pages.json` → `manifest.__usePrivacyCheck__` → `App.vue` 启动隐私授权 → 预约提交前拦截 → H5 隐私页走查 + 我的页入口点击 | ✅ `vue-tsc` 0、H5/MP build exit 0、`check:build` PASS（页数 6）；`privacy_walkthrough.json` 标题/4 节/入口跳转 `#/pages/privacy/index`；**小程序首进弹窗与拒绝路径待体验版真机验证** |
| 4 | 5.5 返工：D-10 / D-15 / D-30 / D-31 + Q-014/015/016 | 分页（`onReachBottom`，`?size=N` 演示）→ 连点 5 次 E2E → 详情出血/遮挡/口径 → `design/annotations.md` + 两张 375 图 → 字段级红字 → 成功态拆组件、`App.vue` 去 `any` | ✅ `vue-tsc` 0、双端 build 0、`check:build` PASS；`e2e_pagination.json`（size=2→1→3 行）、`e2e_click5.json`（POST=1）、`rework_layout.json`（三档溢出 0 / 重叠 0 / 图位 1.25）；证据在项目 `05.5_代码Review/evidence/` |

`design/`：`annotations.md`（17 条 375 基准标注：标注值/实测值/偏差）+ `annotations-375.png`（编号标注层）+ `overlay-375.png`（24px 边距 / 72 与 144 网格 / 预约栏线）。
分页自测：首页支持 `?v=A&size=N`（N=1–50）覆盖每页条数，用于 4 条数据下的「加载更多」演示，默认 12。

证据目录 `evidence/`：`build_h5.log`、`build_mp.log`、`check_build.log`、`type_check.log`、`walkthrough.json`、`walk_{home,login,detail,form,my}.png`、`e2e_result.json`、`e2e_{1..4}_*.png`、`contract_check.log`；批次 2 追加 `design_variants/{A,B,C}.png` + `design_variants/variants.json` + `build_{h5,mp}_variants.log`、`type_check_variants.log`、`check_build_variants.log`。

> 实现说明：本套 uni-app（`3.0.0-alpha-5030720261117001`）不编译 `<style lang="scss">`，
> 因此 token 以 CSS 变量落地（`src/styles/tokens.css` + `base.css`），页面样式用 `var(--ub-*)`，双端一致。

## 6. Skill 遵守清单（5B · 批次 2）

已按 `skills/README.md` 对照表加载：`active/` 三件套 + 类型附加 `motion/emil-animations` + 精修附加 `distinctive-ai-design` / `motion-web`。

| Skill | 遵守 | 因项目约束未遵守 / 说明 |
|---|---|---|
| design-skill-master | 不居中 Hero、不三等价卡、无渐变/发光、无假数据纪念碑、无图标顶格；标题用宋体建立层级，不用 Inter 默认栈 | — |
| taste-skill | 一底（`#0E2B26`）一墨（`#F2EDE4`）一强调（`#C4453A` 仅状态）；纯平色、无阴影、无玻璃、无渐变；每段有标题、页边距一致；内容完整（4 套餐/价格/标签全上） | 「禁 01 编号 / 禁 1px 细线 / 禁等宽」三条未执行：`门面页方向稿.md` §2 明确把编号、装订细线、等宽数字作为方向 A 的核心语汇，step05B 冲突口径为「以 step02 为准」 |
| qiaomu-design | 先功能契约（看套餐→点详情→预约），一个主焦点，loading/error/empty 三态齐，中文排版优先，无 `transition: all` | 「禁编号式眉批」未执行，同上以 step02 为准 |
| distinctive-ai-design | 三版在构图/信息组织/交互隐喻上真正不同（账本 / 印样格 / 票根），遮住颜色仍可区分；真实运行截图作证；用户选择未由 AI 代做 | 空上下文评审 2 轮：7 → 8，8<9 按口径记 deferred；评审建议中「真图+渐变」「删编号/横线」「新增第三色」因无素材 / 方向稿约束未采纳，已在 `设计精修记录.md` 逐条写取舍 |
| motion-web | 先静帧后动效；三版在关掉动效时仍成立；无装饰性粒子/视差/整页 fade-up | `方向稿 §2.5` 两处动效（细线曝光、价格数字跳动）尚未实现，已在 `设计精修记录.md` §遗留 记为待选定版主循环补齐 |
| 视觉资产 | 照片位用 `#1B3A33` 中性空态：4:5 块 + inset 1px 内框 + `01 / 04` 角标，不写比例/张数规格，不伪造实拍、不伪造品牌素材 | 真实样片未到位，正式上线前替换；评审仍把「无真图」列为扣分项，已 deferred |
