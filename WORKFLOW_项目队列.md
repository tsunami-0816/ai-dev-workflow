# 项目队列

> step00 一次会从若干份 JD 设计出多个候选项目；生产线按工位制推进（默认期 1 串行 1 → 期 2 双工位 → 期 3 三工位），规则见下方「产能规则」。
> 所有选中的项目先入这个队列，由 `scripts/slots.py` 按「能解锁 JD 数」自动排工位，每步用 `scripts/run_log.py` 留痕。
> **状态机**：待开工 → 进行中 → 已完成；或 → 已搁置（业务方向作废/硬件跑不动）。
> **候选池 ≠ 待开工**：backlog 里标「候选」的项目（如 #115 研发效能度量看板）只登记想法，**不在本队列总表、不占生产线**；必须先过 step00 选题闸门（JD 对账 / 撞车检查 / 硬件约束 / 工作量 ≤15 人天砍到 MVP）拍板，设计书入 `projects/_队列/` 后状态才标「待开工」。

## 产能规则（2026-11-22 拍板·期 1 起生效：双工位 → 三工位）

> 2026-11-15 的「串行=1」是为了防上下文爆掉；2026-11-22 用户授权改为并行，但**分三期上**：期 1 只看不动（仍串行 1）→ 期 2 双工位（1 运行 + 1 生成）→ 期 3 三工位（1 运行 + 2 生成）。并行不是"同时想 3 个项目"，是"每轮只推进 1 个项目、一天内多个工位各进一步"。

- **工位分工**：起服务、占端口、跑浏览器、要人工走查的只进运行槽（同一时刻 1 套）；写文档、写代码、跑单测的进生成槽。**当前生效档位写在 `_生产运行日志.md` 最新一行的「档位」列**。
- **升级条件**：期 2 需期 1 达标（看板排序正确、每日卡点 ≤3 条）；期 3 需期 2 达标（单项目 ≤2 天、门禁首轮通过率 ≥70%）。
- **回退红线**：单项目耗时 >2.5 天，或门禁首轮通过率 <60% → 立刻降一档，并在运行日志写明原因。
- **上下文隔离（硬规则）**：每轮切到某工位，只读该项目的 `_项目状态.md` + 最近 1 个产物；禁止把多个项目的代码/报错/文档同时装进上下文。
- **卡点批处理**：所有人工卡点汇总到 `projects/_生产并行看板.md`「待你 1 分钟」，一次答完；答完前其他工位照常推进。
- **完成即接**：任一工位空出，立刻从待开工里按「能解锁 JD 数」补位（`scripts/slots.py` 自动排）。
- **每步留痕（硬规则）**：每推进一步，用 `py -3.11 scripts/run_log.py add` 往 `projects/_生产运行日志.md` 追加一行（时间/档位/工位/项目/步骤/产物/闸门退出码/耗时/异常）；看板每次运行用 `slots.py --archive` 归档到 `projects/_看板归档/<日期>.md`。**没有日志行的推进，视为没发生。**
- **单项目预算 ≤5 人天**：并行提吞吐，不放开范围；超预算仍拆能力簇。
- **卡 24h 必上报**：任一工位「当前卡点」非「无」超过 1 天，当天日巡检列为阻塞项。
- **搁置要有判定理由**：已搁置项目必须在「当前卡点」写明"与哪个已交付项目重复 / 零增量在哪"，否则不许挂搁置（防"假在产"）。

### 工位规则与留痕命令速查

| 命令 | 作用 |
|---|---|
| `py -3.11 scripts/slots.py --archive` | 重排工位 + 归档当日看板 |
| `py -3.11 scripts/run_log.py add --slot B --project <名> --step 1 --product <路径> --gate "step_gate_check --step 1" --exit 0 --minutes 25` | 追加一条运行记录 |
| `py -3.11 scripts/run_log.py kpi` | 算日产出 / 单项目耗时 / 门禁首轮通过率 / 每日卡点数 |
| `py -3.11 scripts/run_log.py tail -n 20` | 看最近 20 条执行历史 |
## 队列总表

> 🤖 **事实列**：`状态` / `完成日期` / `当前卡点` 由 `wf queue --sync` 从各项目 `_项目状态.md` + 门禁脚本自动推导生成，**禁止手改**（手改会被 `wf queue --check` 报红）。计划列（项目名 / 业务一句话 / 设计书路径 / 来源 JD / 启动日期 / 排序）仍由人维护。
> **路线取值**：`生产`（step00–11，从 0 到 1）/ `翻新`（F0–F4，既有项目逆向补证据）/ `迭代`（I0–I3，已闭环项目加增量能力）。

| 项目名 | 路线 | 业务一句话 | 设计书路径 | 状态 | 来源 JD | 启动日期 | 完成日期 | 当前卡点 |
|---|---|---|---|---|---|---|---|---|
| multi-tenant-crm-ticket | 生产 | 多租户客户工单 SaaS（Java 后端 + 测试开发双栖） | `projects/multi-tenant-crm-ticket/00_原始项目描述.md` | 已完成 | step00 产出 | 2026-10-26 | 2026-10-27 | 无（门禁全绿） |
| smart-outbound-platform | 生产 | FreeSWITCH+LLM AI 外呼机器人，可视化对话流程画布 | `projects/smart-outbound-platform/00_原始项目描述.md` | 已完成 | JD4/JD5/JD6/JD13 | 2026-10-27 | 2026-10-27 | 无（门禁全绿） |
| 生产异常答疑AI助手 | 生产 | 企业生产异常 RAG 问答 | `projects/生产异常答疑AI助手/00_原始项目描述.md` | 已豁免 | 2026-10-19 | 2026-10-19 | 2026-10-20 | 2026-10-19 完成，早于 2026-10-27 门禁脚本上线日。补造 6.5/8.5/台账等产物属于补造证据，不做。 |
| saas-workflow-agent | 生产 | SaaS 自动化工作流编排（v1 企业级完整版，挑战版） | `projects/_队列/saas-workflow-agent/00_项目设计书.md` | 已完成 | JD1/JD3/JD11/JD12/JD15/JD20/JD29 | 2026-10-28 | 2026-11-01 | 无（门禁全绿） |
| llm-eval-observability | 生产 | LLM 应用评测与可观测平台（v1 企业级完整版，挑战版） | `projects/_队列/llm-eval-observability/00_项目设计书.md` | 已完成 | JD5/JD11/JD18/JD20/JD21 | 2026-10-30 | 2026-10-30 | 无（门禁全绿） |
| enterprise-rag-agent | 生产 | 企业知识库RAG问答Agent（文档上传→向量检索→带引用回答） | `projects/_队列/enterprise-rag-agent/00_项目设计书.md` | 已搁置 | 设计模块产出 | 2026-10-27 | - | 与本地已有 `D:\lg\project\enterprise-rag-java`（Spring Boot+LangChain4j+Qdrant+DashScope 企业级完整版，已在简历）重复；队列版为 Java+Python 双栈阉割 MVP，无简历增量（2026-10-31 搁置） |
| light-workflow-studio | 生产 | 轻量流程画布（v2 保底版，3种节点线性执行） | `projects/_队列/light-workflow-studio/00_项目设计书.md` | 已搁置 | v1 返厂重做 | 2026-10-28 | - | v1 saas-workflow-agent 已于 2026-10-28 闭环交付（11步全绿/用户验收）；v2 后端为 v1 阉割版，唯一增量是 AntV X6 拖拽画布（v1 为表单式 DSL 配置），增量不足以再做一个项目（2026-10-31 搁置） |
| llm-trace-dashboard | 生产 | LLM 调用追踪看板（v2 保底版，手动录入+ECharts） | `projects/_队列/llm-trace-dashboard/00_项目设计书.md` | 已搁置 | v1 返厂重做 | 2026-10-28 | - | 与 v1 llm-eval-observability 重复：v1 已于 2026-10-30 闭环交付（含 ECharts 看板/trace 列表/metrics，已推 GitHub public）；v2 砍成手动录入+SQLite，零增量（2026-10-31 搁置） |
| shopmate-ai | 生产 | ShopMate 电商AI客服运营工作台（LangGraph+RAG+文案生成+反馈闭环） | `projects/_队列/shopmate-ai/00_项目设计书.md` | 已完成 | AI运营含界面设计JD | 2026-11-04 | 2026-11-05 | 无（门禁全绿） |
| nestjs-agent-workbench | 生产 | Node.js NestJS AI对话工作台（补Node.js缺口，WebSocket流式+JWT/RBAC） | `projects/_队列/nestjs-agent-workbench/00_项目设计书.md` | 已完成 | 垦驱智能Agent岗（求职侧设计台） | 2026-11-08 | 2026-11-08 | 无（门禁全绿） |
| SparrowScheduler | 翻新 | 分布式任务调度平台（翻新线·野生入口） | `projects/SparrowScheduler/00_项目设计书.md` | 已完成 | 野生入口迁入 | 2026-11-02 | 2026-11-03 | 无（门禁全绿） |
| cpp-game-server-kit | 生产 | 现代 C++ 游戏服务器基础设施套件（epoll Reactor + 无锁日志 + Protobuf 网关 + KCP 帧同步战斗服） | `projects/_队列/cpp-game-server-kit/00_项目设计书.md` | 已完成 | 求职侧设计台：杭州游梦光年 C++游戏服务端 | - | 2026-11-11 | 无（门禁全绿） |
| react-taro-microfrontend | 生产 | React 18+Taro4 跨端H5/小程序 + qiankun 微前端挂载Vue3子应用 | `projects/_队列/react-taro-microfrontend/00_项目设计书.md` | 已搁置 | 求职侧设计台：连帆/九凌/高帆/伯遇/垦驱 | 2026-11-11 | - | 见看板搁置说明 |
| tauri-rust-ai-task-desktop | 生产 | Tauri 2 + Rust 桌面 AI 任务工作台（ownership/Tokio异步/thiserror错误处理/rusqlite建模/AI任务状态机与异常恢复） | `projects/_队列/tauri-rust-ai-task-desktop/00_项目设计书.md` | 待开工 | 求职侧设计台：镜跃网络桌面开发(Tauri/Rust) | - | - | 无 |
| pytorch-inference-service | 生产 | PyTorch微调BERT中文文本分类 + ONNX导出 + FastAPI推理服务 | `projects/_队列/pytorch-inference-service/00_项目设计书.md` | 待开工 | 求职侧设计台：宇佐智能/绍兴猫草 | - | - | 无 |
| web3-dapp-voting | 生产 | Solidity ERC20+投票合约 + Hardhat本地链 + React+MetaMask DApp | `projects/_队列/web3-dapp-voting/00_项目设计书.md` | 待开工 | 求职侧设计台：坤汇高新Web3 | - | - | 无 |
| sd-image-workflow | 生产 | Stable Diffusion WebUI+ComfyUI+ControlNet 批量电商图生成工作流 | `projects/_队列/sd-image-workflow/00_项目设计书.md` | 待开工 | 求职侧设计台：思元环保/丰度科技 | - | - | 无 |
| game-npc-dialog-agent | 生产 | 游戏智能 NPC 对话 Agent（LangGraph 多轮人设记忆 + Qdrant 游戏知识库 RAG + function calling 道具/技能/任务查询 + 对话质量回归评测） | `projects/_队列/game-npc-dialog-agent/00_项目设计书.md` | 待开工 | 求职侧设计台：网龙网络 AI研究员-游戏（技术类加分缺口，优先级排在 must_have 硬缺口之后） | - | - | 无 |
| dev-metrics-dashboard | 生产 | 研发效能度量看板（工作流自用：解析项目产物→SQLite 聚合→FastAPI+ECharts 看板；简历材料附带，按诚实边界写） | `projects/_队列/dev-metrics-dashboard/00_项目设计书.md` | 已完成 | 无来源 JD（改进建议 #115，2026-11-11 卡点1 拍板：自用工具立项） | 2026-11-11 | 2026-11-12 | 无（门禁全绿） |
| uniapp-miniapp-release-loop | 生产 | uni-app（Vue3+TS）一套代码出 H5 + 微信小程序，真机体验版→提审→发布→回滚闭环（Spring Boot + MySQL/Redis/RabbitMQ 后端，Node.js 云函数代理） | `projects/_队列/uniapp-miniapp-release-loop/00_项目设计书.md` | 进行中（第 9 步：最终验收（AI 预走完成，待用户两段式走查）） | 求职侧设计台：G9（伯遇/星光兔/灰豚/高帆/云联慧算/雄伟） | 2026-11-18 | - | **硬卡点（已解除）**：2026-11-19 用户回复「A」，选定 A 账本单列；B/C 只作发散截图留档，不进主循环 |
| rn-mobile-app-release | 生产 | React Native（Expo+TS）训练打卡双端 App + NestJS/PostgreSQL/Prisma/JWT+RBAC + Jest + EAS 打包升级 + Flutter 两屏对照 | `projects/_队列/rn-mobile-app-release/00_项目设计书.md` | 进行中（第 5.5 步 · 独立代码 Review（R1 报红，待 5A/5B 修复）） | 求职侧设计台：G8（逐爱/九凌/比特鹰/连帆） | 2026-11-23 | - | **人工卡点（APK，2026-11-24 更新）**：D-38~D-41 只差 EAS 构建与真机安装。 已替你做的： |
| ecom-scrape-rpa-dashboard | 生产 | 电商多平台采集（京东/天猫/拼多多/抖音）+ 反爬策略（限速/UA池/Cookie池/代理/退避/断点续采）+ YAML RPA 流程 DSL + pandas 清洗校验 + MySQL 窗口函数 SQL + openpyxl Excel 日报（公式/透视/图表）+ Vue3/ECharts 报表/BI 看板 | `projects/_队列/ecom-scrape-rpa-dashboard/00_项目设计书.md` | 进行中（第 5 步 · 分角色并行开发（5A 后端 ∥ 5B 前端，进行中）） | 求职侧设计台：G1（乐福思杰士邦 电商爬虫工程师 / 索骥数据 加分项） | - | - | 无（第 4 步为 🤖 机器闸门，三闸已全绿自动通过；下一步 5A/5B 为自动开发步骤，无人工卡点） |
| gis-map-service-platform | 生产 | GIS 地图服务与空间分析平台：PostGIS 入库 + 坐标系/投影转换 + 数据质检 + GeoServer 发布 WMS/WFS/WCS + 空间分析（缓冲/叠加/KNN/距离）+ OpenLayers 二维（图层/标绘/查询/量算）+ Cesium 三维轨迹 + GDAL 转换裁切 | `projects/_队列/gis-map-service-platform/00_项目设计书.md` | 待开工 | 求职侧设计台：G13（湖南爵纪网络科技 GIS工程师） | - | - | 无 |
| dw-etl-pipeline | 生产 | 数据仓库 ETL 与指标治理平台：MySQL ODS/DWD/DWS/ADS 四层 + 星型模型/SCD2 + 5 个存储过程（游标/异常/事务/幂等）+ PySpark 90 天重算与对账 + 指标字典/血缘/5 类质量规则 + 3 条慢查询优化 | `projects/_队列/dw-etl-pipeline/00_项目设计书.md` | 已完成 | 求职侧设计台：G14（杭州黉门科技 数据开发工程师） | - | 2026-11-24 | 无（门禁全绿） |
| netops-security-lab | 生产 | 网络与云产品配置运维 + 等保测评实操实验室：netns+OVS 三 VLAN/路由/ACL/DHCP/DNS（Cisco/H3C 命令对照）+ Ubuntu/Windows 装机 + Nmap/OpenVAS/lynis/OpenSCAP 扫描与基线 + 等保 2.0 五份材料 + MkDocs 四本手册资料站 + 四类故障演练 | `projects/_队列/netops-security-lab/00_项目设计书.md` | 待开工 | 求职侧设计台：G16（紫光云数 资料文档工程师 / 杭州砚云仓 计算机网络助理） | - | - | 无 |
| miniapp-iot-device-bridge | 生产 | 设备素材小程序：微信原生 6 页面 3 组件 + Mosquitto/paho-mqtt 模拟设备（配网/心跳/参数 ACK 幂等）+ canvas 裁切预览与动画 + 设备固件 OTA 分片续传回滚 + Java 四组接口（设备/指令/素材/OTA） | `projects/_队列/miniapp-iot-device-bridge/00_项目设计书.md` | 待开工 | 求职侧设计台：G15（杭州铮锐泓川 资深前端校招 / 杭州佳其网络 java全栈） | - | - | 无 |
| pg-agent-data-service | 生产 | PostgreSQL Agent 数据服务：JSONB + `jsonb_path_ops` GIN + 月度分区 + tsvector/trgm 双检索对照 + 窗口函数/CTE 7 指标与 pandas 对账 + 3 条慢查询 EXPLAIN 优化 + 15 条 MySQL 方言对照 + FastAPI 5 接口 / Spring Boot JPA 最小接入 | `projects/_队列/pg-agent-data-service/00_项目设计书.md` | 待开工 | 求职侧设计台：G17（杭州睿索思人工智能 Agent开发工程师（前后端）） | - | - | 无 |
| dubbo-rpc-governance | 生产 | Dubbo 3 RPC 服务治理：Nacos 注册中心 + 订单/库存双服务 + 四种负载均衡策略分布验证 + 超时重试与 requestId 幂等 + 熔断降级与半开探测 + OpenFeign 同接口对照 + JMeter 三场景压测 | `projects/_队列/dubbo-rpc-governance/00_项目设计书.md` | 待开工 | 求职侧设计台：G19（宁波甑远商贸 java，Dubbo 加分缺口） | - | - | 无 |
| db-access-middleware-sharding | 生产 | 数据库访问中间件内核：ShardingSphere-JDBC 4 分片路由 + 读写分离/影子库 + DMS 风格 SQL 入口（白名单/RBAC/审计/限流）+ Oracle→MySQL 方言适配层 + Kafka/TDP 数据管道（幂等/背压/死信/重放）+ 慢 SQL 与连接池观测 | `projects/_队列/db-access-middleware-sharding/00_项目设计书.md` | 待开工 | 求职侧设计台：G20（杭州图尔兹信息技术 Java工程师（26届毕业生）） | - | - | 无 |
| rtdw-ops-support-lab | 生产 | 实时数仓 + 平台排障 + 技术支持交付：Kafka 3 分区 + Flink ODS/DWD/DWS 三层实时指标（watermark/去重/迟到旁路/幂等 upsert）+ Hive/Spark 单机 T+1 对账 + 六类系统层故障演练与排障卡 + 工单 SOP/3 案例卡/客户手册/培训讲义/POC 清单 | `projects/_队列/rtdw-ops-support-lab/00_项目设计书.md` | 待开工 | 求职侧设计台：G23（袋鼠云 技术支持工程师 MJ001273） | - | - | 无（2026-11-24 设计完成，must 7/7、总覆盖 23/23、闸门 exit 0；面试前最低交付见设计书 §2） |
| hw-bench-llm-infer | 生产 | 单机设备性能压测 + LLM 推理性能评测平台：psutil/nvidia-smi 1Hz 采样 + CPU/内存/磁盘/网卡/GPU 五场景 + Qwen2.5-0.5B 双后端 TTFT/TPOT/并发扫描 + Markdown/图表报告 + 基线回归门禁 + pytest | `projects/_队列/hw-bench-llm-infer/00_项目设计书.md` | 待开工 | 求职侧设计台：G22（小红书 服务器与LLM测试实习生） | - | - | 2026-11-23 设计书 + 冒烟骨架已在 `_队列/hw-bench-llm-infer` 内跑过（results/smoke 有产物）；正式开工需按队列规则复制到 `projects/` 初始化 `_项目状态.md`，等用户「启动队列下一个」 |

---

## 已豁免项目（跳过门禁）

> 这些项目由于历史遗留或不可抗力，**跳过完成门禁**，状态标「已豁免」。豁免不是"项目没完成"，而是"完成时门禁还没上线，不重跑"。
> 要撤销豁免（比如某个项目后来补齐了门禁产物），移走下表行即可；要新增豁免，必须在此写下具体原因。

| 项目名 | 豁免原因 | 豁免日期 |
|---|---|---|
| 生产异常答疑AI助手 | 2026-10-19 完成，早于 2026-10-27 门禁脚本上线日。补造 6.5/8.5/台账等产物属于补造证据，不做。 | 2026-10-29 |

---

## 队列规则

1. **入队**：step00 设计书机器闸门全绿后，每个选中项目的 `00_项目设计书.md` + `00_JD对账表.md` 复制到 `projects/_队列/<项目名>/`，状态标"待开工"。此时**不复制模板骨架**，不建 02_架构设计/05_代码 等空目录。
2. **启动**：用户说「启动队列下一个」/「继续下一个项目」时，取状态=待开工 且排最前的项目，从 `projects/_队列/<名>/` 复制设计书到 `projects/<名>/00_原始项目描述.md`，复制模板骨架，初始化 `_项目状态.md`，状态改为"进行中"。
3. **完成**：step10 结束后，先跑 `workflow_completion_check.py` 全绿，状态才能改为"已完成"，填完成日期。设计书留在 `_队列/<名>/` 作为档案，不删。豁免项目（见豁免清单）跳过门禁，直接改"已豁免"。
4. **搁置/抢占**：并行项目要插队时，手上的项目**必须记录三件事**——当前步骤编号、已完成到哪、下次开工清单，才能改"已搁置"。没有三件事的搁置视为无效，禁止抢占。
5. **排序**：队列按"先入先出"，但用户可以指定优先做哪个（改顺序即可，不用严格 FIFO）。并行项目按端口前缀隔离，见 `WORKFLOW_端口分配表.md`。
6. **事实列禁止手改**：`状态` / `完成日期` / `当前卡点` 由 `wf queue --sync` 从各项目看板 + 门禁脚本推导；要改状态就改看板（或跑门禁补齐产物），再 `wf queue --sync`。手改会被 `wf queue --check` 报红。

## 目录约定

```
projects/
├── _队列/                          # 待启动项目的设计书存放处
│   ├── _说明.md
│   ├── <项目A>/
│   │   ├── 00_项目设计书.md
│   │   └── 00_JD对账表.md
│   └── <项目B>/
│       └── ...
├── _TEMPLATE_新项目/               # 模板骨架（启动时复制）
├── multi-tenant-crm-ticket/        # 已完成项目（完整骨架）
└── <已完成项目>/                    # 已完成项目（完整骨架，保留）
```
