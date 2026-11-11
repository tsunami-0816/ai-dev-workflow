# 工作流辅助脚本说明

这些脚本（21 个，含 1 个内部模块 + 1 个一次性维护脚本）是把「AI 评 AI」换成「机器校验」的工具，也是失败数据的采集入口。所有脚本入口都会把 stdout/stderr 切成 UTF-8（Windows 默认 cp936/GBK 下打印中文/emoji 不再 `UnicodeEncodeError`）；密钥扫描另支持根目录 `.secretignore` 豁免清单（仅测试夹具/示例）。**运行口径**：Agent 有终端能力时由 Agent 跑，原始输出贴回对话并落盘；Agent 无终端或需要用户本地凭证时由用户跑，把输出贴回。判定标准只有一个：**原始输出必须落盘**，不落盘的结论一律无效。

| 脚本 | 解决的 AI 问题 | 在工作流哪一步用 |
|---|---|---|
| `dependency_checker.py` | AI 幻觉依赖（编造不存在的包/版本号） | 第 3 步架构评审人工卡点、第 6 步冒烟前 |
| `env_preflight.py` | 架构写得漂亮但本机没装工具/端口被占/内存不够 | 第 3 步架构评审人工卡点、第 5A 步完成定义（`--smoke`） |
| `security_scan_secrets.py` | 硬编码密钥、敏感信息泄露 | 第 8.5 步安全扫描 |
| `prepush_check.py` | push 后密钥/大文件撤不回（公开仓库尤其致命） | 第 10.5 步 GitHub 推送前（push 前必跑） |
| `api_contract_validator.py` | 前后端接口对不上（沉默的不一致） | 第 6 步冒烟后、第 7 步联调前 |
| `p0_regression_test.py` | 回归测试靠手点、不可重复 | 第 8 步全量测试（把 P0 用例沉淀为 JSON，回归时自动跑） |
| `log_failure.py` | 复盘凭记忆、没有失效数据 | 每次返工/卡点拦截时（`--response-type` 记 G3 四分类） |
| `input_card_check.py` | 步骤交接卡缺字段/引用失效/路径越界/枚举写错，开工前拦不住（G1） | 每步开工前（输入卡校验闸） |
| `checkpoint.py` | 中断后靠猜看板恢复、整段重跑、重复造数据（G10） | 长步骤 mark/done，新对话恢复时 status 决策树 |
| `gate_gatekeeper.py` | 新闸长期挂旁路观察期、没人转硬闸（观察期无自动出口） | step10 复盘 / step11 体检：review 按观察日志自动转 strict，status 查状态，mark-fp 标误报 |
| `portfolio_scanner.py` | 作品集撞车（做了 3 个 RAG 又做第 4 个） | step00.2 作品集画像扫描 |
| `skills_coverage_checker.py` | JD 要 Kafka 但设计书里只是个名字 | step00 设计书机器闸门（WORKFLOW_卡点协议.md「机器闸门」表，原卡点2）、第 3 步评审 |
| `split_long_image.py` | JD 长截图 Read 工具直接拒 | step00.1 收 JD 截图时 |
| `design_impl_check.py` | **设计书/架构里写了的要素，实际没实现，到冒烟才发现链路压根没写** | 第 4 步（结构）、第 6 步阶段一、第 10.0 门禁（100%+证据） |
| `design_quality_check.py` | 前端 UI 对比度/小字/padding 拥挤等可量化硬伤 | 第 6 步（R23，包装 impeccable detect） |
| `design_taste_gate.py` | 页面「一眼 AI 模板味」（居中大标题+三图标卡+柔渐变） | 第 6 步（R23 配套 taste 子项） |
| `workflow_completion_check.py` | 产物没齐 / 台账没收敛 / 看板与队列状态撕裂就标「已完成」 | 第 10.0 步完成门禁（唯一放行判据） |
| `refurbish_intake.py` | 翻新线 F0 迁入建档靠手抄、字段漏填 | 翻新线 F0（野生/毕业生两入口） |
| `rule_usage_stats.py` | 规则只增不减、没人知道哪些在空转 | step11 规则体检（统计触发次数） |
| `_f0_manual_finalize.py` | 一次性补跑 F0 闸门并回写看板 | 维护用，不进日常流水线（路径全部显式传参） |

自检用例在 `scripts/tests/test_fixtures.py`（pytest 真断言，含负向漂移 fixture）：

```bash
pip install -e ".[test]"
python -m pytest scripts/tests -q
```

---

## 1. dependency_checker.py — 依赖真实性与可解性校验

```bash
# 版本真实性（自动识别 requirements.txt / package.json / pom.xml，含子目录）
python scripts/dependency_checker.py projects/生产异常答疑AI助手/05_代码/backend

# 追加可解性校验（推荐第 3 步、第 6 步前都跑）
python scripts/dependency_checker.py <项目根目录> --solve
```

- ✅ 绿色：版本真实存在
- ❌ 红色：版本不存在，基本可判定为 AI 幻觉，回第 2/3 步修复架构
- ⚠️ 黄色：网络问题无法校验，需人工手动确认
- `--solve`：Python 走 `pip install --dry-run --ignore-installed -r`，Maven 走 `mvn dependency:tree`；**单包存在 ≠ 整体能解**（版本冲突/传递依赖缺失在这里暴露）。无 pip/mvn 时跳过并提示
- **没有依赖文件/解析出 0 条依赖时退出 1**：打印 `❌ 未找到依赖文件，无法判定`，不再把「目录里没有 requirements.txt / package.json / pom.xml」当成「依赖全部真实存在」假绿

**注意**：需要联网（访问 PyPI / npm registry / Maven Central）。

## 2. security_scan_secrets.py — 硬编码密钥扫描 + SAST

```bash
# 仅密钥扫描
python scripts/security_scan_secrets.py projects/生产异常答疑AI助手/05_代码

# 追加代码级 SAST（第 8.5 步推荐）
python scripts/security_scan_secrets.py <项目根目录> --sast
```

发现一例即阻塞第 9 步验收，修复后必须重跑确认。
`--sast` 规则 3 类：全局 `AviatorEvaluator.execute`、SQL 字符串拼接/f-string 拼 SQL、`Runtime.exec`/`os.system`/`shell=True`。命中需逐条确认，误报写进安全扫描报告豁免说明。

**`.secretignore`（测试夹具/示例豁免，2026-11-08 新增）**：扫描根目录的 `.secretignore` 每行一个「相对根目录」的精确路径或 fnmatch glob，`#` 开头/行尾为注释。命中文件打印 `⏭️ 忽略（.secretignore）: path`，计入总结的 ignored 计数，不阻塞退出码。只允许放测试账号/示例占位（典型：冒烟/联调/验收脚本里的固定测试密码、P0 用例夹具）；**真实密钥必须修代码 + 重置，不许靠豁免绕**。本仓库根目录的 `.secretignore` 列了 CI 干净检出会误报的 9 个测试/验收脚本与夹具，并逐条写了理由。

**测试上下文不再整类豁免（2026-10-30 收紧）**：以前只要路径含 `test` 字样就整类跳过密码扫描，真实密钥藏在测试目录里会漏报。现在只按**目录段**判断（`test/tests/__tests__/testcases/e2e/spec/specs/fixtures`），命中降级为 `[测试上下文]` **警告，不阻塞但必须人工逐条确认**；文件名带 test 不算测试目录，生产代码照样阻塞。脚本末尾会打印「测试上下文文件清单」，豁免要写进安全扫描报告。

## 3. api_contract_validator.py — 接口契约校验

```bash
# 第一步：后端启动后，导出 OpenAPI 契约（FastAPI 自动生成）
python scripts/api_contract_validator.py export http://localhost:8000/openapi.json projects/生产异常答疑AI助手/06.5_契约/openapi.json

# 第二步：校验前端代码里的接口调用是否都在契约中
python scripts/api_contract_validator.py check projects/生产异常答疑AI助手/06.5_契约/openapi.json projects/生产异常答疑AI助手/05_代码/frontend

# 扩展：必带请求头 + 字段别名漂移
python scripts/api_contract_validator.py check <openapi.json> <前端目录> \
  --headers X-Tenant-Id,X-Internal-Token \
  --aliases payload=_payload \
  --scan-dir <后端代码目录>
```

前端调用任何契约中不存在的接口会被标红——这就是「前端臆造接口」的自动化防线，替代「前后端对 Mock 靠自觉」。
`--headers`：校验这些头是否在契约中声明（一次都没声明=漏写 header 参数）；`--aliases`：同一语义两种写法且**没有任何文件同时使用**时判漂移嫌疑（读写对不上的典型形态）。

## 4. p0_regression_test.py — P0 用例自动化回归

第 8 步生成测试用例时，让 AI **同时输出 p0_cases.json**（格式见脚本 docstring），你本地跑：

```bash
python scripts/p0_regression_test.py projects/生产异常答疑AI助手/08_测试/p0_cases.json
```

输出逐条通过/失败 + `p0_cases_report.json` 报告。修复后重跑一遍即完成回归，不再手点。

## 5. log_failure.py — 失败日志记录

每次发生返工、卡点拦截、评审打回时运行一次：

```bash
python scripts/log_failure.py projects/生产异常答疑AI助手 \
  --step 6 --category "真实运行报错" \
  --desc "chromadb 0.5.3 与 langchain-community 0.3.7 不兼容" \
  --ai-error "AI 在架构中选了两个互不兼容的版本" \
  --impact-file "agent-python/requirements.txt" \
  --repro "pip install -r requirements.txt" \
  --human-catch "人工第 3 步未发现，第 6 步冒烟才暴露" \
  --rounds 1 --root-cause "幻觉依赖/版本" --rule R8
```

日志写入项目根目录 `_失败日志.md`，每次运行自动输出统计（哪步返工最多）。第 10 步复盘直接引用这份日志做归因，不再凭记忆。

`--rule R<编号>`（可选）标这次是哪条工作流规则兜住了这个坑：step11 体检据此统计规则触发、给WORKFLOW_规则库.md §8.0 规则登记表补源（「以用证源」），留空记「—」。不额外增加流程步骤，失败日志本来就要写。

**必填字段**：`--step`（白名单：0~4 / 5A / 5B / 6 / 6.5 / 7 / 7.5 / 8 / 8.5 / 9 / 10 / 10.5 / 10.6 / 11）、`--desc`、`--impact-file`、`--repro`；类别为「人工卡点拦截 / 验收不通过」时 `--human-catch` 必填。缺项直接拒写（exit 2），防笔误与不可复盘记录。

**`--response-type`（G3 四分类，2026-11-11 新增）**：`stop`（硬阻断，回上游改设计）/ `retry`（本轮内重试，findings 必须逐轮递减）/ `human`（转人工卡点，振荡第 2 次直接 human）/ `transient`（环境/网络瞬时，探活后重跑）；默认 `retry`。日志表末尾追加「响应类型」列（末尾加列，不动中间列索引，避免破坏现有 by_step 统计解析）。

---

## 6. env_preflight.py — 本机环境就绪预检

第 3 步架构评审人工复核时跑（与 dependency_checker.py 互补：dependency_checker 验"依赖版本在公网存在"，env_preflight 验"本机真的装了能跑"）：

```bash
python scripts/env_preflight.py
# 可选：自定义要检查的端口
python scripts/env_preflight.py --ports 8080,3306,6379
# 可选：配置值实测（第 3 步人工复核、第 6 步冒烟前强烈建议）
python scripts/env_preflight.py --verify-config projects/<项目名>
# 可选：配置完整性差集（裸跑 --env-coverage 等价于扫描当前目录 .）
python scripts/env_preflight.py --env-coverage projects/<项目名>
# 可选：服务起来后做 HTTP 冒烟（第 5A 步完成定义，5A 声明完成前必跑）
python scripts/env_preflight.py --smoke "http://localhost:8081/health,http://localhost:8081/api/docs"
# 裸跑 --smoke：不 argparse 报错，默认检查 http://127.0.0.1:8080/health
python scripts/env_preflight.py --smoke
```

检查项：Java/Maven/Node/npm/Docker/Compose/Python 版本、常用端口占用、可用内存。**退出码是硬判据（2026-11-08 收紧）**：必需工具缺失、版本低于期望下限、端口被占、配置实测失败、冒烟失败 → 一律退出码 1；内存不足仍是 warning 不阻塞。
`--verify-config`：读项目内 `.env`/`.env.example` → 逐项 TCP 探活 → Redis 发 PING（有密码先 AUTH）→ MySQL 有客户端时 `SELECT 1` → 多个 `.env` 中同名令牌值不一致直接报错（恒 401 的根因）→ 模板里的必填键缺失或仍是占位值报错。
`--smoke`：逗号分隔的 URL 列表，逐个 GET 并断言状态码（`--smoke-expect` 默认 200）；超时 8 秒，连不上/状态码不符并入问题清单。**「能编译」不等于「能跑」，这一步就是把起服务后的第一手事实落成机器判据**。

## 7. split_long_image.py — JD 长截图切分

step00.1 收到超长 JD 截图（高度 >2000px Read 工具拒读）时跑：

```bash
pip install pillow   # 只需装一次
python scripts/split_long_image.py "D:\path\to\jd_long.png"
```

按 1600px 一段、段间重叠 100px 切分，输出 `xxx_part1.png` `xxx_part2.png`，再逐段喂给 Read 工具识别。

## 8. portfolio_scanner.py — 作品集画像扫描

step00.2 跑一次，扫描 D:\lg\project\ 下所有项目，提取技术栈：

```bash
python scripts/portfolio_scanner.py --root "D:\lg\project" --out projects/<新项目>/00_作品集画像库.json
```

扫 pom.xml/requirements.txt/package.json/docker-compose.yml 里的依赖，按内置 SKILL_MAP 映射成技能点。已存在的画像库会覆盖（人工补充的打标建议在 JSON 里保留）。

## 9. skills_coverage_checker.py — JD 技能点对账

step00 设计书机器闸门（WORKFLOW_卡点协议.md「机器闸门」表，原卡点2）跑，机器校验"JD 高频技能点在设计书里真有落地"：

```bash
python scripts/skills_coverage_checker.py \
  --skills-json 00_JD技能点清单.json \
  --design-doc projects/<新项目>/00_项目设计书.md \
  --portfolio-json 00_作品集画像库.json
```

- must_have 覆盖率 <100% 直接退出码 1，打回重设计
- 某技能点在设计书里只出现 1 次会标"浅覆盖"，人工确认是不是只列了个名字
- 带 --portfolio-json 时顺手做技术栈撞车检测
- **设计书 9 节存在性检查（默认开启）**：一句话定位/业务场景/技术架构/硬骨头/JD 对账/工作量拆解/面试三问/主动砍掉/风险点，缺节退出码 1；历史项目补跑可加 `--skip-sections`
- **只卡必备节（可选）**：`--required-sections "硬骨头模块,工作量拆解,主动砍掉项"`（按节名）或 `--required-sections 4,6,8`（按脚本内节序号，顺序为 1 一句话定位 / 2 业务场景 / 3 技术架构 / 4 硬骨头模块 / 5 JD 技能点对账表 / 6 工作量拆解 / 7 面试三问 / 8 主动砍掉项 / 9 风险点）。只校验指定子集，不能与 `--skip-sections` 混用；节名无法识别或节号越界退出码 2

## 10. design_impl_check.py — 设计→实施 100% 映射校验

第 2 步架构文档末尾的「§ 设计要素与端到端链路清单」（`D-01…`）→ 第 4 步逐条抄进项目根目录 `_设计实施映射表.md` → 5A/5B 开发时回填状态 → 第 6/10 步机器核对。**这条脚本就是用来防「设计书写了、实际没写、到冒烟才发现」的**。

```bash
# 第 4 步：只查结构（文件在不在、表头列全不全、编号有没有重复、砍掉行有没有依据）
python scripts/design_impl_check.py projects/<项目名> --stage 4

# 第 6 步阶段一：禁止存在 ❌未实现
python scripts/design_impl_check.py projects/<项目名> --stage 6

# 第 10 步 / 10.0 门禁：❌未实现、⚠️已实现未验证、✅但没写验证证据 都不允许（100% 才算完）
python scripts/design_impl_check.py projects/<项目名> --stage 10
python scripts/design_impl_check.py projects/<项目名> --stage 10 --min-rows 10 --json
```

映射表固定表头（缺列即报 `MAPPING_STRUCTURE`）：

| 编号 | 设计来源 | 设计项（功能/链路） | 验收指标 | 端到端链路（输入→处理→输出） | 用户操作路径 | 实现落点 | 状态 | 验证证据 |

状态四值：`❌未实现` / `⚠️已实现未验证` / `✅已实现已验证` / `✂️明确砍掉`（必须在「验证证据」列写砍掉依据，否则结构报错）。

**stage 10 的「验收指标」挂接核对（G8，2026-11-11 新增）**：基线说明书里的 `criterion_id`（C01、C02…）必须在映射表「验收指标」列逐条挂到对应链路；基线有但映射表没挂、或映射表引用了基线不存在的 C 编号，返回 `MAPPING_CRITERION`。基线里没有任何 C 编号时跳过本项（历史/未改造项目豁免）。**旁路口径（方案 §8）**：缺省为旁路观察期，挂接问题只记 `criterion_warning`、不阻塞交付；连续一个项目无误报后加 `--strict-criterion` 转阻塞闸。

**stage 10 的「验证证据」硬校验（2026-11-08 新增）**：状态 ✅ 的行，「验证证据」不能是空/`—`/`-`/`无`/`待补`/`TODO`，否则返回新状态 `MAPPING_EVIDENCE` 并报缺几条。依据：状态只靠 AI 自填 ✅ 无法防「说自己验证了但没证据」，交付阶段必须能追到接口返回/截图路径/日志片段/测试名。stage 4/6 保持宽松（只查结构/未实现）。

**`min_rows` 条数下限**：由 `workflow/steps.yaml` 的 `mapping.min_rows` 传给门禁（当前 `10`），也可用 `--min-rows` 手动指定；映射表数据行数低于阈值直接 `MAPPING_NOT_READY`（防 1 行表冒充 100%）。

退出码：0 通过 / 1 阻塞（`MAPPING_MISSING` 文件缺失、`MAPPING_STRUCTURE` 结构错、`MAPPING_EMPTY` 无数据行、`MAPPING_NOT_READY` 仍有未实现/未验证或行数不足、`MAPPING_EVIDENCE` ✅ 行缺验证证据、`MAPPING_CRITERION` 基线指标未挂接/悬空引用） / 2 参数错。
历史豁免：`workflow/steps.yaml` 的 `mapping.launch_date`（当前 `2026-10-31`）之前创建的项目不阻塞，避免已交付项目复跑变红。

## 11. workflow_completion_check.py — 第 10.0 完成门禁

```bash
python scripts/workflow_completion_check.py projects/<项目名>
```

门禁项来自 `workflow/steps.yaml`（产物齐套）+ 台账收敛 + 看板一致性 + 映射 100% + 失败日志缺口；非绿项按 `suggested_fallback_steps` 回退补齐：

**产物内容闸门（2026-11-08 新增，steps.yaml 的 artifact 可选键，缺省不启用）**
- `min_bytes`：文件最小字节数，默认 32；小于判 `EMPTY`（10 字节占位文件不再算「产物落盘」）
- `forbid`：禁用内容子串列表，命中任一判 `NEGATIVE` 并报命中词。用于堵「否定式通过」——例：安全扫描报告必须 `keywords: ["P0","P1","清零"]` 命中，同时 `forbid: ["未清零","未通过","仍存在 P0","仍存在 P1","阻塞验收"]`，这样「P0 未清零」正文命中关键词也能被抓出来
- `optional: true` + `mode: "精修"`：仅当看板「设计模式」含该模式时才要求产物；普通模式返回 `OK + skipped`（如 `设计精修记录.md`），不逼普通模式交占位文件
- `alt` 历史路径与 `launch_date` 历史项目豁免逻辑保持不变
- 状态：`OK` / `MISSING` / `EMPTY` / `NO_KEYWORD` / `NEGATIVE` / `READ_ERROR` / `BOARD_STALE` / `LEDGER_OPEN` / `MAPPING_*`（含 `MAPPING_EVIDENCE`）

**台账 / 看板 / 映射 / 日志**
- **`LOG_GAP_WARNING`**：台账里 `P1 && verified` 的条数比 `_失败日志.md` 的数据行还多 → 警告，不阻塞；step11 复盘必须补齐或说明原因。
- **映射 100%**：调 `design_impl_check.py --stage 10` 并传 `mapping.min_rows`——有未实现/未验证/✅缺证据/行数不足即报 `MAPPING_*` 阻塞；早于 `launch_date` 的历史项目返回 OK 并注明豁免理由。
- **看板一致性**：看板仍写「进行中/未开始/当前卡点」或产物比看板新 >10 分钟 → `BOARD_STALE` / `BOARD_FRESH_WARNING`。

全绿是队列状态改「已完成」的唯一判据。`--json` 输出含每项 `status` / `skipped` / `details`，便于 CI 消费。

## 12. prepush_check.py — 公开推送前硬闸（10.5 push 前必跑）

对齐 WORKFLOW_步骤定义.md step10.5：`git push` 之后密钥/大文件/运行数据推到公开仓库就撤不回。第 10.5 步 push 前跑：

```bash
python scripts/prepush_check.py
python scripts/prepush_check.py --json
```

检查项（任一红退出 1，禁止 push）：
1. **`.gitignore` 覆盖**：必须含 `.env`、`node_modules`、运行数据（`runtime/` `data/` `*.db` 等一类规则）
2. **Git 历史密钥扫描**：`git log -p --all` 全分支逐行扫 `sk-` / `AKIA` / `ghp_` / `xox` / 私钥块 / Bearer / 带账号密码的数据库连接串 / `DB_PASSWORD=`、`api_key=` 一类赋值；跳过明显占位值（example/${VAR}/process.env/st.text_input( 等代码引用）
3. **被跟踪的危险文件**：`git ls-files` 里存在真实 `.env`（`.env.example/.sample/.template` 不算）或 >5MB 大文件
4. **仓库可见性**：`gh repo view --json visibility` 尽力检查。WORKFLOW_步骤定义.md step10.5 要求仓库必须 public（作品集展示）→ private/internal 判红；PUBLIC 警告（确认历史已清零再推）；查不到（未装 gh/未登录/无远端）SKIP 不阻塞

豁免：与密钥扫描共用根目录 `.secretignore`（测试夹具/示例的历史命中会被跳过并计数）。
注意：它检查的是「你准备 push 的那一刻」的本地仓库，不是远端；红项要先清历史（重置密钥 → `git filter-repo`/BFG 清历史 → 重扫确认）再 push。

## 13. input_card_check.py — 步骤交接卡 Schema 校验（G1/G2）

每步开工前跑，把「交接卡缺字段、引用失效、路径越界、枚举写错、scope 自相矛盾、限额非法」拦在动手之前：

```bash
python scripts/input_card_check.py 5A projects/<项目名>/05_代码/5A_输入卡.yaml --project projects/<项目名>
```

- Schema 唯一事实源：`workflow/input_card_schema.yaml`（通用必填 + 分步骤扩展 + task 项 + G2 scope/limits + 端口规则）
- 校验项：必填字段、`sources`/`arch_ref` 产物存在且不越出项目根、枚举合法（risk/mock_policy 等）、scope 的 in/out 不相交、limits 为正整数、端口在合法区间
- 退出码：0 全绿或旁路警告 / 1 报红（仅 `--strict` 阻塞闸）/ 2 脚本自身错误
- **旁路口径（方案 §8）**：缺省为旁路观察期，校验不绿先 ⚠️ 警告、exit 0；连续一个项目无误报后加 `--strict` 转阻塞闸（exit 1，回上一步补卡，卡不绿不动手）
- 历史项目豁免：门禁上线前创建的项目不强制补卡；误报按 R12 先怀疑脚本

## 14. checkpoint.py — 断点标记 + 恢复决策树（G10）

长步骤中断后靠标记文件恢复，不靠猜看板；恢复不整段重跑：

```bash
# 开工前标记断点
python scripts/checkpoint.py mark projects/<项目名> --step 6 --command "npm run dev" --pid 12345 --output-path "06_冒烟/冒烟记录.md"
# 收口（记录退出码）
python scripts/checkpoint.py done projects/<项目名> --step 6 --exit-code 0
# 新对话恢复：读最新断点并给恢复建议
python scripts/checkpoint.py status projects/<项目名>
```

- 标记文件：项目根 `.checkpoint/<step>.json`（运行时状态，`.gitignore.template` 已排除，不进 10.0 门禁产物清单）
- 决策树：① 产物已落盘 + exit_code=0 → 跳过；② pid 仍存活 → 探活等待，不重启；③ 进程死 + exit_code≠0 → 只重跑本步；④ 无标记 → 从本步开始
- 硬规则：禁止整段从头重跑；恢复第一步永远先 `env_preflight.py --smoke <已知 URL>` 探活，服务活着不重启
- 本期不做：自动崩溃重启、跨机器恢复、断点状态云端同步。退出码：0 正常 / 2 脚本错误

## 15. gate_gatekeeper.py — 新闸观察期自动转硬闸（G1/G8）

新闸按方案 §8 先旁路观察一个项目，本脚本负责观察期的自动出口，避免长期挂旁路：

```bash
python scripts/gate_gatekeeper.py status                      # 看各闸 observe/strict、观察计数、误报数
python scripts/gate_gatekeeper.py review projects/<项目名>    # step10 复盘 / step11 体检跑
python scripts/gate_gatekeeper.py mark-fp projects/<项目名> --gate input_card --note "路径含括号被误判越界"
```

- 状态文件：`workflow/gate_states.yaml`（机器维护，`observed_projects` / `false_positives` / `activated_*` 不要手改）
- 观察日志：`<项目根>/.gate_observations/<gate>.jsonl`，每次 observe 模式跑校验追加一条
- **review 判据**：本项目该闸观察记录无误报 → 观察计数 +1，达 `threshold_projects`（默认 1）自动翻 `strict`；有误报 → 计数清零、误报累计，继续 observe；本项目没跑过该闸则不计入（幂等，已计入的行打 `counted` 标记）
- 读不到状态文件或解析失败 → 保守按 observe 旁路，不误阻塞（R12）
- 配套模块 `_gate_states.py`：状态读取 / 观察日志读写，供 `input_card_check.py`、`design_impl_check.py` 共用

---

## 安装依赖

全部脚本只用 Python 标准库即可运行（Python 3.8+，UTF-8 输出在入口自动切换）；`workflow_completion_check.py` 需要 PyYAML（`pip install pyyaml`，随 `pip install -e .` 装）。
`split_long_image.py` 需要 Pillow：`pip install pillow`。
`design_quality_check.py` / `design_taste_gate.py` 需要 Node.js 与 `skills/active/` 下的对应 skill 脚本（无 Node 时会显式报错，不静默跳过）。
