# 工作流辅助脚本说明

这些脚本（11 个）是把「AI 评 AI」换成「机器校验」的工具，也是失败数据的采集入口。**运行口径**：Agent 有终端能力时由 Agent 跑，原始输出贴回对话并落盘；Agent 无终端或需要用户本地凭证时由用户跑，把输出贴回。判定标准只有一个：**原始输出必须落盘**，不落盘的结论一律无效。

| 脚本 | 解决的 AI 问题 | 在工作流哪一步用 |
|---|---|---|
| `dependency_checker.py` | AI 幻觉依赖（编造不存在的包/版本号） | 第 3 步架构评审人工卡点、第 6 步冒烟前 |
| `env_preflight.py` | 架构写得漂亮但本机没装工具/端口被占/内存不够 | 第 3 步架构评审人工卡点、第 5A 步完成定义（`--smoke`） |
| `security_scan_secrets.py` | 硬编码密钥、敏感信息泄露 | 第 8.5 步安全扫描 |
| `api_contract_validator.py` | 前后端接口对不上（沉默的不一致） | 第 6 步冒烟后、第 7 步联调前 |
| `p0_regression_test.py` | 回归测试靠手点、不可重复 | 第 8 步全量测试（把 P0 用例沉淀为 JSON，回归时自动跑） |
| `log_failure.py` | 复盘凭记忆、没有失效数据 | 每次返工/卡点拦截时 |
| `portfolio_scanner.py` | 作品集撞车（做了 3 个 RAG 又做第 4 个） | step00.2 作品集画像扫描 |
| `skills_coverage_checker.py` | JD 要 Kafka 但设计书里只是个名字 | step00.5 卡点2、第 3 步评审 |
| `split_long_image.py` | JD 长截图 Read 工具直接拒 | step00.1 收 JD 截图时 |
| `design_impl_check.py` | **设计书/架构里写了的要素，实际没实现，到冒烟才发现链路压根没写** | 第 4 步（结构）、第 6 步阶段一、第 10.0 门禁（100%） |
| `workflow_completion_check.py` | 产物没齐 / 台账没收敛 / 看板与队列状态撕裂就标「已完成」 | 第 10.0 步完成门禁（唯一放行判据） |

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
python scripts/p0_regression_test.py projects/生产异常答疑AI助手/08_测试/cases/p0_cases.json
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

`--rule R<编号>`（可选）标这次是哪条工作流规则兜住了这个坑：step11 体检据此统计规则触发、给主控 §8.0 规则登记表补源（「以用证源」），留空记「—」。不额外增加流程步骤，失败日志本来就要写。

**必填字段**：`--step`（白名单：0~4 / 5A / 5B / 6 / 6.5 / 7 / 7.5 / 8 / 8.5 / 9 / 10 / 10.5 / 10.6 / 11）、`--desc`、`--impact-file`、`--repro`；类别为「人工卡点拦截 / 验收不通过」时 `--human-catch` 必填。缺项直接拒写（exit 2），防笔误与不可复盘记录。

---

## 6. env_preflight.py — 本机环境就绪预检

第 3 步架构评审人工复核时跑（与 dependency_checker.py 互补：dependency_checker 验"依赖版本在公网存在"，env_preflight 验"本机真的装了能跑"）：

```bash
python scripts/env_preflight.py
# 可选：自定义要检查的端口
python scripts/env_preflight.py --ports 8080,3306,6379
# 可选：配置值实测（第 3 步人工复核、第 6 步冒烟前强烈建议）
python scripts/env_preflight.py --verify-config projects/<项目名>
# 可选：服务起来后做 HTTP 冒烟（第 5A 步完成定义，5A 声明完成前必跑）
python scripts/env_preflight.py --smoke "http://localhost:8081/health,http://localhost:8081/api/docs"
```

检查项：Java/Maven/Node/npm/Docker/Compose/Python 版本、常用端口占用、可用内存。缺工具直接阻塞评审，警告项人工确认。
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

step00.5 卡点2 跑，机器校验"JD 高频技能点在设计书里真有落地"：

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

# 第 10 步 / 10.0 门禁：❌未实现 与 ⚠️已实现未验证 都不允许（100% 才算完）
python scripts/design_impl_check.py projects/<项目名> --stage 10
python scripts/design_impl_check.py projects/<项目名> --stage 10 --json
```

映射表固定表头（缺列即报 `MAPPING_STRUCTURE`）：

| 编号 | 设计来源 | 设计项（功能/链路） | 端到端链路（输入→处理→输出） | 用户操作路径 | 实现落点 | 状态 | 验证证据 |

状态四值：`❌未实现` / `⚠️已实现未验证` / `✅已实现已验证` / `✂️明确砍掉`（必须在「验证证据」列写砍掉依据，否则结构报错）。
退出码：0 通过 / 1 阻塞（`MAPPING_MISSING` 文件缺失、`MAPPING_STRUCTURE` 结构错、`MAPPING_EMPTY` 无数据行、`MAPPING_NOT_READY` 仍有未实现或未验证） / 2 参数错。
历史豁免：`workflow/steps.yaml` 的 `mapping.launch_date`（当前 `2026-10-31`）之前创建的项目不阻塞，避免已交付项目复跑变红。

## 11. workflow_completion_check.py — 第 10.0 完成门禁

```bash
python scripts/workflow_completion_check.py projects/<项目名>
```

门禁项来自 `workflow/steps.yaml`（产物齐套）+ 台账收敛 + 看板/队列一致性 + 本次新增两项：
- **`LOG_GAP_WARNING`**：台账里 `P1 && verified` 的条数比 `_失败日志.md` 的数据行还多 → 警告，不阻塞；step11 复盘必须补齐或说明原因。
- **映射 100%**：调 `design_impl_check.py --stage 10`，有未实现/未验证即报 `MAPPING_*` 阻塞；早于 `launch_date` 的历史项目返回 OK 并注明豁免理由。
全绿是队列状态改「已完成」的唯一判据；报红按 `suggested_fallback_steps` 回退补齐。

---

## 安装依赖

基础脚本（前 6 个）只用 Python 标准库 + requests 系均不需要额外安装，直接可跑（Python 3.8+）。
`split_long_image.py` 需要 Pillow：`pip install pillow`。
`skills_coverage_checker.py` 和 `portfolio_scanner.py` 只用标准库。
