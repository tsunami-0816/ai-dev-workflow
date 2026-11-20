# 第 5.5 步 独立代码 Review 报告 · R2 复审

> 审查对象：`uniapp-miniapp-release-loop` 5A/5B 全部产物 + 2026-11-20 返工 diff。
> Reviewer 上下文：**2026-11-20 新开会话**，未参与 5A/5B 编码、未参与本轮返工实施；全程只读源码 + 自己写独立探针实跑，**未改任何产品代码**。
> R1 报告原文归档在 `05.5_代码Review/代码Review报告-R1.md`（14 项 Q-004～Q-017 的原始判定）。
> 审查基线：**工作区快照**。`projects/uniapp-miniapp-release-loop/` 在根仓库仍是 untracked，HEAD `92fab2708f4f0826d908b82cff1750487ad84cad` 并不包含本项目代码（见 §七）。
> 本次新增证据：`evidence/r2_probe_api.{mjs,txt}`、`r2_login_field_err.{cjs,json,png}`、`r2_cache_singleflight.cjs`、`r2_cache_evidence.txt`；复跑覆盖 `e2e_pagination.json`、`e2e_click5.json`、`rework_layout.json`。

---

## 一、结论

**🟢 通过（代码层），附 1 项工具口径备注。0 项新 P0/P1，0 条返工项残留。**

| 判定项 | 结果 |
|---|---|
| R1 的 11 条 `fixed` 是否可信 | ✅ **11/11 全部转 `verified`**（逐条实跑，见 §三） |
| 新引入的 P0/P1 | ✅ **0** |
| 新增 P3 | 2 条（Q-019 文档细节不实、Q-020「我的」分页缺 UI 用例） |
| 5.5 机器闸门（协议口径） | ✅ `design_impl_check --stage 4` exit 0（`WORKFLOW_卡点协议.md:46` ④） |
| `design_impl_check --stage 6` | ❌ exit 1，6 条 ❌ **全部为 step8/10 交付物**（D-28/29/33/34/35/36），非 5A/5B P0 → 不构成打回依据，归 Q-017 |
| 类型/构建 | ✅ `vue-tsc` exit 0；`build:h5`/`build:mp-weixin` exit 0；`check:build` PASS（6 页） |
| 契约一致性 | ✅ `api_contract_validator check`：4 个调用 0 个不在契约 |
| 风险变更确认 | ⏳ 关键/高 10 项**待用户确认**（§六），未确认不得进第 6 步 |

> 结论口径：本轮**没有发现新的实质缺陷**；R1 打回的三条阻断（openid 可伪造、详情页出血、P0 标注漏做）均已实测收口。剩下的都是文档级细节与一条测试覆盖缺口（P3）。

---

## 二、复审方法（本次实跑清单，全部为 reviewer 自己执行）

| # | 命令 | 结果 | 证据 |
|---|---|---|---|
| 1 | `npm run type-check`（frontend） | exit 0 | 终端输出 |
| 2 | `npm run build:h5` / `build:mp-weixin` / `check:build` | 三个 exit 0；PASS 6 页 | 终端输出 |
| 3 | `python scripts/design_impl_check.py <项目> --stage 4` | exit 0 | 终端输出 |
| 4 | `python scripts/design_impl_check.py <项目> --stage 6` | exit 1，`✅17 / ⚠️13 / ❌6` | 终端输出 + §四 |
| 5 | `python scripts/api_contract_validator.py check 06.5_契约/openapi.json 05_代码/frontend/src` | 4 调用全命中，0 漂移 | 终端输出 |
| 6 | `node evidence/r2_probe_api.mjs`（自写，13 断言） | **13/13 PASS** | `r2_probe_api.txt` |
| 7 | `node scripts/rework_layout_check.cjs`（复跑） | 375/390/414 溢出 0、遮挡 0、比例 1.25 | `rework_layout.json` |
| 8 | `node scripts/e2e_click5.cjs`（复跑） | 5 次点击 → **POST=1**，pass=true | `e2e_click5.json` |
| 9 | `node scripts/e2e_pagination.cjs`（复跑） | size=2 → 1 行 → 翻页 → 3 行，pass=true | `e2e_pagination.json` |
| 10 | `node evidence/r2_login_field_err.cjs`（自写） | 口令字段红字「账号或密码不正确」，无表单级 err、无 token | `r2_login_field_err.json/png` |
| 11 | 清 `ub:pkg:list` → 并发 20 请求 + `Com_select` 前后差 | 20/20 成功；**DB SELECT 增量 = 2**（无单飞应≈20）；TTL=300 | `r2_cache_evidence.txt` |
| 12 | 未签名 openid 前后 `users` 计数 | 401/40102 ×3 次，users **5 → 5（0 新建）** | 终端输出 |

**与实施侧自测的差异**：R1 只看到「写了断言」，本次不看其自评，全部重跑；另外补了三项 R1/返工记录没覆盖的证据（口令字段红字独立截图、单飞用 DB 计数而非「接口 200」、无签名登录前后用户数对比）。

---

## 三、R1 11 条 `fixed` → `verified` 逐条核实

| 台账 | 原判 | 复核方式（文件:行 / 命令） | 实测 | 结论 |
|---|---|---|---|---|
| Q-004 openid 信任链（P1） | fixed | `SignatureFilter.java:78-105`（无签名放行仅写 `verifiedCloud=false`；声明 cloud 缺签名→40102；验签通过→true）；`AuthService.java:47-49` 强制 | 自写探针 T1/T2/T3 = 401/40102（无签名、只声明 cloud、错签）；T4 正确签名 200；三次失败尝试后 `users` 5→5 | ✅ verified |
| Q-005 设计标注（P1） | fixed | `frontend/design/annotations.md`（17 条：首页 8/详情 6/表单 3，含标注值/实测值/偏差）；两张 375 图 | 目录存在；`rework_annotations_375.png` 目视确认为真实标注层（24px 边距线、72/144 网格、10 条数值面板）；非零偏差 2 条，最大 |0.733| 为字阶比（<8px 判据） | ✅ verified（细节扣分见 Q-019） |
| Q-006 详情出血（P1） | fixed | `detail.vue:145-157`：`width: calc(100% + var(--gutter) * 2)` + `height: 125vw` + 合法 `margin: var(--sp-3) calc(var(--gutter) * -1)` | 375/390/414 三档 `scrollWidth = clientWidth`（375/375、390/390、414/414）；图位 x=0、右=视口宽；比例 1.250 | ✅ verified |
| Q-007 分页（P2） | fixed | `index.vue:44-97`（page/hasMore/onReachBottom 追加去重）；`my/index.vue:77-142` 同口径 | 复跑 `e2e_pagination`：`beforeRows=1 → afterRows=3`、`page=2&size=2` 真实发出；API 侧 T10：`page=2&size=2` 返回 2 行 / total=4 | ✅ verified（「我的」缺 UI 用例 → Q-020） |
| Q-008 连点 5 次（P2） | fixed | `scripts/e2e_click5.cjs`（`page.on('request')` 计 `POST /api/bookings` 次数，判定 `posts.length===1 && doneNo`） | 复跑：`clicks=5, postCount=1, pass=true` | ✅ verified |
| Q-009 首屏遮挡（P2） | fixed | `detail.vue` 模板顺序：`说明(28-32)` 在 `photo(36)` 之前；`.ub-page` padding-bottom 112px | 复跑：说明 y238–367 / bar 顶 763 → `overlap=0`（三档均 0） | ✅ verified |
| Q-011 跨账号幂等（P2） | fixed | `BookingService.java:78,120-152`：`lookupByKey` + `ensureOwner`；`DuplicateKeyException` 分支同样校验 | 探针 T7/T8：demo2 同手机号同日同时段 → 400/40001 且**无 data**；T9 demo 同参 → duplicated=true 且同 bookingId | ✅ verified |
| Q-012 缓存单飞（P2） | fixed | `PackageService.java:69-98`：`readCache` 预热 → `synchronized(loadLock)` 二次确认 → 回源 | 清 key 后并发 20 请求：20/20 成功，**Com_select 增量 2**（对照无锁≈20），TTL=300；Redis 异常降级分支为代码级 | ✅ verified（单实例锁；多实例留 v1.1） |
| Q-014 字段级红字（P3） | fixed | `pages/login/index.vue:24,37,105-126`：`errors.account/password`，40101 落口令字段 | 自写 E2E：`口令 → fieldErr="账号或密码不正确"`、表单级 `formErr` 为空、无 token；截图 `r2_login_field_err.png` | ✅ verified |
| Q-015 口径矛盾（P3） | fixed | `detail.vue` 全文无 `.photo-note` / 「样片 4:5」 | `specTextPresent=false`（三档一致）；grep `样片 4:5`=0、`photo-note`=0 | ✅ verified |
| Q-016 规范（P3） | fixed | 成功态外移 `components/BookingDone.vue`；`form.vue` 实际 **381 行**（≤400）；`App.vue` 无 `any` | grep `: any` = 0；`form.vue` 381 行（返工记录写 330，见 Q-019）；`vue-tsc` 0 | ✅ verified（记录数值不实，不返工） |

---

## 四、机器闸门口径（必须写清楚，避免下一位 Agent 误判）

`design_impl_check --stage 6` 报红 6 条，逐条核对后**全部不属于 5A/5B 代码**：

| 行 | 内容 | 真实归属 |
|---|---|---|
| D-28 | 提审材料清单 | 第 10 步交付 |
| D-29 | 发布/回滚记录模板 | 第 10 步交付 |
| D-33 | 双端差异表 | 第 10 步交付 |
| D-34 | 浏览器兼容对照 | 第 9/10 步（含 `06_冒烟/前端UI质量报告.md`） |
| D-35 | 隐私一致性核对表 | 第 10 步交付 |
| D-36 | pytest 分层测试套件 | 第 8 步 |

- **不构成 5.5 打回**：脚本把「还没到交付/测试阶段的行」也按 ❌ 计数，这 6 条不是 P0 功能缺失，也不是 5A/5B 漏做（R1 已把它们判为「归属 step8/10」，Q-017）。
- **不构成 5.5 通过条件缺失**：`WORKFLOW_卡点协议.md:46` 规定的 5.5 闸门是 `--stage 4`，本次 **exit 0**。
- **但它确实是第 6 步的隐患**：任何沿用 `--stage 6` 的地方都会红。Q-017 仍 `open`（归 step11），建议在那之前，第 6 步的入口检查继续用 `--stage 4`，或给脚本加「计划阶段」过滤（属改门禁脚本，Agent 不自行执行）。

---

## 五、测试有效性（G6）

| 用例 | 断言打的是什么 | 是否只断 200/mock | 结论 |
|---|---|---|---|
| `e2e_click5.cjs` | 网络层 `POST /api/bookings` 计次 + 成功态 `.done-no` 文本 | 否（真实请求计数） | 真绿，采纳 |
| `e2e_pagination.cjs` | 行数变化（1→3）+ 实际请求 `page=2&size=2` | 否 | 真绿，采纳 |
| `rework_layout_check.cjs` | `scrollWidth/clientWidth`、`getBoundingClientRect().bottom/top`、`computedStyle` 字号、`photoRatio` | 否（DOM 实测值） | 真绿，采纳（唯一缺陷是 `specTextPresent` 只判断元素存在，已配合 grep 交叉验证） |
| `r2_probe_api.mjs`（本次新增） | 业务字段：userId、bookingId、duplicated、total、page、data 是否泄漏 | 否 | 真绿，采纳 |
| `r2_cache_singleflight.cjs` | `Com_select` 全局计数增量 | 否（DB 侧计数） | 真绿，采纳 |
| `r2_login_field_err.cjs` | 字段级 `err-field` 文本 + 无 token | 否 | 真绿，采纳 |
| `smoke.ps1` | 只断 HTTP 200 / code=0 | 是 | 仍按 R1 口径：冒烟性质，不作验收证据 |

遗留覆盖缺口：**「我的」列表分页（>20 单）没有滚到底 UI 用例**（Q-020，P3，归第 8 步）。

---

## 六、风险变更确认清单（5.5 → 第 6 步的人工卡点）

> 依据 `04_任务拆解与开发规范.md` 风险级别列。命中「关键/高」→ 必须用户逐项确认，未确认不得进第 6 步。
> **R1 的第 3 项（openid 可伪造）已修复并 verified**，确认时按修复后的代码为准。

| # | 变更内容（文件:行） | 影响面 | 风险级别 | 本轮复核 |
|---|---|---|---|---|
| 1 | JWT 签发/校验/黑名单 `JwtService` / `JwtAuthFilter` / `RedisTokenStore` | 全站访问控制 | 关键 | 未变，无 token→401、登出→40103 实测仍成立 |
| 2 | HMAC 验签 + nonce 去重 `SignatureFilter:72-107` | 云函数→后端唯一信任通道 | 关键 | **本轮有改动**（新增 `verifiedCloud` 属性 + 声明 cloud 必须带签名）；T1/T2/T3 均 40102 |
| 3 | openid 登录 `AuthService:41-53` | 微信身份映射 | 关键 | **已修**：非验签来源 40102「仅允许经小程序云函数发起」 |
| 4 | 云函数反代 `apiProxy` + `proxyHandler` | 小程序唯一数据通道 | 关键 | 未变；8093 本轮未起（见 §八环境偏差） |
| 5 | Schema：`user.password_hash` 新增 | 生产库需迁移、无回滚脚本 | 关键 | 未变，仍待确认 |
| 6 | 幂等键 + `uk_booking_contact_date_slot` | 重复预约/脏数据 | 关键 | **语义收紧**：跨账号改为 40001，不再返回他人单（Q-011） |
| 7 | 预约写库 + 事件发布 `BookingService:66-174` | 用户数据写入；MQ 失败不回滚 | 高 | 未变；本轮 MQ 未起，写入成功、publish 失败仅 ERROR |
| 8 | 启停脚本 `start_all.ps1` / `stop_all.ps1` | 部署；误启/误杀共享实例 | 关键 | 未变 |
| 9 | 默认 `APP_SECRET` / `JWT_SECRET`（`application.yml` 与 `config.js` 一致可跑） | 生产必须 `.env` 覆盖；默认值≈无鉴权 | 关键（8.5） | **本轮实测确认风险仍在**：无 `.env`，后端用默认 secret；`/healthz` `secretConfigured=false` |
| 10 | H5 直连放行（无签名）+ dev CORS 只放 5186 | 公网暴露面 | 高 | 未变；H5 仍不能凭 openid 登录（第 3 项已闭合，仅剩 account 登录） |

**请回复格式**：`5.5 关键项确认：1-10 全部同意；approved_commit=<方案A新SHA / 方案B不绑定>`（或逐项列出不同意项）。

---

## 七、`approved_commit` 处置（需用户拍板，Agent 不擅自 commit）

现状：`git rev-parse HEAD` = `92fab27`，而 `git status` 显示 `?? projects/uniapp-miniapp-release-loop/` —— **本项目目录整体 untracked**，HEAD 不含任何本项目代码。因此 `approved_commit=92fab27` 语义是假的（R1 已提出，本轮再次确认）。

| 方案 | 做法 | 代价 | 建议 |
|---|---|---|---|
| A | 现在只把该项目目录纳入 git 并做一次基线提交（`git add --all projects/uniapp-miniapp-release-loop`，试算 **269 个文件**，不含 node_modules/target），`approved_commit`=新 SHA | 往用户仓库新增 1 个提交（可回退） | **推荐**：审批从此绑定真实快照；后续返工自动作废审批（符合 G5） |
| B | 不提交，`approved_commit` 填 `—`，改绑「工作区快照 + 证据文件清单」 | 审批无 commit 锚点，后续任何改动无法自动判「审批作废」 | 仅当用户不想动 git 时用 |
| C | 完全不绑定，等第 10.5 步 push 时再补 | 第 6–9 步全程无审批锚点 | 不推荐 |

---

## 八、环境偏差与副作用（复审按此复核）

1. MySQL 用本机原生 **3307**（文档写 3308 容器）；库 `uniapp_booking` 4 表/4 套餐/2 账号正常。
2. RabbitMQ **5672 未启动**：预约写入成功、publish 失败仅记 ERROR，`notify_log` 无新增（不影响 5.5 代码判定；第 6/7 步需恢复后复测）。
3. 云函数 **8093 未启动**：openid 正向用例由 reviewer 探针直算 HMAC 打 8092（算法与 `shared/signer.js` 一致）；8093 的 18 项冒烟为 5A 旧证据，本轮未重跑。
4. H5 dev **5186** + 后端 **8092** 本轮实跑在用；状态看板记录的服务未关闭。
5. **副作用（第 7.5 步重置时一并清）**：reviewer 探针新增预约 2 条（`bookingId=4/5`，手机号 13800000009 与 139…，备注 `R2 reviewer probe`）；openid 账号 1 个（`userId=5`，openid `oR2PROBEfake_openid_003`，由 T4 带合法签名创建）。当前 `users=5 / bookings=5 / max(booking.id)=5`。

---

## 九、误报与「已确认不修」

| 项 | 复核结论 | 理由 |
|---|---|---|
| `form.vue` 381 行 > 返工记录写的 330 行 | 不返工 | 仍 ≤400 行规范；记录数值不实 → Q-019（P3，文档对齐） |
| `annotations.md` #07 写 `App.vue:50`，实际 `.uni-tabbar__label` 在 `App.vue:57` | 不返工 | 标注指向偏差 7 行，量值本身正确 → Q-019 |
| D-02/D-04 证据仍写 `pages=5` | 已在映射表修正为 6 | 5B 加了隐私页，`check:build` 期望已是 6 |
| 首屏裸入口 2 次 GET（Q-018） | 保持 deferred | `e2e_pagination.json firstLoadCalls=2` 复现；带 `?v=A` 为 1；不影响功能，第 6 步真机复测 |
| 云函数无 `callFunction` 分支 / MP 硬编码 127.0.0.1（Q-013） | 保持 open | 外部依赖（云开发未开通），不伪造 |
| 备注 255 vs 设计 1000（Q-010） | 保持 open | 第 6 步定口径，二选一并回写 |
| `smoke.ps1` 只断 200 / admin 无种子 / `NotifyConsumer` javadoc | 不修 | 与 R1 结论一致 |

---

## 十、下一步

1. **用户回 §六 确认 10 项关键变更，并在 §七 选 A/B/C**（这是 5.5 的具名人工确认，缺一不得进第 6 步）。
2. 确认后：看板把 5.5 置 `已完成`，进第 6 步「本地运行与冒烟」——起 MQ → 复测 `notify_log` → 按映射表「用户操作路径」逐行走查（D-05/D-07/D-13/D-17/D-26/D-27 仍是 ⚠️，走查时逐行确认或维持 ⚠️ 并写原因）。
3. Q-010（备注上限口径）在第 6 步一并定；Q-017（stage6 口径）留 step11，但第 6 步入口闸门请继续用 `--stage 4`。
