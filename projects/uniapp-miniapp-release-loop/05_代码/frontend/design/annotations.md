# 375 基准实测标注（T-705 / D-31）

> 基准：视口 **375 × 844**（DPR 1），H5 dev `http://127.0.0.1:5186`，内容来自真实后端 8092。
> 标注值出处：`src/styles/tokens.css`（设计 token）与本页样式；实测值取自 `scripts/rework_layout_check.cjs` 的 DOM 计算值（`getBoundingClientRect` / `getComputedStyle`）。
> 证据：`05.5_代码Review/evidence/rework_layout.json`、`annotations-375.png`、`overlay-375.png`。
> 复跑：`node scripts/rework_layout_check.cjs`（会同时产出 375/390/414 三档数值与截图）。

## 一、首页（A 版账本）

| # | 元素 | 目标文件:行 | 标注值 | 实测值 @375 | 偏差 | 判定 |
|---|---|---|---|---|---|---|
| 01 | 页面左右安全边距 | `src/styles/tokens.css:34`（`--gutter: 24px`） | 24px | 24px | 0 | 符合 |
| 02 | 首屏大标题字号 | `src/styles/tokens.css:17`（`--fs-display: 34px`） | 34px | 34px | 0 | 符合 |
| 03 | 首屏价格字号 | `src/styles/tokens.css:20`（`--fs-num: 18px`） | 18px | 18px | 0 | 符合 |
| 04 | 清单行高 | `src/styles/tokens.css:35`（`--row-h: 72px`）+ `variants/LedgerVariant.vue:146` | 72px | 72px | 0 | 符合 |
| 05 | 清单行标题字号 | `variants/LedgerVariant.vue:163`（`font-size: 18px`） | 18px | 18px | 0 | 符合 |
| 06 | 首屏图位宽 | `variants/LedgerVariant.vue:111`（`width: 46%`，内容宽 327） | 150px | 150px（x=225→右 375） | 0 | 符合（右侧出血到屏幕边） |
| 07 | tabBar 文案字号 | `src/App.vue:57`（H5 覆盖 12px） | 12px（≥11 可读下限） | 12px | 0 | 符合（uni 默认 10px 已覆盖） |
| 08 | 横向溢出 | 验收要求：≤0px | 0px | `scrollWidth 375 = clientWidth 375` | 0 | 符合 |

## 二、详情页

| # | 元素 | 目标文件:行 | 标注值 | 实测值 @375 | 偏差 | 判定 |
|---|---|---|---|---|---|---|
| 09 | 图片位左右出血 | `pages/package/detail.vue:154`（`margin: var(--sp-3) calc(var(--gutter) * -1)`） | 左 0 / 右 375 | 左 0 / 右 375（w=375） | 0 | 符合（Q-006 已修） |
| 10 | 图片位比例 | `pages/package/detail.vue:152-153`（宽 = 视口宽，高 `125vw`） | 4:5 = 1.25 | 470/375 = **1.250** | 0 | 符合（vw 兜底，兼容 WXSS） |
| 11 | 说明区与固定预约栏 | `pages/package/detail.vue:190`（bar 高 81） | 首屏重叠 0px | 说明区 y 238–367；bar 顶 763；重叠 **0** | 0 | 符合（Q-009 已修：说明上移到图片之前） |
| 12 | 预约栏高度 | `pages/package/detail.vue:190-201`（按钮 48 + 上下 16） | 80px | **81px** | **+1px** | 有意偏差（`border-top` 1px 计入高度） |
| 13 | 规格文字「样片 4:5」 | `pages/package/detail.vue:29`（已删除） | 不出现 | `specTextPresent=false` | 0 | 符合（Q-015 已修） |
| 14 | 标题/正文字号比 | `tokens.css:17,18`（34 / 15） | ≥3.0（critique 判据） | 34/15 = **2.267** | **−0.733** | 已知审美偏差（Q-003 记录，v1.1 调正文 11–12px 或标题 44px） |

## 三、表单页

| # | 元素 | 目标文件:行 | 标注值 | 实测值 @375 | 偏差 | 判定 |
|---|---|---|---|---|---|---|
| 15 | 主按钮高度 | `pages/booking/form.vue:344`（`height: 48px`） | 48px | 48px | 0 | 符合 |
| 16 | 输入控件高度 | `tokens.css:36`（`--tap-min: 44px`） | ≥44px | 44px | 0 | 符合 |
| 17 | 字段上下留白 | `tokens.css:26`（`--sp-3: 24px`） | 24px | 24px | 0 | 符合 |

## 四、三档复测（375 / 390 / 414）

| 档位 | 首页 scrollWidth / clientWidth | 详情 scrollWidth / clientWidth | 详情图位比例 | 首屏重叠 |
|---|---|---|---|---|
| 375 | 375 / 375 ✅ | 375 / 375 ✅ | 1.250 | 0 ✅ |
| 390 | 390 / 390 ✅ | 390 / 390 ✅ | 1.250 | 0 ✅ |
| 414 | 414 / 414 ✅ | 414 / 414 ✅ | 1.250 | 0 ✅ |

## 五、偏差汇总

- 共 **17 条**标注，非零偏差 **2 条**：`#12` 预约栏 +1px（`border-top` 计入高度）、`#14` 字阶比 −0.733（设计审美边界，见 `_问题台账.md` Q-003）。
- 三档横向溢出、首屏遮挡均为 0，与 5.5 首轮报告的三处阻断项对应收口。
