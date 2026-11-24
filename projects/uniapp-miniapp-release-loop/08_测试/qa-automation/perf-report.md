# 性能测试报告（指针）

> 本文件为指针，正文唯一来源：`../性能测试报告.md`（第 8 步交付根目录，含 C03–C06 实测、Python/JMeter 三档对比、瓶颈分析与调优建议）。
> 原始数据：`reports/perf_result.json`、`reports/jmeter_summary.json`、`jmeter/result_10.jtl`、`jmeter/result_50.jtl`。

## 关键结论（摘要，详细口径见正文）

- C03：预约接口 30 样本 P95 = 34.1ms（阈值 <800ms，通过）。
- C04：套餐缓存命中 19/21 = 90.5%（阈值 >80%，通过）。
- C05：同键重复提交 3 次 → 1 行（通过）。
- C06：10 条预约 → notify_log 10/10（通过）。
- JMeter 定压 30s：10 线程 6,859.7 TPS / P95 2ms；50 线程 10,124.4 TPS / P95 9ms；均 0 错误。
- Python 客户端 50 并发 TPS 仅比 20 并发 +3.1%（客户端先饱和），服务端容量以 JMeter 为准。

复跑命令见 `README.md` 的「性能测试」一节。
