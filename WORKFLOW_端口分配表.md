# 端口分配表

> 所有项目共用一套基础设施，后端端口按项目固定分配。
> **开工时 env_preflight.py 自动检查本表**：项目配置的端口被占用且不是本项目进程 → 报红，禁止启动。

## 基础设施（所有项目共用，固定不变）

| 服务 | 宿主机端口 | 容器名 | 说明 |
|---|---|---|---|
| MySQL 8.0 | **3310** | 05_-mysql-1 | 所有项目共用，不同项目用不同 database |
| Redis 7.2 | **6379** | 05_-redis-1 | 所有项目共用，不同项目用不同 db index |
| Kafka | **9092** | saas-kafka | 需要时共用 |
| ClickHouse | 3310 容器内 | 05_-clickhouse-1 | 未映射宿主机端口，需要时单独映射 |

## 后端端口分配池（8081 起递增）

| 项目 | 后端端口 | 状态 | 说明 |
|---|---|---|---|
| smart-outbound-platform | 8081 | ✅ 已完成 | 单模块 Spring Boot |
| multi-tenant-crm-ticket | 8080(gw) / 8081 / 8082 | ✅ 已完成 | 三模块：gateway+customer+ticket |
| saas-workflow-agent | 8083 | ✅ 已完成 | 单模块 Spring Boot（java-backend） |
| saas-workflow-agent | 8085 | ✅ 已完成 | python-agent（FastAPI Agent 运行时，2026-10-28 架构分配） |
| enterprise-rag-agent | **8084** | ⏸️ 已搁置 | 与本地 enterprise-rag-java 重复，2026-10-31 搁置 |
| llm-eval-observability | **8086** | 🔨 进行中 | FastAPI 主服务（2026-10-30 启动分配） |
| SparrowScheduler | 8087 | ✅ 已完成 | 单模块 Spring Boot（sparrow-admin，2026-11-02 翻新线分配；Docker prod 映射 8090） |
| shopmate-ai | **8088** | ✅ 已完成 | FastAPI 主服务（2026-11-04 启动分配） |
| nestjs-agent-workbench | **8089** | 🔨 进行中 | NestJS 主服务（2026-11-08 启动分配） |
| 预留 | 8090 | | |

## 前端端口分配池（5173 起递增）

| 项目 | 前端端口 | 状态 |
|---|---|---|
| smart-outbound-platform | 5175 | ✅ 已完成 |
| multi-tenant-crm-ticket | 5176 | ✅ 已完成 |
| saas-workflow-agent | 5177 | ✅ 已完成 |
| enterprise-rag-agent | **5178** | ⏸️ 已搁置 | 2026-10-31 搁置 |
| llm-eval-observability | **5179** | 🔨 进行中 |
| SparrowScheduler | 5181 | ✅ 已完成 | Vite dev（2026-11-02 翻新线分配；Docker web 映射 3002） |
| shopmate-ai | **5182** | ✅ 已完成 | Vite dev（2026-11-04 启动分配） |
| nestjs-agent-workbench | **5183** | 🔨 进行中 | Vite dev（2026-11-08 启动分配） |

## 开工时自动分配规则（env_preflight.py）

1. 读本表，找到项目对应的后端端口和前端端口
2. 用 `netstat -ano | findstr :<port>` 检查该端口是否被占用
3. 如果被占用且占用进程不是本项目 → **报红**："端口 X 被 PID Y 占用，请先杀进程或改分配表"
4. 如果表中项目没有分配端口 → 自动从池里取下一个空闲端口，写入分配表和 application.yml
5. 基础设施端口（3310/6381/9092）启动前检查 Docker 容器是否在跑，不在跑就 `docker start`
