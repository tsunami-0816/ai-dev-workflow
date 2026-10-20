# ai-dev-workflow

![CI](https://github.com/tsunami-0816/ai-dev-workflow/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-yellow)

> 一套驱动 AI 从 0 到 1 交付项目的标准化工作流：10 步流程 + CLI 工具 + 5 项自动化质量校验，覆盖架构评审、接口契约、安全扫描到 P0 回归全链路。

---

## 亮点

- **10 步标准化流程**：项目基线 → 架构设计 → 评审卡点 → 任务拆解 → 前后端并行开发 → 本地冒烟 → 契约校验 → 全链路联调 → 全量测试 → 安全扫描 → 最终验收 → 交付复盘，每步产物按编号落盘。
- **CLI 工具 `wf`**：一行命令创建项目脚手架、查看进度看板、调取提示词模板、记录失败日志、触发机器校验。
- **5 项自动化校验脚本**：依赖版本真实性（查 PyPI / npm / Maven Central）、OpenAPI 接口契约一致性、硬编码密钥扫描、P0 用例自动化回归、失败日志结构化记录。
- **机器校验优先于 AI 自检**：AI 的评审/报告只是参考，脚本结果才是判据，专治幻觉依赖、臆造接口、跳过验证。
- **真实示例项目已全流程交付**：基于本工作流完成「生产异常答疑 AI 助手」（FastAPI + Chroma + 混合检索 + 三级兜底），47 项 e2e 断言全通过，P0/P1 Bug 清零。

---

## 架构

### 工作流 10 步

```
1 项目基线定义
  ↓
2 技术架构设计
  ↓
3 架构评审卡点 ──── 人工确认（技术选型 / 版本冲突 / 模块遗漏）
  ↓
4 任务拆解与开发规范
  ↓
5A 后端开发 ──┐
              ├── 产出 OpenAPI 契约
5B 前端开发 ──┘
  ↓
6 本地冒烟 ──── 阶段一 AI 自启动探活 / 阶段二用户走主流程
  ↓
6.5 接口契约校验（脚本）
  ↓
7 全链路联调（≤2 轮）
  ↓
8 全量测试（≤2 轮，P0 用例存 p0_cases.json）
  ↓
8.5 安全扫描（强制卡点）
  ↓
9 最终验收（人工卡点）
  ↓
10 交付复盘
```

### 技术栈

| 模块 | 技术 |
|---|---|
| CLI 工具 | Python 3.8+ / argparse |
| 依赖校验 | PyPI JSON API / npm Registry / Maven Central |
| 契约校验 | OpenAPI 3.0 规范解析 + 前端调用静态扫描 |
| 安全扫描 | 正则模式匹配（API Key / Token / 数据库连接串 / 私钥） |
| 示例项目后端 | FastAPI + SQLAlchemy + Chroma + JWT |
| 示例项目前端 | Streamlit（多页面） |

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/<your-username>/ai-dev-workflow.git
cd ai-dev-workflow

# 安装 CLI 工具（安装后全局可用 wf 命令）
pip install -e .
```

### 启动一个新项目

```bash
# 1. 从模板创建项目（自动复制目录结构 + 初始化进度看板）
wf init my-project --desc "一个基于 RAG 的智能问答系统，使用 FastAPI + Chroma"

# 2. 查看所有项目及当前阶段
wf list

# 3. 查看某个项目的进度看板
wf status my-project

# 4. 获取当前步骤应使用的提示词模板
wf next my-project

# 5. 打印指定步骤的提示词模板
wf prompt 2       # 第 2 步 技术架构设计
wf prompt 8.5     # 第 8.5 步 安全扫描
```

### 机器校验

```bash
# 依赖版本真实性校验（解析 requirements.txt / package.json / pom.xml，批量查官方源）
wf check deps ./projects/my-project/05_代码/backend

# 硬编码密钥扫描
wf check secrets ./projects/my-project/05_代码

# 导出后端 OpenAPI 契约
wf check contract export http://127.0.0.1:8000/openapi.json ./openapi.json

# 校验前端调用符合契约（0 臆造接口）
wf check contract check ./openapi.json ./projects/my-project/05_代码/frontend

# P0 自动化回归测试
wf check regression ./projects/my-project/08_测试/cases/p0_cases.json
```

### 失败日志

```bash
wf log my-project --step 6 --category 真实运行报错 \
  --desc "启动后端时报 ModuleNotFoundError: no module named 'chromadb'" \
  --root-cause 幻觉依赖/版本
```

---

## 示例项目：生产异常答疑 AI 助手

基于本工作流全流程交付的真实项目，位于 `projects/生产异常答疑AI助手/`。

### 项目定位

面向生产环境运维场景的智能答疑系统：用户上传异常处理文档构建知识库，提问时通过 RAG 混合检索召回相关知识，大模型生成答案；未命中时自动降级为工单派单。

### 核心成果

| 维度 | 数据 |
|---|---|
| 后端代码 | 49 个 Python 文件 / 2086 行 |
| 前端代码 | 10 个 Python 文件 / 774 行，8 个页面 |
| 数据库 | 12 张表（用户 / 会话 / 消息 / 工单 / 知识库 / 文档 / 审核 / 通知 / 评估等） |
| API 接口 | 25 个路由，OpenAPI 契约导出 |
| RAG 策略 | 向量检索 + BM25 混合检索 + 分级三级兜底（知识库命中 → 大模型直答 → 自动派单） |
| 全链路联调 | 47 项 e2e 断言，第 2 轮 47/47 PASS |
| 全量测试 | P0 自动化 20/20 通过，边界测试 11 项全绿 |
| 安全扫描 | 密钥扫描 0 命中；修复 P1 路径穿越漏洞；人工渗透 8 项通过 |
| 最终验收 | 用户走查 A1-A7 全过，验收通过 |

### 文档产物链

```
projects/生产异常答疑AI助手/
├── 01_项目基线说明书.md
├── 02_架构设计/
│   ├── 第一轮技术架构设计文档.md
│   └── 第二轮技术架构设计文档.md
├── 03_评审报告/
│   ├── 第一轮架构评审报告.md
│   └── 第二轮架构复审报告.md
├── 04_任务拆解与开发规范.md
├── 05_代码/
│   ├── backend/    (FastAPI + RAG)
│   └── frontend/   (Streamlit)
├── 06.5_契约/      (openapi.json + 校验记录)
├── 06_冒烟/        (冒烟记录 + 验证脚本)
├── 07_联调/        (问题清单 + 修复说明 + 回归验证报告 + e2e 脚本)
├── 08_测试/        (用例清单 + Bug 清单 + 回归报告 + p0_cases.json)
├── 08.5_安全扫描/  (安全扫描报告 + 3 个扫描脚本)
├── 09_验收/        (最终验收清单与报告)
└── 10_交付/        (项目交付包与复盘报告)
```

---

## 目录结构

```
ai-dev-workflow/
├── README.md                  ← 你正在看的
├── WORKFLOW_工作流主控.md       ← 工作流执行手册（AI 按此执行，规定 10 步怎么走、卡点怎么停）
├── AGENTS.md                  ← 项目规则（给 AI Agent 看的行为约束）
├── pyproject.toml             ← Python 包配置（pip install -e . 后可用 wf 命令）
├── LICENSE                    ← MIT 许可证
├── .gitignore
├── prompts/                   ← 10 步 + 2 附录的全部提示词模板
│   ├── step01_项目基线定义.md
│   ├── step02_技术架构设计.md
│   ├── step03_架构评审卡点.md
│   ├── step04_任务拆解与开发规范.md
│   ├── step05A_后端开发.md
│   ├── step05B_前端开发.md
│   ├── step06_本地运行与冒烟.md
│   ├── step07_全链路联调.md
│   ├── step08_全量测试.md
│   ├── step08_5_安全扫描.md
│   ├── step09_最终验收.md
│   ├── step10_交付复盘.md
│   ├── appendixA_通用修复回归模板.md
│   └── appendixB_上下文裁剪策略.md
├── scripts/                   ← 5 项自动化校验脚本
│   ├── dependency_checker.py      依赖版本真实性校验
│   ├── api_contract_validator.py  OpenAPI 接口契约校验
│   ├── security_scan_secrets.py   硬编码密钥扫描
│   ├── p0_regression_test.py      P0 自动化回归测试
│   ├── log_failure.py             失败日志结构化记录
│   └── README_脚本说明.md
├── workflow_cli/              ← CLI 工具源码
│   ├── __init__.py
│   └── cli.py
├── projects/
│   ├── _TEMPLATE_新项目/          ← 新项目模板（wf init 从这里复制）
│   └── 生产异常答疑AI助手/         ← 真实示例项目（10 步全流程交付）
└── docs/
    └── 参考资料/
```

---

## 核心设计原则

1. **卡点不跳过**：架构评审、本地冒烟、安全扫描、最终验收，必须人工确认，AI 不替用户下结论。
2. **机器校验优先于 AI 自检**：脚本结果才是判据，AI 的评审/报告只是参考。
3. **真实报错驱动修复**：第 6 步起所有修复基于真实终端报错，禁止凭空猜 Bug。
4. **失败必记录**：任何返工、卡点拦截、评审打回，当场记入项目 `_失败日志.md`。
5. **Bug 只修 3 轮**：全量测 1 轮 + 修复回归最多 2 轮，超限走架构回流或留 P2/P3 到下版本。
6. **产物落盘**：每步产出写入项目对应编号目录，不靠对话记忆充当产物；`_项目状态.md` 是唯一进度看板。

---

## License

[MIT](./LICENSE)
