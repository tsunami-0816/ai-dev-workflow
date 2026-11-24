# 第 8 步 · pytest 四层自动化测试

> 路线=生产；环境口径：后端 8092、云函数 8093、H5 5186、MySQL 3307、Redis 6379、MQ 5672/15672。
> 一键：`pytest -q`（自动 allure-results）；性能：`python perf_test.py`。

## 分层

| 层 | 目录 | 用例数 | 内容 |
|---|---|---|---|
| L1 | `testcases/l1_unit/` | 8 pytest + 10 JUnit | 纯函数/契约静态/幂等键/手机号；后端 PasswordHasher 5 + JwtService 5 |
| L2 | `testcases/l2_api/` | 58 | 健康、登录登出、套餐分页/详情、预约四象限、CORS、云函数代理、账号自动补种 |
| L3 | `testcases/l3_integration/` | 8 | 真实 Redis 命中率/单飞、DB+MQ 落库/重放、DLQ、openid mock、C06 十条 |
| L4 | `testcases/l4_e2e/` | 3 + 2 UI | 直连/云函数主链路；Q-020 滚到底、Q-025 长说明折叠 |

## L3 降级说明

本机 16GB 内存且 Docker 中间件已常驻，未用 Testcontainers 另起容器；按 step08 文档允许的
「docker-compose 起好中间件后手动连」执行，风险：用例会写真实测试库，靠 fixture 自造自清。

## 账号兜底（硬规则）

本项目无注册接口，账号来自 `db/init.sql` 种子（`demo` / `demo2`，口令 `welcome1`）。
`testcases/conftest.py` 先正常登录；若失败，用 `common/account_util.py` 按后端同参数
（PBKDF2-HmacSHA256 / 120000 / 32B / 标准 Base64，格式 `pbkdf2$120000$<saltB64>$<hashB64>`）
直接补种/纠正账号后再登录，不依赖人工准备口令。链路有效性由
`test_autoprovisioned_account_can_login` 每次全量回归验证（临时账号 finally 删除）。

## 性能测试

- 入口：`python perf_test.py --duration 10 --concurrency 10,20,50 --booking-samples 30`
- JMeter 交叉：`jmeter/packages_read.jmx`（定压）、`summarize_jtl.py` 汇总 JTL。
- 报告正文：`../性能测试报告.md`；本目录 `perf-report.md` 为指针与摘要。
- 原始结果：`reports/perf_result.json`、`reports/jmeter_summary.json`、`jmeter/result_10.jtl`、`result_50.jtl`。

## 目录

`config/` 配置、`common/` 工具、`api/` 接口封装、`testcases/` 四层用例、`ui/` Puppeteer 证据脚本、
`jmeter/` 压测计划与 JTL、`reports/` 结果与 Allure、`data/` 预留测试数据落盘目录、`evidence/`（上级目录）留证。

## 数据纪律

- 每条用例自造数据、finally 清理（`booking_factory` 删 notify_log/booking + 幂等键）；
- 临时套餐（Q-025）id=9001，用完即删并清 `ub:pkg:list`；
- 不读历史行做断言，不依赖执行顺序。
