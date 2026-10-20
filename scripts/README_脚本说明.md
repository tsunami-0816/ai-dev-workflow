# 工作流辅助脚本说明

这五个脚本是把「AI 评 AI」换成「机器校验」的工具，也是失败数据的采集入口。全部由**用户在本地运行**（Agent 不代跑），结果贴回对话或落盘。

| 脚本 | 解决的 AI 问题 | 在工作流哪一步用 |
|---|---|---|
| `dependency_checker.py` | AI 幻觉依赖（编造不存在的包/版本号） | 第 3 步架构评审人工卡点、第 6 步冒烟前 |
| `security_scan_secrets.py` | 硬编码密钥、敏感信息泄露 | 第 8.5 步安全扫描 |
| `api_contract_validator.py` | 前后端接口对不上（沉默的不一致） | 第 6 步冒烟后、第 7 步联调前 |
| `p0_regression_test.py` | 回归测试靠手点、不可重复 | 第 8 步全量测试（把 P0 用例沉淀为 JSON，回归时自动跑） |
| `log_failure.py` | 复盘凭记忆、没有失效数据 | 每次返工/卡点拦截时 |

---

## 1. dependency_checker.py — 依赖版本真实性校验

```bash
# 在待校验项目根目录执行（自动识别 requirements.txt / package.json / pom.xml）
python scripts/dependency_checker.py projects/生产异常答疑AI助手/05_代码/backend
```

- ✅ 绿色：版本真实存在
- ❌ 红色：版本不存在，基本可判定为 AI 幻觉，回第 2/3 步修复架构
- ⚠️ 黄色：网络问题无法校验，需人工手动确认

**注意**：需要联网（访问 PyPI / npm registry / Maven Central）。

## 2. security_scan_secrets.py — 硬编码密钥扫描

```bash
python scripts/security_scan_secrets.py projects/生产异常答疑AI助手/05_代码
```

发现一例即阻塞第 9 步验收，修复后必须重跑确认。

## 3. api_contract_validator.py — 接口契约校验

```bash
# 第一步：后端启动后，导出 OpenAPI 契约（FastAPI 自动生成）
python scripts/api_contract_validator.py export http://localhost:8000/openapi.json projects/生产异常答疑AI助手/06.5_契约/openapi.json

# 第二步：校验前端代码里的接口调用是否都在契约中
python scripts/api_contract_validator.py check projects/生产异常答疑AI助手/06.5_契约/openapi.json projects/生产异常答疑AI助手/05_代码/frontend
```

前端调用任何契约中不存在的接口会被标红——这就是「前端臆造接口」的自动化防线，替代「前后端对 Mock 靠自觉」。

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
  --human-catch "人工第 3 步未发现，第 6 步冒烟才暴露" \
  --rounds 1 --root-cause "幻觉依赖/版本"
```

日志写入项目根目录 `_失败日志.md`，每次运行自动输出统计（哪步返工最多）。第 10 步复盘直接引用这份日志做归因，不再凭记忆。

---

## 安装依赖

四个脚本只用 Python 标准库 + requests 系均不需要额外安装，直接可跑（Python 3.8+）。
