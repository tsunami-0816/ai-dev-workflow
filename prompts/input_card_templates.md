# 输入卡模板集

> 每个步骤开始时必读的结构化输入卡。
> 上一步产出时必须同时生成下一步的输入卡，放在对应目录下，文件名 `input_card.yaml`。

---

## step5A 后端开发输入卡

> 位置：`05_代码/backend/input_card.yaml`
> 由 step4 任务拆解完成时生成

```yaml
step: 5A
project: <项目名>
generated_by: step4
generated_at: <日期>

# 技术栈
tech_stack:
  backend: <语言+框架，如 Java 17 + Spring Boot 3>
  db: <数据库，如 MySQL 8 + Redis 7>
  mq: <消息队列，如 RabbitMQ，无则空>

# 端口分配（从 WORKFLOW_端口分配表.md 取）
ports:
  backend: <端口>
  mysql: <端口>
  redis: <端口>

# P0 任务清单（从 step4 任务拆解复制）
tasks:
  - task_id: T01
    desc: <任务描述>
    endpoint: <接口路径，如 POST /api/v1/workflows>
    risk_level: <高/中/低>
    contract_ref: <契约路径，如 06.5_契约/openapi.json#/paths/~1api~1v1~1workflows/post>

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
generated_by: step4
generated_at: <日期>

# 技术栈
tech_stack:
  frontend: <框架，如 Vue 3 + Vite>
  ui_library: <UI 库，如 Element Plus>

# 端口分配
ports:
  frontend: <端口>

# 项目类型（R25）
project_type: <b2b-admin / internal-tool / landing / portfolio>

# 设计模式（R24）
design_mode: <普通 / 精修>

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
    risk_level: <高/中/低>

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
generated_by: step5.5
generated_at: <日期>

# 启动命令
startup:
  backend_cmd: <后端启动命令>
  frontend_cmd: <前端启动命令>
  docker_cmd: docker compose up -d

# 健康检查 URL
health_urls:
  backend: <后端健康检查 URL>
  frontend: <前端首页 URL>

# P0 任务清单（主流程路径）
p0_tasks:
  - task_id: T01
    desc: <任务描述>
    user_path: <用户操作路径，如 打开首页→点击登录→输入账号密码→点击登录>

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
