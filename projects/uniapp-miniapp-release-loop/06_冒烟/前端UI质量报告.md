# 第 6 步 · 前端 UI 质量与 taste 检测报告

- 扫描时间：2026-11-20（第 6 步阶段一，未宣告第 6 步放行；§六 关键项确认仍在等用户）
- 目标：H5 dev `http://127.0.0.1:5186/`（uni-app Vue3 H5 产物，Vite dev）
- 浏览器：Edge（puppeteer-core，headless=new）
- 证据：`06_冒烟/evidence/step6_ui_probe.json` + `step6_home_{375,390,414,1440}.png`

## 一、`design_quality_check.py`（impeccable detect）

| 项 | 结果 |
|---|---|
| 命令 | `python scripts/design_quality_check.py --url http://127.0.0.1:5186 --json …前端UI质量报告.json` |
| 退出码 | 0 |
| 输出 | `✅ 未发现问题（或扫描失败）`；**JSON 未生成** |
| 结论 | **无阻塞问题，但证据强度弱**：impeccable 返回空、脚本仍报「未发现问题」，无法区分「干净」与「扫描失败」 → 记 Q-023（P3，工作流脚本口径，归 step11） |

> 口径说明：按 step06 提示词 4.4，本项 error 级才阻塞；本轮 0 条，故不阻塞冒烟。JSON 缺失已如实登记，不写成「已全绿」。

## 二、自测四档布局（`probe_step6_ui.cjs` 实测）

| 宽度 | scrollWidth = clientWidth | 横向溢出 | h1 | 首屏可见按钮 | 运行中的动画 | `--gutter` |
|---|---|---|---|---|---|---|
| 375 | 375 = 375 | 0 | 0 | 0 | `lb-expose` | 24px |
| 390 | 390 = 390 | 0 | 0 | 0 | `lb-expose` | 24px |
| 414 | 414 = 414 | 0 | 0 | 0 | `lb-expose` | 24px |
| 1440 | 1440 = 1440 | 0 | 0 | 0 | `lb-expose` | 24px |

> 首轮（补动效前）四档 `runningAnimations` 均为空；补 Q-021 后复跑，四档均为 `lb-expose-…`。

判读：
1. **C10（375/414 无横向溢出）仍成立**，与 5.5 R2 结论一致。
2. `h1 = 0`、`首屏可见按钮 = 0`、`动画 = 空` 三项为真实缺口，见下表落台账。
3. 1440 下页面内容铺满全宽（`contentLeft=0 / contentRight=1440`），无 `max-width` 居中 → H5 桌面端行宽失控（首屏 61% 为空图位），非 C10 范围但影响 H5 可读性。

## 三、`design_taste_gate.py`（taste 子项，17 条 FAIL 逐条标注）

- 退出码 0（脚本按软观察期恒 0，不阻塞）；已写入 `WORKFLOW_taste_gate_观察.md` 2026-11-20 行。
- 扫描视口为桌面宽度（1440），本项目设计基准是 375（C10/C11 口径），部分 FAIL 属视口错配的误报。

| # | FAIL 项 | 标注 | 依据 |
|---|---|---|---|
| 1 | eyebrow/kicker `No.01` 在标题上方 | 误报 | 方向稿 §2.1 账本编号是刻意元素 |
| 2 | Monospace 用在非代码处（IBM Plex Mono） | 误报 | 方向稿 §2.2 等宽数字为设计选择 |
| 3 | 装饰性编号 `No.01 / 01 / 04 / 02 / 03 / 04` | 误报 | 同 1 |
| 4 | 6 条细分割线 | 误报 | 账本横线，方向稿 §2.3 |
| 5 | 1 处 1px 描边盒 | 误报 | 账本边框语言 |
| 6 | 黄米色背景（#f2ede4） | 误报 | 方向稿 §2.1 纸色 token |
| 7 | 使用 3 种字体 | 误报 | 方向稿 §2.2 三族分工（黑/宋/等宽） |
| 8 | 首屏无可见按钮 | 误报（建议 step11 白名单） | 小程序列表卡片即主入口，无独立 CTA 按钮 |
| 9 | 全页 0 张图片 | 误报（已知边界） | 无真实样片，4:5 有意空态，已记 Q-003 |
| 10 | 全页无视频 | 误报 | 需求不含视频 |
| 11 | 首屏无主导元素 | 误报 | 1440 视口把 375 版式拉平所致 |
| 12 | dev server 提供服务 | 误报 | 环境提示，非产物问题 |
| 13 | 边距左 6px / 右 24px（1440） | **真问题（并入 Q-022，P3）** | 1440 下无 `max-width`，内容铺满全宽，行式边距不对称 |
| 14 | 页面无可见 h1 | **真问题（Q-022，P3）** | `uni-app` 全站 `<text>`/`<view>`，无 h1；SEO/读屏缺失 |
| 15 | 首屏 61% 是同一空块 | 误报（并入 13 的成因） | 1440 + 4:5 空图位放大 |
| 16 | 加载与滚动期间 0 个元素运动 | **真问题 → 已修（Q-021 verified）** | 方向稿 §2.5 两处动效原未实现；本轮已在 `LedgerVariant.vue` 补 `lb-expose` + 价格 300ms 跳动，复测四档 `runningAnimations=["lb-expose-…"]`，`step6_rowtap.json` pass=true |
| 17 | 2/2 桌面屏几乎全空 | 误报 | 同 11/15 |

**标注汇总：真问题 3 条（其中 2 条落台账 Q-021/Q-022，1 条并入 Q-022）/ 误报 14 条。**

## 四、落台账

| ID | 级别 | 现象 | 归属 |
|---|---|---|---|
| Q-021 | P2 | 方向稿 §2.5 两处动效未实现（含 `prefers-reduced-motion` 降级） | **已修并回归（verified）**：`LedgerVariant.vue` + `step6_rowtap.json` |
| Q-022 | P3 | H5 无 h1 语义；1440 宽屏无 `max-width`（行宽失控、边距不对称） | 第 9 步前修（C10 不含宽屏） |
| Q-023 | P3 | `design_quality_check` 空转仍报「未发现问题」，JSON 不生成 | step11 脚本口径 |

## 五、复跑命令

```powershell
cd D:\lg\project\工作流测试\projects\uniapp-miniapp-release-loop
node "06_冒烟\scripts\probe_step6_ui.cjs"
python D:\lg\project\工作流测试\scripts\design_quality_check.py --url http://127.0.0.1:5186 --json "06_冒烟\前端UI质量报告.json"
python D:\lg\project\工作流测试\scripts\design_taste_gate.py --url http://127.0.0.1:5186 --project uniapp-miniapp-release-loop --project-type landing
```
