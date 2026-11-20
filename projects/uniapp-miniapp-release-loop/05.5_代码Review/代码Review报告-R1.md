# 代码 Review 报告（第 5.5 步 · 独立上下文）

> 审查对象：`uniapp-miniapp-release-loop` 的 5A（后端 + 云函数）与 5B（前端）全部产物。
> Reviewer 上下文：**2026-11-19 新开的独立会话**，未参与 5A/5B 任何编码或调试；只读代码、实跑接口、独立截图。
> 审查基线：根仓库 HEAD `92fab2708f4f0826d908b82cff1750487ad84cad`（`approved_commit` 待「风险变更确认清单」确认后回填）。
> 只审不改：本步未改任何产品代码；唯一写操作是 `_设计实施映射表.md` 的 3 行状态降级与证据列。
> 证据目录：`05.5_代码Review/evidence/`（截图、实测 JSON、临时探针脚本）。
> 问题已全部回流 `_问题台账.md`（Q-004…Q-017，来源阶段=5.5）。

---

## 一、结论

**🔴 需返工（打回 5B，1 项连带 5A）。当前不得进入第 6 步。**

| 判定 | 说明 |
|---|---|
| 契约一致性 | ✅ PASS（`api_contract_validator.py check` exit 0，17 个前端调用全部命中契约；人工核对 path param 拼接正确） |
| 映射表 stage6 前置 | 🔴 7 条 ❌（`design_impl_check.py --stage 6` exit 1）：D-28/29/31/33/34/35/36 |
| 其中真正属 5A/5B 的 P0 | 🔴 **D-31（T-705 设计标注）从未实现**，`frontend/design/` 目录不存在 |
| 假 ✅ 实证 | 🔴 **D-30** 详情页 390 宽 `scrollWidth=414 > 390`；**D-10** 无分页加载更多；**D-15** 无「连点 5 次」用例 |
| 关键安全问题 | 🔴 **H5 直连可凭任意 openid 登录**（实测新建 userId=3） |
| 类型/构建 | ✅ `vue-tsc` exit 0；`check:build` PASS（H5 入口 + 6 页） |
| 设计审美（第四层） | ⚠️ 6.2/10：概念成立，但无真实样片（上限 6.5）+ 详情页溢出/遮挡/规格标注 |

> 结论口径：不是「写得差」，而是**两类问题**——① 一个 P0 设计项漏做（D-31）+ 3 行映射表 ✅ 与事实不符；② 一个鉴权信任链缺口（openid）。两类都必须回 5A/5B 补齐后再审。

---

## 二、Review 范围与方法

- 被审代码目录 / 模块：`05_代码/backend`（35 个 Java，重点 18 个）、`05_代码/cloud-functions`（8 个 JS）、`05_代码/frontend`（12 个 TS/Vue/JSON）、`db/init.sql`、`scripts/*.ps1`、`06.5_契约/openapi.json`。
- 对照基线：`01_项目基线说明书.md`、`02_架构设计/第二轮技术架构设计文档.md`、`04_任务拆解与开发规范.md`（风险级别列）、`_设计实施映射表.md`。

| 维度 | 方法 | 实际动作 |
|---|---|---|
| 需求正确性 | 映射表逐行对代码 + 抽跑 | 抽查 22 行（全部 P0 任务行 + 关键 P1），实跑 9 条接口链路 |
| 系统一致性 | 契约 / 字段 / 错误码 / 权限 / 命名 | `api_contract_validator`；4 组 DTO/VO 逐字段比对；6 个错误码实测；权限矩阵实测 |
| 回归 | 回归基线 + 并发/幂等/事务 | 查 `p0_cases.json`（不存在）；实跑幂等、越权、边界 |
| 健壮性 | 异常分支、空值、越权、外部依赖 | 读 `GlobalExceptionHandler`、`SignatureFilter`、MQ/缓存降级；G6 用例有效性核对 |

### 分维度检查（对照模板）

| 维度 | 检查要点 | 发现 | 严重级别 | 台账 ID |
|---|---|---|---|---|
| 需求正确性 | 实现是否与基线/契约一致，有无漏做、错做 | P0 标注漏做（D-31）；分页加载更多缺失（D-10）；备注 255 vs 设计 1000 | P1 / P2 | Q-005 / Q-007 / Q-010 |
| 系统一致性 | 命名/分层/复用/配置口径 | H5 直连 openid 不校验来源；幂等跨账号拿他人单；MP 硬编码 127.0.0.1 | P1 / P2 | Q-004 / Q-011 / Q-013 |
| 回归 | 是否破坏既有链路 | 无 `p0_cases.json`，可跑回归 0 条（新项目）；风险带入第 7/8 步 | — | — |
| 健壮性 | 异常分支、边界、空值、并发与越权 | 详情页横向溢出；首屏摘要被固定栏压；缓存无单飞；连点无用例 | P1 / P2 | Q-006 / Q-009 / Q-012 / Q-008 |

---

## 三、映射表复核结果

抽查 22 行，**3 行状态降级**（已直接改 `_设计实施映射表.md`），另 3 行补证据不改状态。

| 行 | 原状态 | 复核 | 证据 | 处理 |
|---|---|---|---|---|
| D-01 | ✅ | 成立 | 目录齐全；`check:build` PASS；`build_h5.log` 存在 | 保持 |
| D-02 | ✅ | 成立 | `check_build.mjs` 断 tabBar 2 项；实际页数已由 5 增至 6（映射表写 5 是旧值） | 保持，证据列注「页数 6」 |
| D-03/04 | ✅ | 成立 | 本次复跑 `check:build` PASS | 保持 |
| D-05 | ⚠️ | 保持 | `#ifdef` 仅 1 处（`request.ts:26`）；产物 `dist/build/mp-weixin/utils/*.js` 已裁 H5 分支；真机未验 | 保持 |
| D-06 | ⚠️ | 保持 + 补证 | **登录页密码错是表单级 `errMsg`（`login/index.vue:38,116`），不是字段级红字**；表单页 `form.vue:210-212` 才是字段级 | 补证据 |
| D-08 | ✅ | 成立 | 实测 `loginByAccount` → userId=1 / token 185 / expiresIn | 保持 |
| D-09 | ✅ | 成立 | `request.ts` 超时 3s + 失败重试 1 次 + 40103 清 session；H5 不带签名（已登记偏差） | 保持 |
| **D-10** | ✅ | **不实** | `index.vue:47-57` 只请求 `page=1,size=12`，全仓无 `onReachBottom`（grep 0 命中）；实测滚到底 4 行不变（`review_shots.json afterScroll.rows=4`） | **✅→⚠️** |
| D-11 | ⚠️ | 保持 + 补证 | `PackageService.java:69-86` 无 single-flight（并发 miss 各自回源）；命中率归第 8 步 | 补证据 |
| D-12 | ✅ | 成立 | 实测 `GET /api/packages/999` → 404/40401；`/api/no-such-path` → 404/40400 | 保持 |
| D-14 | ✅ | 成立 | 实测创建成功 bookingId=67，第二次 duplicated=true | 保持 |
| **D-15** | ✅ | **证据不足** | `form.vue` 有 `submitting` + disabled；但 `e2e_run2.txt` 只点 1 次提交，没有「连点 5 次」用例 | **✅→⚠️** |
| D-16 | ✅ | 成立 | `smoke_cf.txt` 18 项 PASS（5A 产出，签名/40102/超时/重试）；本次未重跑 | 保持 |
| D-17 | ⚠️ | 保持 + 补证 | 云函数 `exports.main` + `localServer` 双入口存在；**前端无 `callFunction` 分支**（grep 0 命中），MP 恒走 `http://127.0.0.1:8093` | 补证据 |
| D-18 | ✅ | 成立 | 实测两连发同 bookingId=67 | 保持 |
| D-19 | ✅ | 成立 | DB 4 表可用、种子 4 套餐/2 账号；本次查询正常 | 保持 |
| D-20 | ✅ | 成立 | `smoke_batch3.txt`；本次实测 40002/40001 边界文案正确 | 保持 |
| D-21 | ✅ | 成立 | `e2e_result.json` myList=15、首条 No.66、脱敏 `138****0001` | 保持 |
| D-22 | ✅ | 成立 | 实测 demo2 带 `?userId=1` → 返回自己 total=0；无 token → 401 | 保持 |
| D-23 | ✅ | 成立 | 实测 40400/40401/40001/40002 | 保持 |
| D-24 | ✅ | 成立 | 实测 40101 登录失败；logout 后 40103 | 保持 |
| D-26 | ⚠️ | 保持 | H5 隐私页走查 `privacy_walkthrough.json` 4 节 302 字、无溢出；MP 首进弹窗待真机 | 保持 |
| **D-30** | ✅ | **不实** | 首页 375/390/414 均无溢出；**详情页 390 实测 scrollWidth=414**（`.photo` 右溢 24px） | **✅→⚠️** |
| **D-31** | ❌ | **确认未实现** | `frontend/design/` 目录不存在；T-705 为 **P0**、5B 范围 | 保持 ❌，写证据 |
| D-32 | ⚠️ | 保持 + 补证 | 8092/8093/3308/6379/5672 全部 LISTEN，`/healthz` `secretConfigured=false`；5186 实测可渲染 | 补证据 |
| D-28/29/33/34/35 | ❌ | 归属 step8/10 | 提审材料/发布模板/双端差异表/兼容记录/隐私核对，按主控是第 8/10 步产物 | 保持 ❌，注「stage6 门禁口径冲突」 |
| D-36 | ❌ | 归属 step8 | pytest 分层用例，第 8 步产物 | 保持 ❌，同上 |

---

## 四、需求正确性（逐 P0 核验）

| 需求 | 设计出处 | 代码实现 | 实测 | 判定 |
|---|---|---|---|---|
| 套餐列表/详情只读、下架不返回 | D-10/D-12 | `PackageService.loadAll()` 只取 `findAllActive` | 200 / 4 套餐 / 404 | ✅ |
| 手机号脱敏、状态文案 | D-21 | `BookingItem.contactMasked/statusText` | `138****0001`「待确认」 | ✅ |
| 30 天窗口 / 时段三选 | D-20 | `BookingService` 校验 + `BookingRequest` | 40002「2026-11-19 ~ 2026-12-19」；40001「上午/下午/晚间」 | ✅ |
| 幂等：同手机号+同日+时段只 1 单 | D-18 / R-02 | Redis 键 + DB 唯一键 `uk_booking_contact_date_slot` | 两连发 bookingId=67 duplicated=true | ✅ |
| 无 token 不能看/写「我的」 | D-22 | `JwtAuthFilter` 保护 `/api/bookings*`、`/api/auth/logout` | 401 | ✅ |
| 越权参数被忽略 | §6.3 | `findPageByUser` 只用 token userId | demo2 + `userId=1` → 0 条 | ✅ |
| 未注册路由 | D-23 | `40400` | 404 | ✅ |
| 套餐缓存 300s | D-11 | `LIST_KEY` + TTL | 接口正确；无单飞 | ⚠️ |
| 列表分页加载更多 | T-303 验收 | 无 | 滚到底仍 4 行 | **❌** |
| 连点 5 次只 1 次请求 | T-406 验收 | 前端 disabled，但缺用例 | 未验证 | **⚠️** |
| 设计标注 375 基准 ≥10 条 | T-705（P0） | 无 `design/` | 目录不存在 | **❌** |
| 备注 1000 字 | 设计 §8 | `@Size(max=255)` + 云函数 255 + 前端 255 | 三端一致，但与设计不符 | ⚠️ |
| 表单草稿本地恢复 | 设计 §7 | 无 `setStorage` 草稿逻辑 | — | ⚠️ |
| 首页轮播 | D-13 | 无 `swiper` | 占位图位 | ⚠️（已登记） |

**结论**：主链路（登录→列表→详情→下单→我的）全部正确；缺「加载更多」「连点用例」「标注」与 3 处口径偏差，均属实、非虚报。

---

## 五、系统一致性

| 检查项 | 结果 | 证据 |
|---|---|---|
| 契约 vs 前端调用 | ✅ 17 个调用全部命中 6 个操作；脚本把 `/api/packages/{id}` 归并为 `/api/packages`，人工核对 `api/index.ts` 拼 `/api/packages/` + id 正确 | `api_contract_validator check` exit 0 |
| 字段命名 | ✅ `PackageVO`、`BookingItem`、`LoginData`、`BookingCreateData` 与 `types.ts` 逐字段一致 | 4 组 DTO 对读 |
| 错误码 | ✅ 6 个码实测一致：40001/40002/40101/40103/40400/40401；`errors.js` 与 `ErrorCode.java` 同名同值 | 本次 curl |
| 鉴权链 | 🔴 **H5 直连 `POST /api/auth/login {openid}` 不带签名即成功建号**（实测 userId=3）。`AuthService:59 loginByOpenid` 只校验非空；`SignatureFilter` 对 H5 无签名放行 → openid 可伪造，知他人 openid 即可登录其账号读预约 | 实测 + `SignatureFilter:52` |
| 权限矩阵 | ✅ 游客只读套餐/登录；普通用户写需 JWT、读按 userId 过滤；⚠️ admin 角色无种子账号/后台入口（demo 未实现） | 实测 + `init.sql` |
| 单点定义 | ⚠️ 文案层「套餐」与「档期」混用（首页 tab、详情页眉、后端 msg），同对象两种叫法；不影响功能 | `index.vue` / `detail.vue` |
| 异常兜底 | ⚠️ MQ 发布失败只 log、不回滚、无 outbox（已登记）；缓存 miss 无单飞；H5 无签名（取舍） | 代码对读 |
| 过滤链顺序 | ✅ `SignatureFilter` → `JwtAuthFilter`；OPTIONS 两处均放行；nonce 120s 去重 + 验签后才 SETNX | 代码对读 |

---

## 六、回归、并发与测试有效性

### 6.1 回归基线

- `p0_cases.json` **不存在**（第 8 步才产出）；新项目、5A/5B 未改老逻辑。→ 本次回归**可判定条目 0 条**，风险带入第 7/8 步，**不得解释为回归通过**。

### 6.2 并发 / 幂等 / 事务

| 点 | 结论 | 证据 |
|---|---|---|
| 幂等短路 + DB 唯一键 | ✅ 逻辑成立；Redis 不可用降级 DB 唯一键 | `BookingService:118-135` + `init.sql` |
| SETNX 占位不判返回值 | ✅ 不构成 bug（DB 唯一键兜底） | 同上 |
| 幂等命中不校验 userId | ⚠️ 同手机号被另一账号提交 → 返回**首单（属他人）**的 bookingId/status，且不在自己列表 | `BookingService:120-127` + `idemKey` 不含 userId |
| 事务边界 | ✅ 单表 INSERT 自动提交；publish 在事务外，失败不回滚主流程（符合设计） | 代码对读 |
| 异步失败兜底 | ⚠️ 无 outbox；消费者重试 3 次 + DLQ（已登记 P2） | `NotifyConsumer` / `RabbitConfig` |
| 缓存并发回源 | ⚠️ 无 single-flight（设计写了「单飞」） | `PackageService:69-86` |

### 6.3 G6 · 测试有效性（断言 vs 验收标准）

| 用例 | 断言 | 真绿/假绿 | 结论 |
|---|---|---|---|
| `e2e_booking.cjs` 登录 | URL 跳转 + `ub_token` 185 + `meName=演示用户A` | **真绿**（业务字段） | 采纳 |
| 同脚本 提交 | `.done-no` 文本 + `.done-note` 状态 + `err` 为空 | **真绿** | 采纳 |
| 同脚本 我的 | `.booking` 条数 15 + 首条含「No.66 待确认 城市轻写真 2026-11-19 · 下午 · 138****0001」 | **真绿** | 采纳 |
| 同脚本 连点 | **无用例**：只 `click('.submit')` 一次 | **无覆盖** | Q-008，T-406 需补 |
| `check_build.mjs` | H5 入口 + MP 页数 6 + tabBar | **真绿**（断产物） | 采纳 |
| `smoke.ps1` | 只断 HTTP 200 / code=0 | 口径宽（冒烟性质） | 不作验收证据 |
| 50001 / 42901 | 无任何用例 | **0 条**（映射表未标 ✅，无假绿） | 归第 8 步 |
| 伪造 userId 越权 | 无用例 | — | 本次人工实测，建议转第 8 步用例 |

### 6.4 本次实跑清单（非伪证）

| # | 请求 | 结果 |
|---|---|---|
| 1 | `POST /api/auth/login demo/welcome1` | 200 code=0 userId=1 token 185 |
| 2 | `GET /api/packages?page=1&size=10` | 200 total=4 |
| 3 | `GET /api/packages/2` | 200 |
| 4 | `GET /api/packages/999` | 404 40401 |
| 5 | `GET /api/bookings`（Bearer） | 200 total=15 |
| 6 | `POST /api/bookings`（13900001234） | 200 bookingId=67 duplicated=false |
| 7 | 同 payload 再发 | 200 bookingId=67 duplicated=true |
| 8 | `bookDate=2026-10-01` | 400 40002 |
| 9 | `slot=凌晨` | 400 40001 |
| 10 | 无 token `GET /api/bookings` | 401 |
| 11 | `/api/no-such-path` | 404 40400 |
| 12 | demo2 + `?userId=1` | 200 total=0（隔离生效） |
| 13 | H5 直连 `{openid:"oREVIEWfake..."}` | 200 userId=3 建号（**缺陷证据**） |

> 副作用：DB 新增 1 条评审数据（bookingId=67 / 13900001234 / 备注「REVIEW-5.5 独立评审抽跑」）与 1 个 openid 账号（userId=3）。第 7.5 步重置一并清；本次未擅自动库。

---

## 七、风险变更确认清单（5.5 → 第 6 步的人工卡点）

> 按第 4 步风险级别列，以下模块属「关键 / 高」。5.5 无关键项 → 可直接进第 6 步；**有关键项 → 必须用户逐项确认，未确认前不得进第 6 步**。
> `approved_commit` 待填：**`92fab2708f4f0826d908b82cff1750487ad84cad`**（当前 HEAD）。后续新 commit 审批自动作废、需重审。

| # | 变更内容（文件:行） | 影响面（数据/安全/外部接口/部署） | 4 步风险级别 | 结论 |
|---|---|---|---|---|
| 1 | JWT 签发/校验 + 黑名单 `JwtService` / `JwtAuthFilter` / `RedisTokenStore` | 全站访问控制；密钥泄露=全站失守 | 关键（T-203/T-501） | 需确认 |
| 2 | HMAC 验签 + nonce 去重 `SignatureFilter:52-110` | 云函数→后端唯一信任通道 | 关键（T-204） | 需确认 |
| 3 | **openid 登录 `AuthService:59`** | 微信身份映射；当前可伪造 | 关键（T-205） | **需先修，再确认** |
| 4 | 云函数反代 `apiProxy` + `proxyHandler`（超时/重试/错误映射） | 小程序唯一数据通道 | 关键（T-206） | 需确认 |
| 5 | **Schema：`user.password_hash` 新增**（架构 §5 漏列） | 生产库需迁移；无回滚脚本 | 关键（T-401） | 需确认 |
| 6 | 幂等键 + 唯一键 `uk_booking_contact_date_slot` | 重复预约/脏数据 | 关键（T-402） | 需确认（含跨账号口径） |
| 7 | 预约写库 + 事件发布 `BookingService:60-110` | 用户数据写入；MQ 失败不回滚 | 高（T-403/T-404） | 需确认 |
| 8 | 启停脚本 `start_all.ps1` / `stop_all.ps1`（docker start 共享容器、Stop-Process） | 生产部署；误启/误杀共享实例 | 关键（T-701） | 需确认 |
| 9 | 默认 `APP_SECRET` / `JWT_SECRET`（`application.yml` 与 `config.js` 一致可跑） | 生产必须由 `.env` 覆盖；默认值≈无鉴权 | 关键（8.5） | 需确认「8.5 前必须换」 |
| 10 | H5 直连放行（无签名）+ dev CORS 只放 5186 | 公网暴露面 | 高（T-207 / 8.5） | 需确认 |

**请回复格式**：`5.5 关键项确认：1-10 全部同意，approved_commit=92fab27`（或逐项列出不同意项）。若第 3 项要求先修，回复 `3 修完再确认`。

---

## 八、第四层 · 设计审美（设计模式=精修）

依据：`taste-skill/references/critique.md` 十四遍 + `design-skill-master` 十条 tell；截图在 `05.5_代码Review/evidence/`。

```
ROUND 1（390 × 844，H5 dev 5186：套餐 1 首页 + 套餐 3 详情）
Seen in one second: 「城市轻写真」——一个宋体大字 + 一块暗绿照片位。
Idea (one sentence): 一本影像工作室的档期账本（No. 编号、细横线、印样角标、朱红「剩 2 档」）。
Live thing: 每天变化的「剩 N 档」与真实档期表（数据来自后端）。
Layout words by section: hero=editorial-split / 照片位=full-bleed-block / 清单=ledger-list / footer=colophon
Scores: design 6 · usability 6 · creativity 7 · content 6 → overall 6.2
Caps applied: ① 无真实照片（0 张，仅纯色图位）→ design ≤6.5；② 01/02/03 编号大量出现（No.01 / 01–04 行号 / 01/04 角标）→ overall ≤6.5；③ 详情页横向溢出 + 首屏摘要被固定栏压住 → usability ≤6；④ 有意空态仍是纯色块 → content ≤6。
Top three problems（按可见度）:
1. 详情页照片位右溢 24px（`review_detail_390.png` / `review_detail3_390.png`）：`.photo` 左起 24、右到 414，屏幕上被切；根因 `detail.vue:152` 的 `margin: … (calc(var(--gutter) * -1))` 多了一层括号，整条 margin 声明失效（H5 与 mp-weixin 产物同样失效，`detail.wxss` 原文可见）。修法：`margin: var(--sp-3) calc(var(--gutter) * -1);` 或拆 `margin-left`。
2. 详情首屏「说明」被底部固定预约栏盖住 51px（`probe_collision`：summary 781–832 vs bar 763–844），滚动到底才露出。修法：把 bar 高度计入首屏 padding-bottom，或把说明上移到图片位之前。
3. 照片位右下写「样片 4:5」（`detail.vue:183`），与 5B 评审第 1 轮已改的「不写比例/张数规格」自相矛盾；首屏 hero 与清单第一行重复同一套餐（「城市轻写真 ¥399」两次），削弱清单递减节奏。
次要：标题 34px / 正文 15px = 2.3 倍，未到 critique 的 3 倍判据；页脚前约 90px 空白偏大。
```

> 6.2 是**被真实素材缺失与编号体系封顶**的结果，不是执行粗糙。概念（暗房账本）在 hero、清单、详情、页脚四处一致；无渐变/玻璃/阴影/图标顶帽；朱红只用于「剩 2 档」。补真实样片 + 修溢出后可到 7 段。

---

## 九、误报与「已确认不修」

| 项 | 复核结论 | 理由 |
|---|---|---|
| H5 不带签名 | **不修**（设计取舍） | 浏览器不能持 `APP_SECRET`；H5 只读 + JWT 写 |
| 读他人单不返 40301 而返回自己 | **不修** | 不泄漏数据；语义与设计不同，已登记 |
| `42901` 无限流触发路径 | **不修（demo）** | 无管理端；第 8 步不做假触发 |
| admin 角色无种子 | **P3 不修** | demo 不提供后台；设计 §6.3 保留 |
| `smoke.ps1` 只断 200 | **不修** | 定位是冒烟，不是验收 |
| `NotifyConsumer` javadoc `@throws IllegalException` | **P3** | 笔误，无该类；文档瑕疵 |
| `form.vue` 427 行 > 规范 400 行 | **P3** | 规范偏差，非功能问题 |
| `App.vue` 3 处 `any` 无 eslint-disable 注释 | **P3** | 规范偏差 |
| D-28/29/33/34/35/36 在 stage6 报 ❌ | **非 5B 责任** | 主控把提审材料/兼容记录/隐私核对放第 10 步、pytest 放第 8 步；`design_impl_check --stage 6` 不区分归属，属**工作流规则冲突**，归 step11 |

---

## 十、返工清单（打回 5B，1 项连带 5A）

### 5B（必须，按顺序）

1. **D-31 / T-705（P0 漏项）**：补 `05_代码/frontend/design/annotations.md`（≥10 条实测偏差，目标文件:行 + 实测值 vs 标注值）+ `annotations-375.png` + `overlay-375.png`，基准取 375。
2. **D-30 详情页出血修复**：`detail.vue:152` 改合法 margin 写法；确认 `aspect-ratio` 在 mp-weixin 的兼容写法（可改 `padding-top` 4:5 或 `height:125vw` 兜底）。修后 375/390/414 三档对首页 + 详情各测 `scrollWidth`。
3. **D-10 分页加载更多**：`index.vue` 加 `onReachBottom` + `hasMore/page` 状态，追加而非覆盖；保留下拉刷新与骨架。
4. **D-15 连点用例**：E2E 加「连点 5 次」步骤并计 `POST /api/bookings` 次数 = 1，落 `evidence/e2e_click5.txt`。
5. **详情页遮挡**：底部栏高度与 `padding-bottom` 对齐，首屏不得压住「说明」正文。
6. **口径清理**：删 `detail.vue:183`「样片 4:5」；首屏 hero 与清单首项二选一（建议清单从第 2 项起，或 hero 只留图/不重复价格）。
7. **我的列表分页**（P2，可与 3 同批）：`my/index.vue` 加 `hasMore` + `onReachBottom`（>20 单场景）。
8. **注释规范**：`form.vue` 拆到 ≤400 行；`App.vue` 的 `any` 补 `eslint-disable` 理由。

### 5A（必须，先于第 6 步）

9. **openid 信任链（关键）**：`AuthService:44-70` 要求「带 openid 的登录」必须具备云函数签名（`X-Client: cloud` 且验签通过），或改「getOpenid 签发一次性 ticket → 后端换 token」；否则 H5 直连可伪造 openid 冒充。
10. **幂等跨账号口径（P2，可同批）**：命中后校验 `row.userId == userId`；不一致不得返回该单（改为新建或 40001 提示“该手机号当日该时段已有预约”）。
11. **缓存单飞（P2）**：`loadAll()` miss 分支加分布式锁或 `synchronized` 双检。

### 5A/5B 协同（外部依赖，归 step9 判定卡）

12. **体验版通道**：小程序产物硬编码 `127.0.0.1:8093/8094`（`dist/.../utils/env.js`），真机/体验版不可用，且前端无 `callFunction` 分支。补「cloud 分支 + 公网域名配置」代码骨架；真实可用仍取决于云开发开通/域名备案（C07–C09），不得伪造。

### 工作流（归 step11）

13. `design_impl_check --stage 6` 把第 8/10 步产物一律判 ❌，与主控顺序冲突；建议按「步骤归属」过滤或分 stage 6/8/10 三档。

---

## 十一、回归与结论

- 回归验证方式：13 条接口实测（`05.5_代码Review/evidence` 外的终端输出，报告 6.4 节逐条留痕）+ `api_contract_validator check` + `vue-tsc` + `check:build` + 两档独立截图；`p0_cases.json` 不存在 → 回归可判定 0 条。
- **Review 结论：不通过（🔴 打回 5B）**。D-31 P0 漏做、D-30 实证溢出、openid 信任链可伪造，三条属实质性阻断；其余 P2/P3 随批修。
- 遗留项归属：Q-004/005/006 为 **P1 必修**（阻塞第 6 步）；Q-007…Q-013 **P2** 随 5B/5A 同批；Q-014…Q-016 **P3** 顺手修；Q-017 **工作流冲突**归 step11。
- 重审要求：修完后**换新上下文 reviewer** 复测（详见 §十一 下一步）。

### 下一步

1. 用户先回 §七「5.5 关键项确认」（10 项，含 `approved_commit`）。
2. 5B 返工 1–8、5A 返工 9–11 完成后，由新上下文 reviewer 重审本步（重点：详情 3 档 overflow、连点 5 次、design 目录、openid 伪造）。
3. 重审通过（映射表 P0 行全 ✅ 且证据在位）→ 进第 6 步本地冒烟。

---

## 附 · 证据索引

| 文件 | 内容 |
|---|---|
| `evidence/review_home_390.png` / `review_home_375.png` | 首页两档独立截图 |
| `evidence/review_detail_390.png` / `review_detail3_390.png` | 详情页截图（右溢可见） |
| `evidence/review_detail3_bottom.png` | 详情滚到底截图 |
| `evidence/review_shots.json` | 首页/详情/滚到底/375 实测数值 |
| `evidence/probe_overflow.cjs` | `.photo` left=24 / right=414 定位脚本 |
| `evidence/probe_collision.cjs` | 摘要 781–832 与 bar 763–844 重叠 51px |
| `evidence/review_shots.cjs` | 本步临时截图脚本（不进产品代码） |
