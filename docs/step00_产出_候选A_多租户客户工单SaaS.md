# 候选 A · 多租户客户跟进与工单 SaaS（一页纸设计书）

> 本文是 step00.5 产出，确认后直接作为新项目的 `00_原始项目描述.md`，不再重写需求分析。

---

## 1. 一句话定位

一个面向中小团队的 SaaS 多租户业务系统：销售在 CRM 里管客户、客服在工单系统里处理售后，不同公司数据隔离，高并发读场景下缓存与消息队列真实落地。

## 2. 业务场景（小而真）

你开过外卖店/做过小生意的人都知道，小团队用钉钉/企业微信管客户很乱：
- 客户资料散在销售个人微信里，人走客户走
- 售后工单靠群里吼，谁接了、处理到哪一步没人知道
- 一个客户从"咨询→下单→售后"的时间线拼不出来

本项目做一个最小可用版本：每个注册公司是一个租户，租户内有销售和客服两种角色。销售记录客户跟进，客服建工单处理售后，工单状态变更自动在客户时间线上留痕。

**MVP 范围**（不做的写在第 8 节）：
- 租户注册/登录/JWT
- 客户 CRUD + 跟进记录
- 工单 CRUD + 状态机（待处理→处理中→已解决→已关闭）
- 客户详情页时间线（自动聚合跟进记录 + 工单事件）

## 3. 技术架构

### 3.1 服务拆分（3 个，Docker Compose 起）

```
┌─────────────┐
│  Vue3 前端   │  Element Plus，简单 CRUD 页面
└──────┬──────┘
       │ HTTP
┌──────▼──────────────────────────────────┐
│  gateway-service (Spring Cloud Gateway) │  路由 + JWT 鉴权 + 租户上下文解析
└───┬───────────────────────┬────────────┘
    │                       │
┌───▼──────────┐    ┌───────▼─────────┐
│ customer-     │    │ ticket-service  │
│ service       │    │                 │
│ Spring Boot   │    │ Spring Boot     │
│ MyBatis-Plus  │    │ MyBatis-Plus    │
│ MySQL + Redis│    │ MySQL + Kafka  │
└───────────────┘    └───────┬─────────┘
                             │ 事件发布
                     ┌───────▼───────┐
                     │   Kafka      │
                     └───────┬───────┘
                             │ 消费
                     ┌───────▼───────┐
                     │ customer-svc  │
                     │  更新客户时间线 │
                     └───────────────┘
```

### 3.2 技术栈清单

| 层 | 技术 |
|---|---|
| 微服务框架 | Spring Cloud Alibaba 2022.x（Nacos 注册+配置、Gateway、OpenFeign） |
| 业务框架 | Spring Boot 3.x、MyBatis-Plus 3.5.x |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7.x（Spring Data Redis / Lettuce） |
| 消息队列 | Kafka 3.x（spring-kafka） |
| 前端 | Vue 3 + Vite + Element Plus |
| 部署 | Docker Compose（5 个容器：MySQL、Redis、Kafka、Nacos、3 个后端服务 + 前端，共 8 个） |
| 测试 | JUnit5 + Mockito（Java 单测）、Pytest + Requests + Allure（接口/E2E）、Testcontainers（集成）、JMeter（性能） |

**Docker Compose 资源估算**：8 个容器约占 6-8GB 内存，16GB 机器跑得动。

## 4. 硬骨头模块（面试能讲 10 分钟的点）

### 硬骨头 1：多租户数据隔离 + 缓存一致性

**问题**：
- 多租户用字段隔离（`tenant_id` 列）还是独立 Schema？trade-off 是什么？
- 客户详情是高频读数据，怎么缓存？缓存和 DB 双写不一致怎么办？

**方案**：
- 采用**字段隔离**：所有业务表带 `tenant_id`，MyBatis 拦截器自动拼接 `WHERE tenant_id = ?`，业务代码无感知。写一份对比文档说明为什么 MVP 阶段不上独立 Schema。
- Redis 缓存客户详情：
  - **缓存穿透**：布隆过滤器（Redisson RBloomFilter）拦截不存在的客户 ID
  - **缓存击穿**：热点 key 过期时用 Redis 分布式锁（Redisson RLock）只放一个请求回源
  - **缓存雪崩**：过期时间加随机偏移（基础 30min ± 5min）
  - **双写一致性**：采用"先更新 DB → 再删除缓存"（延迟双删），不做 Cache-Aside 写入
- 压测对比：缓存命中 vs 未命中的 QPS / P99 延迟，用 JMeter 出报告

**面试讲法**："我选字段隔离是因为 MVP 阶段租户少、运维简单，但我知道字段隔离的代价是跨租户查询容易漏过滤，所以用 MyBatis 拦截器兜住；缓存一致性我踩过双写不一致的坑，最终用延迟双删 + 布隆过滤器解决。"

### 硬骨头 2：Kafka 异步最终一致性

**问题**：
- 工单状态变更后，客户时间线要自动显示这个事件，怎么做？
- Kafka 消息重复消费怎么办？消息丢了怎么办？顺序性怎么办？

**方案**：
- ticket-service 工单状态流转后，**本地消息表**记录事件，定时任务投递到 Kafka（不直接发，避免 DB 和 Kafka 不在一个事务）
- customer-service 消费 `ticket.status.changed` 主题，写客户时间线表
- **幂等消费**：消费端用事件 ID 唯一索引 + 工单状态机防重入（已关闭的工单不能再被"处理中"事件覆盖）
- **死信队列**：连续失败 3 次的消息进 DLQ，人工介入
- **顺序性**：按 `customer_id` hash 分区，同一客户的工单事件进同一分区，保证局部有序

**面试讲法**："我没有用 Seata，因为 MVP 阶段上分布式事务框架太重，本地消息表 + Kafka 是更轻的最终一致性方案；重复消费我踩过坑，工单状态被重复消息回退，最终用唯一索引 + 状态机兜住。"

## 5. JD 技能点对账表

| JD 技能点 | 在本项目的落地位置 | 覆盖深度 |
|---|---|---|
| Java | 三个后端服务全部 Java 17 | 深入 |
| Spring Cloud | Gateway + Nacos + OpenFeign | 深入 |
| MySQL | 业务库 + 本地消息表 + 时间线表 | 深入 |
| MyBatis | MyBatis-Plus + 多租户拦截器 | 深入 |
| Redis | 客户详情缓存 + 布隆过滤器 + 分布式锁 | 深入 |
| Kafka | 工单事件驱动 + 本地消息表 + DLQ | 深入 |
| 高并发 | JMeter 压测客户列表接口，缓存命中 vs 未命中对比 | 中级（压测数据说话） |
| 高可用 | Kafka 重试/DLQ、Redis 降级（缓存挂了直接回源 DB） | 中级 |
| SaaS | 多租户字段隔离 + 拦截器 | 深入 |
| Git Flow / PR / Code Review | GitHub 仓库 + PR 模板 + 分支保护 | 中级（工程规范） |
| AI 编程工具 | 开发过程使用 Codex/Cursor，README 记录提效数据 | 中级 |
| Pytest / Allure | 见第 6 节测试体系 | 深入 |
| 性能测试 | JMeter 压测报告 + TPS/瓶颈分析 | 中级 |

**脚本覆盖率校验**：JD2 硬标签 7 个（Java/SpringCloud/MySQL/Kafka/Redis/MyBatis/Spring）全部覆盖；JD1 的 SaaS/AI Agent/Git 工程规范覆盖。

## 6. 测试体系（重点，覆盖测试开发方向）

这是本项目区别于普通 CRUD 项目的核心。测试体系本身就是测试开发岗的作品。

### 6.1 四层测试金字塔

| 层 | 工具 | 测什么 | 产物 |
|---|---|---|---|
| L1 单元测试 | JUnit5 + Mockito | service 层业务逻辑、状态机、拦截器 | jacoco 覆盖率报告 ≥ 70% |
| L2 接口测试 | Python + Pytest + Requests | 对 OpenAPI 做契约测试，覆盖所有 REST 接口 | Allure HTML 报告 |
| L3 集成测试 | Testcontainers | 起真实 MySQL/Redis/Kafka，测跨服务交互（建工单→Kafka 事件→客户时间线更新） | Allure 报告 |
| L4 端到端 | Pytest | 核心业务链路：租户注册→登录→建客户→建工单→状态流转→时间线可见 | Allure 报告 + CI badge |

### 6.2 Allure 报告组织

- 按 Epic / Feature / Story 分类：Epic = 模块（客户/工单/租户），Feature = 接口组
- 按严重级别标注：Blocker / Critical / Normal / Minor
- CI 里跑 `pytest --alluredir` 生成报告，GitHub Pages 托管

### 6.3 性能测试

- JMeter 压测客户列表接口：缓存命中（预期 2000+ QPS）vs 缓存未命中（预期 200 QPS）
- 压测工单状态流转接口：单服务 + Kafka 异步链路
- 输出：TPS、P50/P95/P99、错误率、瓶颈定位（DB 慢查询？Redis 延迟？）

### 6.4 安全测试（沿用工作流 step8.5）

- `security_scan_secrets.py` 扫硬编码密钥
- `pip-audit` / `npm audit` 扫依赖 CVE
- `.env.example` 与代码环境变量差集校验

## 7. 工作量拆解（共 15 人天）

| 模块 | 人天 | 说明 |
|---|---|---|
| 项目骨架 + Nacos/Gateway + 租户登录/JWT | 2 | 脚手架跑通 |
| customer-service（客户 CRUD + 跟进 + Redis 缓存 + 布隆过滤器） | 3 | 含硬骨头 1 |
| ticket-service（工单 CRUD + 状态机 + Kafka + 本地消息表） | 3 | 含硬骨头 2 |
| customer-service Kafka 消费 + 客户时间线聚合 | 1 | |
| Vue3 前端（登录 + 客户列表/详情 + 工单列表/详情） | 3 | 简单 CRUD 页面，不做花哨 |
| L1+L2 测试（JUnit + Pytest 接口） | 1.5 | |
| L3+L4 测试（Testcontainers + E2E） | 1.5 | |
| JMeter 压测 + 报告 | 0.5 | |
| README + 部署文档 + 收尾 | 0.5 | |

**超过 15 人天就砍范围**：优先砍前端页面美化，不砍测试体系和硬骨头。

## 8. 主动砍掉的东西（反粗制滥造）

| 砍掉的内容 | 原因 |
|---|---|
| JD2 提到的"存算分离""全球化部署""分布式数据库""大数据" | 大厂 C 轮公司真实技术栈，个人项目不可能实现，硬塞就是造假。面试时诚实说"了解原理，项目里用 Redis + Kafka 模拟了高并发和最终一致性" |
| Spring Cloud Alibaba 全套（Sentinel/Seata/Sleuth） | 只用到 Gateway + Nacos + OpenFeign，其他不上，避免过度设计 |
| 独立 Schema 多租户方案 | MVP 阶段字段隔离够了，写对比文档说明 trade-off 即可 |
| 微服务拆 5+ 个服务 | Docker Compose 起不动，3 个服务是上限 |
| 权限管理（RBAC 完整实现） | MVP 只分销售/客服两种角色，不做完整权限矩阵 |
| 报表/数据分析看板 | 大而空，不做 |
| AI Agent 集成 | 这是候选 B 的事，本项目不碰 |

## 9. 面试三问答案

**Q1：为什么用 Spring Cloud Alibaba 不用 Netflix 那套？**
A：Netflix OSS 已经停更（Eureka/Hystrix/Zuul），Spring Cloud Alibaba 适配国内生态，Nacos 把注册中心和配置中心合一减少运维组件，Gateway 比 Zuul 性能好（WebFlux 非阻塞）。MVP 阶段不需要 Sentinel 的完整流控，用简单的 Redis 限流就够。

**Q2：项目最难的技术问题是什么？怎么解决的？**
A：两个。
- 一是缓存与 DB 双写不一致：客户详情更新后，旧缓存没删干净，列表页看到旧数据。最终用"先更新 DB → 延迟 500ms 再删缓存"（延迟双删），加 Redis key 版本号兜底。
- 二是 Kafka 重复消费导致工单状态错乱：测试时手动重投消息，工单从"已关闭"被回退到"处理中"。最终消费端做幂等：事件 ID 唯一索引 + 状态机校验（已关闭的工单拒绝任何状态变更事件），异常消息进 DLQ。

**Q3：如果再做一次你会怎么改？**
A：
- 多租户直接上独立 Schema（小租户数量下运维成本可接受，省掉拦截器的心智负担）
- 测试体系提前到开发阶段写（这次是后端写完才补测试，应该 TDD）
- 前端用低代码或 Admin 模板减少开发量，把时间省在测试和压测上
- 引入 OpenTelemetry 做链路追踪，现在跨服务排查问题靠日志 grep

## 10. 风险点

- **Nacos 单机模式**：生产是集群，MVP 单机够，面试要说明
- **Kafka 在 Windows Docker 里性能一般**：压测数据不要吹太高，诚实报告
- **多租户拦截器漏过滤风险**：必须有自动化测试验证"租户 A 查不到租户 B 的数据"，这是安全红线
- **用户基础薄弱点**：Spring Cloud、Kafka 可能不熟，开发过程用 Codex/Cursor 辅助，但要自己读代码理解，不能跑完就交
