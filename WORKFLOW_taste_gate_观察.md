# taste gate 观察记录（跨项目）

> step6 跑 `scripts/design_taste_gate.py` 后自动追加一行。
> **本表是 R23 的 taste 子项观察数据，不单独构成规则**；样本 <3 时保持软观察、不下结论，达到阈值后由 step11 回写 R23 或调整 allow 列表。
>
> 判定规则（step11 自动读）：
> - 连续 ≥3 个项目，标注为「真问题」的 FAIL 占比 ≥50% → 建议改成硬卡（脚本最后一行改 `sys.exit(1 if rc==1 else 0)`）
> - 连续 ≥3 个项目，标注为「误报」的 FAIL 占比 ≥70% → 建议把对应规则加进 --allow 白名单，或降低该规则级别
> - 样本 <3 个 → 保持软观察，不下结论

| 日期 | 项目 | 项目类型 | URL | inspect 退出码 | FAIL 数 | 人工标注（真问题/误报/未看） | 备注 |
|---|---|---|---|---|---|---|---|
| 2026-11-08 | nestjs-agent-workbench | b2b-admin | http://localhost:5183 | 1 | 4 | 未看 | |
| 2026-11-11 | dev-metrics-dashboard | internal-tool | http://127.0.0.1:8091/ | 1 | 3 | 真问题 2 / 误报 1 | 真问题：字号 48%<13px（P3）、口径角标距边 9px（P3），均 deferred；误报：热力图单色相=状态编码非数据系列，建议 allow 白名单。另 5 路由 inspect 复测，根因页 overflow 134px 已在本轮修复 |
| 2026-11-12 | react-taro-microfrontend | portfolio | http://127.0.0.1:5185/index.html | 1 | 11 | 真问题 1 / 误报 7 / 待 T24 3 | 真问题：no-title 缺 h1 语义（P3，Q-008 deferred）。误报/不适用：font-fallback（系统字体非 webfont）、first-action（Taro Button 未被识别为 button）、few-pictures/no-footage/no-hero（后台门面非 landing）、off-centre（flex 居中被边距算法误判）、dev-server（环境提示）。待 T24 冻结期：shadow、hero-void、still-page。仅扫登录页首屏，其余页留阶段二人工走查 |
