# 输入卡模板集

> 每个步骤开始时必读的结构化输入卡。
> 上一步产出时必须同时生成下一步的输入卡，放在对应目录下，文件名 `input_card.yaml`。
> **开工前先过机器校验（G1）**：`python scripts/input_card_check.py <step> <卡路径> --project <项目目录>`，卡不绿不动手。
> Schema 唯一事实源：`workflow/input_card_schema.yaml`；历史项目豁免。

---

## 通用字段（所有步骤必填）

```yaml
step: 5A
project: <项目名>
updated_at: "2026-11-11 14:30"
sources:            # 上游产物引用，必须真实存在于项目目录内
  - 02_架构设计/第一轮技术架构设计文档.md
  - 04_任务拆解与开发规范.md
```

---

## step1 项目基线输入卡

> 位置：`01_项目基线说明书.md.input_card.yaml`（根级步骤的卡与产物同名）
> 由 step00 冻结原始描述后生成；step1 产出基线时补齐 `baseline_ref / scope_ref`

```yaml
step: "1"
project: <项目名>
updated_at: "2026-11-11 14:30"
sources:
  - 00_原始项目描述.md
baseline_ref: 01_项目基线说明书.md
scope_ref: 01_项目基线说明书.md#3-范围界定
```

---

## step4 任务拆解输入卡

> 位置：`04_任务拆解与开发规范.md.input_card.yaml`
> 由 step3 架构评审结论产出后生成；任务项必须能映射到基线 criterion

```yaml
step: "4"
project: <项目名>
updated_at: "2026-11-11 14:30"
sources:
  - 02_架构设计/第一轮技术架构设计文档.md
  - 03_评审报告/第一轮架构评审报告.md
arch_ref: 02_架构设计/第一轮技术架构设计文档.md
tasks:
  - task_id: T01
    desc: <任务描述>
    risk: 中
    criterion_ref: C01
scope:
  files_in_scope:
    - 05_代码/backend/**
  out_of_scope:
    - 05_代码/frontend/**
limits:
  max_files: 60
  max_attempts: 5
  timeout_min: 120
```

---

## step5A 后端开发输入卡

> 位置：`05_代码/backend/input_card.yaml`
> 由 step4 任务拆解完成时生成

```yaml
step: 5A
project: <项目名>
updated_at: "2026-11-11 14:30"
sources:
  - 02_架构设计/第一轮技术架构设计文档.md
  - 04_任务拆解与开发规范.md

# 技术栈
tech_stack:
  backend: <语言+框架，如 Java 17 + Spring Boot 3>
  db: <数据库，如 MySQL 8 + Redis 7>
  mq: <消息队列，如 RabbitMQ，无则空>

# 端口分配（从 WORKFLOW_端口分配表.md 取）
ports:
  backend: 8083
  mysql: 3310
  redis: 6379

# P0 任务清单（从 step4 任务拆解复制）
tasks:
  - task_id: T01
    desc: <任务描述>
    endpoint: <接口路径，如 POST /api/v1/workflows>
    risk: <低/中/高/关键>
    criterion_ref: [C01, C02]      # G8：挂接基线量化指标 id，可多值
    contract_ref: <契约路径，如 06.5_契约/openapi.json#/paths/~1api~1v1~1workflows/post>

# 改动范围与限额（G2；step5 不得自行扩大）
scope:
  files_in_scope:
    - "05_代码/backend/workflow/**"
    - "05_代码/backend/controller/**"
  out_of_scope:
    - "05_代码/frontend/**"
    - "**/docker-compose.yml"
    - "**/auth/**"
limits:
  max_files: 12
  max_attempts: 3
  timeout_min: 20

# 硬件约束
hardware_limit: RTX 2050 4GB + 16GB 内存

# Mock 策略
mock_policy: 外部依赖必须 Mock，带 # MOCK: 注释

# 必读文件
must_read:
  - 01_项目基线说明书.md
  - 02_架构设计/第一轮技术架构设计文档.md
  - 04_任务拆解与开发规范.md
```

---

## step5B 前端开发输入卡

> 位置：`05_代码/frontend/input_card.yaml`
> 由 step4 任务拆解完成时生成（step5A 产出 Mock 后才能开始）

```yaml
step: 5B
project: <项目名>
updated_at: "2026-11-11 14:30"
sources:
  - 02_架构设计/第一轮技术架构设计文档.md
  - 04_任务拆解与开发规范.md

# 技术栈
tech_stack:
  frontend: <框架，如 Vue 3 + Vite>
  ui_library: <UI 库，如 Element Plus>

# 端口分配
ports:
  frontend: 5177

# 项目类型（R25）
project_type: <b2b-admin / internal-tool / landing / portfolio>

# 设计模式（R24）
design_mode: <普通 / 精修>

# G9 门面页方向稿（仅 landing/portfolio 或看板标注含门面页时必填；业务页省略）
design_ref:
  direction_doc: 02_架构设计/门面页方向稿.md
  approved_by_user: true          # 👤 卡点：用户确认方向后才动工

# 契约前置检查（D4）
contract_check:
  contract_file: 06.5_契约/openapi.json
  min_paths: 1
  pre_check_cmd: python scripts/api_contract_validator.py check 06.5_契约/openapi.json 05_代码/frontend

# P0 任务清单
tasks:
  - task_id: T101
    desc: <任务描述>
    page: <页面路径，如 /login>
    risk: <低/中/高/关键>
    criterion_ref: [C01]

# 改动范围与限额（G2）
scope:
  files_in_scope:
    - "05_代码/frontend/src/**"
  out_of_scope:
    - "05_代码/backend/**"
limits:
  max_files: 12
  max_attempts: 3
  timeout_min: 20

# 必读文件
must_read:
  - 02_架构设计/第一轮技术架构设计文档.md
  - 04_任务拆解与开发规范.md
```

---

## step6 冒烟输入卡

> 位置：`06_冒烟/input_card.yaml`
> 由 step5.5 reviewer 完成时生成

```yaml
step: 6
project: <项目名>
updated_at: "2026-11-11 14:30"
sources:
  - _设计实施映射表.md

# 待冒烟的代码目录
code_dirs:
  - 05_代码/backend
  - 05_代码/frontend

# 启动命令
start_commands:
  backend_cmd: <后端启动命令>
  frontend_cmd: <前端启动命令>
  docker_cmd: docker compose up -d

# 健康检查 URL（探针）
probe_urls:
  backend: <后端健康检查 URL>
  frontend: <前端首页 URL>

# P0 主流程路径（指向映射表 / 用例清单）
p0_ref:
  mapping_rows: [D-01, D-02, D-03]
  user_paths:
    - <用户操作路径，如 打开首页→点击登录→输入账号密码→点击登录>

# Mock 检查
mock_check:
  must_have_mock: <外部依赖列表>
  mock_comment_format: "# MOCK:"

# 必读文件
must_read:
  - 05_代码/backend/
  - 05_代码/frontend/
  - _设计实施映射表.md
```

---

## 使用规则

1. 上一步产出时必须同时生成下一步的输入卡，不能只写产物不写卡
2. Agent 执行某步时，先读本步的 `input_card.yaml`，不预加载上游产物全文
3. 输入卡 ≤ 1 页，超过说明信息冗余，需要精简
4. 输入卡是"指针式"的——关键字段都带引用路径，需要详细信息时才按需读
5. 卡内 `scope` / `limits` 是本步改动边界与限额，实现不得越界；越界改动在 5.5 Review 记越界项
