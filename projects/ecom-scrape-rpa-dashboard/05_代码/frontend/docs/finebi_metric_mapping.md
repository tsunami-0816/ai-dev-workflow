# FineBI 指标口径映射（finebi_metric_mapping.md）

> 对应任务 T26 / 设计项 D-92（P1-10，JD 加分项「BI 可视化」落点）。
> **明示：本项目未使用 FineBI。** 看板由 Vue 3 + ECharts 5 实现（架构 §1.1 选型）；
> 本文档把 4 个视图的指标口径映射为 FineBI 的维度/度量/过滤/刷新四栏概念，
> 供后续如迁移 FineBI 时对齐口径，不伪称已用 FineBI。

## 0. 口径总则

- 所有业务指标（成功率/封禁率/P95/涨跌幅/均价）**一律由后端 SQL 计算**（`sql/queries/*.sql`，
  与 Excel 报表同源，ADR-08）；前端与 BI 工具都只做展示与格式化，不二次计算口径。
- 涨=红 `#d93025`、跌=绿 `#1a7f37`（A 股口径，C07）。
- 无数据 ≠ 错误：`code=0, data=[]` 走空态文案；数据服务不可用走 50301 顶部条。

## 1. 四视图口径映射表

| 视图（页签） | 维度 | 度量 | 过滤 | 刷新 |
|---|---|---|---|---|
| 价格走势 `/api/trend` | 日期（date，日粒度） | 价格（price，¥2 位小数）；销量（sales_num，tooltip 展示）；异常点（anomaly_flag=1 标记，不拦截） | sku_id（必选）；platform（必选：jd/tmall/pdd/douyin）；days ∈ {7,30} | 手动刷新按钮；接口侧 60s TTL 缓存 |
| 平台对比 `/api/platform-compare` | 平台（platform） | sku_count；avg_price；min_price；max_price；sum_sales | date（必选，默认当日）；category（可选） | 手动刷新按钮；60s TTL |
| TOP 变动 `/api/top-changes` | 商品（sku_id + title）；平台（platform） | prev_price；curr_price；change_pct（涨红/跌绿） | days=1（对比跨度，后端取数窗口自动 +1 天，§4.5 Q2）；direction ∈ {up,down}；limit（默认 10，≤50） | 手动刷新按钮；60s TTL |
| 采集健康度 `/api/health` | 日期（date，7 日）；平台（platform，可选，不传=全平台汇总） | success_rate；blocked_rate；p95_latency_ms；req_cnt；series 三指标按日序列 | days=7；platform 可选 | 手动刷新按钮；60s TTL |

## 2. ECharts ↔ FineBI 对照

| 概念 | ECharts（本项目实现） | FineBI（迁移时的对应物） |
|---|---|---|
| 折线走势图 | `LineChart`（echarts/charts 按需注册） | 组合图-折线图，维度拖入日期，指标拖入价格 |
| 异常点标记 | `ScatterChart` 叠加 anomaly_flag=1 的点（红色 symbol） | 指标条件格式 / 标记点（图表-标记） |
| 柱状对比图 | `BarChart`（双 Y 轴：均价 + SKU 数） | 柱形图，双值轴 |
| 指标卡（三指标） | `StatTile.vue` 组件（后端返回值直接展示） | 指标卡（KPI 组件） |
| 明细表格 | `DataTable.vue`（文本插值，不用 v-html） | 明细表 / 分组表 |
| 筛选器 | 视图内 select/segment 控件 + 1s 防抖 | FineBI 过滤组件（参数注入数据集） |
| 60s 缓存 | 服务端进程内 TTL（L8） | FineBI 数据集缓存/实时直连 |
| 涨跌配色 | `#d93025` / `#1a7f37`（A 股口径） | 同色配置到图表系列颜色 |

## 3. 数据源说明

- 本项目看板数据源：FastAPI 只读接口（ro 账号）读 `agg_daily_platform` / `price_snapshot` /
  `antibot_metrics`（预聚合，C10 P95 保障）。
- 若迁 FineBI：同一 MySQL 库 `ecom_scrape` 建数据集，指标口径按上表映射，SQL 与
  `sql/queries/*.sql` 保持同源，避免「报表一个数、看板另一个数」。

## 4. 当前状态标注

- 契约 `06.5_契约/openapi.json` 尚未产出（5A 并行开发中），前端当前用架构 §5.4 样例 JSON
  做本地 stub 兜底（页面顶部黄条标注 mock 环境）。**契约待 5A 产出后复核。**
