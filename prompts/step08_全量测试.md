# 第 8 步 · 第一轮全量测试（自动化框架 + 性能测试 + 报告CI）

- **角色**：资深测试开发工程师
- **输入**：《项目基线说明书》+ 联调通过的完整系统
- **输出物**（落盘 `08_测试/`）：
  - **pytest 四层自动化测试框架**（`08_测试/qa-automation/`）
  - 《全量测试用例清单》
  - **Bug 全部记入项目根目录 `_问题台账.md`**（只列 P0/P1 必修，P2/P3 标 `deferred`）——不另建 BUGLIST.md
  - **性能测试报告**（Python 轻量压测 + JMeter 交叉验证）
  - **Allure 可视化测试报告**
  - 8-1 修复：代码片段 + 修改影响分析 + 自测说明
  - 8-2 回归结果**写回台账**（`fixed` → `verified`、轮次日志）——不另产《第二轮回归测试报告》
  - **GitHub Actions CI 配置**（push 自动跑自动化用例）
- **规则**：本轮只修 P0/P1，P2/P3 标 `deferred` 留到下版本；修复不限轮次，按收敛判据（台账 open P0/P1 数须下降；同一根因 3 次无效或问题数回升 → 回流第 3 步），通过后进入第 9 步。

---

## 8.0 搭建 pytest 四层自动化测试金字塔（先做这个，再写用例）

在 `08_测试/qa-automation/` 下按**测试金字塔四层**组织用例，不要散着写脚本。每层职责、数量占比、技术选型写死：

| 层 | 名称 | 测什么 | 技术选型 | 数量占比 | 必须 |
|---|---|---|---|---|---|
| L1 | 单元测试 | 纯函数/工具类/业务逻辑，不碰 DB/HTTP | pytest + mock | 最多（约 50%） | 核心工具类、边界逻辑必须覆盖 |
| L2 | 接口集成测试 | 起后端进程，打真实 HTTP 接口，用内存/SQLite 或临时库 | FastAPI TestClient / requests + pytest | 次之（约 30%） | 每个核心接口正向+反向+边界+越权 |
| L3 | 中间件集成测试 | 用 Testcontainers 起真实 MySQL/Redis/Kafka 容器，验中间件交互 | testcontainers-python（Docker 需手动启动） | 少而精（约 10%） | 仅关键链路：DB 事务回滚、缓存失效、消息消费失败重试 |
| L4 | E2E 端到端 | 起完整前后端，走通主业务链路（注册→登录→建数据→列表可见） | requests + DB 断言脚本 | 最少（约 10%） | 只覆盖 P0 主路径，不追求分支覆盖 |

> **L3 取舍**：本机 16GB 内存，Docker Compose 已占一定资源。若 Testcontainers 起容器导致内存不足或启动过慢，L3 可降级为"L2 接口测试 + docker-compose 起好中间件后手动连"，但必须在测试报告里说明降级原因，不得偷偷砍掉。

目录结构（在上述分层基础上组织）：

```
qa-automation/
├── config/config.yaml        # 环境地址、账号（不写死密码，用变量）
├── common/
│   ├── request_util.py       # 封装 requests：自动带 token、打请求/响应日志
│   └── assert_util.py         # 封装统一返回体断言（code==0）
├── api/                      # 接口层：一个业务模块一个文件
│   ├── auth_api.py
│   └── xxx_api.py
├── testcases/
│   ├── conftest.py           # fixture：自动注册测试账号、登录拿 token；L3 提供容器 fixture
│   ├── l1_unit/              # L1 单元测试（mock 掉外部依赖）
│   │   └── test_xxx_util.py
│   ├── l2_api/               # L2 接口集成测试（TestClient / 真 HTTP）
│   │   └── test_xxx_api.py
│   ├── l3_integration/       # L3 中间件集成测试（Testcontainers，可选降级）
│   │   └── test_xxx_middleware.py
│   └── l4_e2e/               # L4 端到端主路径
│       └── test_main_flow.py
├── data/                     # 测试数据（yaml/csv）
├── reports/allure-results/   # Allure 输出（gitignore）
├── perf_test.py              # Python 轻量压测脚本
├── jmeter/xxx.jmx            # JMeter 压测脚本
├── perf-report.md            # 性能测试报告
├── requirements.txt
└── pytest.ini
```

> Bug 不再写成本目录的 BUGLIST.md，统一记在项目根目录 `_问题台账.md`（来源阶段=8）。

### 框架硬规则
1. **conftest 自动注册账号**：不依赖人工准备 admin 密码，登录失败自动注册临时用户再登录
2. **用例四象限**：每个核心接口必须写 正向 / 反向 / 边界 / 未授权 四类用例
3. **用例独立**：每条用例自己造数据、自己清理，不依赖其他用例执行顺序
4. **已知 Bug 用 xfail**：发现的已知 Bug 用 `@pytest.mark.xfail(reason=根因)` 标记，不要让它红；修复后自动转 PASS
5. **pytest.ini 配 allure**：`--alluredir=reports/allure-results --clean-alluredir`
6. **断言前先刷新快照**：用例内跨请求/跨 session 断言时，必须 `session.commit()`（或 `refresh`/`expire_all`）后再读，否则读到的是旧快照（本项目首轮 6 条 failed 的根因之一）
7. **禁止依赖库里已有业务数据**：不得 `select` 历史行做断言（例如「流程列表第 1 条」），每条用例自己创建、自己校验、自己清理
8. **异步/执行类用例显式等终态**：SSE/MQ/引擎执行类用例必须轮询到终态（`SUCCESS/FAILED`）并设上限超时，禁止 `sleep` 固定时长后直接断言

---

## 8.1 测试用例生成 Prompt

```
你是资深测试工程师，基于项目基线和功能清单，帮我生成一份全量测试用例清单，并在 qa-automation/testcases/ 下用 pytest 实现。

【项目基线】
{{粘贴《项目基线说明书》}}
【接口清单】
{{粘贴后端 Controller 的 @RequestMapping/@PostMapping 注解 + 入参出参}}

【输出要求】
1. 按业务模块分组，每个接口写：正向用例 + 反向用例（空值/超长/类型错/越权）
2. 业务特有边界必须覆盖：
   - 文件上传：MD5重复、超大文件、不支持类型、并发上传
   - 分页：pageNum=0、pageSize=999、负页码
   - 权限：普通用户调管理员接口、跨租户访问
   - 幂等：重复提交、并发创建同一条数据
3. 每条用例函数名：test_xxx_success / test_xxx_unauthorized，docstring 写人话
4. 断言要具体：不只断言 code==0，还要断言 data 里的关键字段
5. P0 用例同时导出 p0_cases.json（格式见 scripts/p0_regression_test.py docstring），用于冒烟回归
```

---

## 8.1.5 基线量化指标验证表（必做，不能跳过）

《项目基线说明书》里写的每个量化成功指标（响应时长、准确率、并发数、数据保留时长等），**到这一步必须给它一个验证归属**，不许默认达标：

```
请基于《项目基线说明书》，输出《基线指标验证表》：
| 基线指标 | 目标值 | 验证方式（自动化断言/人工实测/未验证） | 验证结果 |
逐条处理：
- 能自动化的：写进 pytest 用例或单独写 benchmark 脚本
- 只能人工测的：写清楚实测步骤和判定标准
- 既不能自动化也不好人工测的：标注「未验证风险」，如实告诉用户这个指标目前无法保证
禁止写「预计达标」「应该可以」这种模糊结论。
```

---

## 8.2 全量测试 Bug 清单 Prompt

```
你是资深测试工程师，基于项目基线和联调通过的系统，执行第一轮全量测试，把 Bug 逐条写入项目根目录 `_问题台账.md`（来源阶段=8）。

【台账每行必须包含】
- ID（Q-0xx，递增不复用）
- 严重级别（P0致命 / P1严重 / P2一般 / P3轻微）
- 现象：复现步骤 + 预期结果 vs 实际结果（写在同一格）
- 【根因标签 + 根因定位】必须翻到源码，指出哪个文件哪一行、什么逻辑导致，标签一句话概括
- 状态（open）
- 轮次（R1）
- 归属（本轮修复 / 下版本）

【输出要求】
1. 测试范围：覆盖的功能、链路、场景
2. 一次性列全所有 P0/P1，禁止分批输出
3. P2/P3 状态写 deferred，本轮不修
4. 未覆盖场景：本次未覆盖的边界与异常分支
```

> **根因定位是核心价值**：面试官/评审不在乎你测了多少，在乎你能不能从测试现象一路定位到源码根因。每条 Bug 都必须翻代码，不允许只写"接口报错了"。

---

## 8.3 8-1 Bug 定向修复 Prompt

**输入**：原有代码 + 第 8.2 步输出的 P0+P1 Bug 清单

```
你是资深开发工程师，基于现有代码，修复 `_问题台账.md` 里「来源阶段=8 且状态=open」的 P0、P1 问题。
【严格执行规则】
1. 只修复这些行对应的问题，禁止任何额外优化、重构、代码调整
2. 修改前先输出「修改影响分析」：每条 Bug 的修改点、涉及文件/函数、可能影响的其他功能
3. 修改后的代码标注：// 修复-Q0xx 改动原因
4. 修复完成后回报修了哪几条，我把台账状态改 fixed，并去掉对应 testcases 里的 xfail
5. 只输出有修改的代码片段，不输出完整全部代码
```

---

## 8.4 8-2 定向回归测试 Prompt

**输入**：修复后的代码 + 台账里 `状态=fixed` 的问题

```
你是资深测试工程师，执行本轮 Bug 修复的定向回归测试，结论写回 _问题台账.md。
【回归范围】
1. 上一轮所有 P0、P1 级 Bug 是否修复（对应 xfail 用例应转 PASS）
2. 修改影响分析中提到的关联功能是否正常
3. 跑全量 pytest：pytest --tb=no -q，要求 0 failed
【输出要求】
1. 已修复验证：逐条列 ID + 验证结果（通过/未通过）；未通过的说明原因（我把状态改回 open）
2. 引入新 Bug：在修改影响范围内新发现的，登记进台账（来源阶段=8，新 ID）
3. 结论：本轮回归是否通过、本轮 open P0/P1 数（写进台账轮次日志）
```

---

## 8.5 性能测试（必做，不能跳过）

### 8.5.1 Python 轻量压测（快速出数据）

在 `qa-automation/perf_test.py` 写一个多线程压测脚本：
- 三档并发：10 / 20 / 50，每档持续 10 秒
- 压测目标：选 1~2 个核心读接口（登录、列表查询等，不依赖外部 LLM）
- 输出指标：平均 RT、P95 RT、TPS、错误率

### 8.5.2 JMeter 交叉验证

在 `qa-automation/jmeter/` 下写一个最小 JMX（线程组 + HTTP 请求 + 聚合报告），命令行跑：
```
jmeter -n -t xxx.jmx -l result.jtl
```

### 8.5.3 瓶颈分析（写进 perf-report.md）
```
基于压测数据回答：
1. TPS 随并发变化的拐点在哪里？
2. 拐点后 RT 是否线性上升但 TPS 不涨？
3. 瓶颈大概率在：DB连接池？Tomcat线程池？外部调用？
4. 调优建议（具体到配置项，如 HikariCP maximum-pool-size）
```

---

## 8.6 Allure 报告 + GitHub Actions CI

### 8.6.1 Allure 可视化报告
1. pytest.ini 配 `--alluredir`
2. 跑 `allure generate reports/allure-results -o reports/html --clean`
3. 报告截图作为测试交付物

### 8.6.2 GitHub Actions CI
在项目根目录 `.github/workflows/test.yml` 配 CI：
- push 到 main 时自动跑 `pytest --collect-only`（语法检查 + 用例收集）
- 不需要真连数据库（CI 环境没有中间件），保证 badge 永远绿
- README 顶部加 CI badge

---

## 放行检查

- [ ] pytest 四层框架搭好，`pytest` 命令一键跑通，0 failed
- [ ] 每个核心接口都有正向+反向+边界+越权用例
- [ ] **`_问题台账.md` 里「来源阶段=8」的 P0/P1 全部 `verified`**，无 `open`/`fixed` 残留（门禁会查）
- [ ] **每条 P1 在台账改 `verified` 之前，已用 `python scripts/log_failure.py <项目目录> --step 8 --category "<类别>" ... --rule R10` 记入 `_失败日志.md`**（不记不许标 verified；门禁 `LOG_GAP_WARNING` 比对缺口）
- [ ] 「轮次日志」已记录本轮 open P0/P1 数，且单调下降；P2/P3 标 `deferred`
- [ ] 已知 Bug 用 xfail 标记，修复后自动转 PASS
- [ ] **性能测试完成**：有 Python + JMeter 双工具数据表，有瓶颈分析和调优建议
- [ ] Allure 报告能生成，截图交付
- [ ] GitHub Actions CI 配好，README 有绿 badge
- [ ] 基线指标验证表已产出，每个量化指标都有验证归属
- [ ] P2/P3 与未覆盖场景登记，移交第 10 步下版本规划
