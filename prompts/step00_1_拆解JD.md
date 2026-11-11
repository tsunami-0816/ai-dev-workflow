# step 0.1 · JD 结构化拆解

- **角色**：资深技术招聘分析师
- **输入**：一份或多份 JD 原文（图片 / PDF / 文本均可）；超长截图先跑 `python scripts/split_long_image.py <图片>` 切段，再逐段 Read/OCR
- **输出物**：`00_JD技能点清单.md`（机器对账需要时另存 `00_JD技能点清单.json`）→ 落盘本轮 step00 设计工作目录
- **模块位置**：设计模块第 1 步（WORKFLOW_步骤定义.md 0.1；设计说明见 `docs/step00_JD选题模块设计.md` §1.1）
- **卡点**：自动步骤，无人工卡点。产物质量由 0.3 缺口分析、0.4 选题矩阵和 `scripts/skills_coverage_checker.py` 反查

---

## 提示词（直接套用，代码块内为可粘贴全文）

```
你是资深技术招聘分析师。把下面每份 JD 拆解成结构化技能点，禁止笼统概括、禁止脑补 JD 没写的内容。

【角色与目标】
目标是把 JD 变成后续 step00.3 选题、step00.4 覆盖度对账可以直接消费的「技能点清单」，不是写 JD 摘要。

【输入】
{{jd_text_or_image_ocr}}
- 多份 JD 用 `--- JD 2 ---` 这类分隔线隔开；
- 截图/PDF 看不清或被截断的部分，标注「[识别风险] 待用户补充」，不得编造；
- 若拿到的是 JD 长图，先确认已用 scripts/split_long_image.py 按 1600px 切段，逐段识别后再合并。

【对每份 JD 的输出格式】
严格输出以下 JSON（不要多余解释），一份 JD 一个对象：
{
  "position_title": "",
  "company": "",
  "salary": "",
  "hard_stack": ["具体技术名", "..."],
  "architecture_skills": ["高并发/缓存一致性/...", "..."],
  "business_domain": "",
  "engineering_practices": ["Git Flow/Code Review/...", "..."],
  "must_have_vs_nice_to_have": {
    "must_have": [],
    "nice_to_have": []
  },
  "red_flags": ["JD 里个人项目不可能实现的词"],
  "degree_requirement": "应届/在校/几年经验"
}

【硬性要求】
1. hard_stack 必须具体到组件名：写 Kafka / Spring Cloud Gateway / Redis / MyBatis，禁止「熟悉微服务」「了解大数据」这类笼统词。
2. architecture_skills 必须是可考核的机制：高并发、高可用、分布式事务、缓存一致性、消息幂等/顺序、限流熔断——不要写「架构能力强」这种形容词。
3. business_domain 写具体场景：SaaS 工单、企业内部审批、AI Agent 评测、电商售后；不要写「互联网行业」。
4. must_have 与 nice_to_have 必须分开：JD 原文「必须/要求/熟练掌握/精通」→ must_have；「加分/了解/优先/熟悉者优先」→ nice_to_have。判据写成一句话贴在 JSON 后面，便于复核。
5. red_flags 必须逐条列出 JD 里个人项目不可能实现的词（全球化部署、存算分离、K8s 集群、大模型微调、千万级 DAU……），对照 `docs/个人项目不可实现清单.md`，这些词后面设计项目时要主动砍掉。
6. 原文没写的要求不要猜；模糊处写「JD 未明确」。
7. 多份 JD 的同一技能点要合并计数，不得重复列。

【落盘（必须执行）】
把结果写成 `00_JD技能点清单.md`（放在本轮 step00 设计工作目录，文件名必须逐字一致），结构固定：
# 00_JD技能点清单
## JD-1 <岗位名> @ <公司>
- 岗位/公司/薪资/学历要求：…
- JSON 代码块（把上面那个 JSON 对象原样贴回）
- 三行摘要：核心硬技术栈 / 可讲深度的架构点 / 需主动砍掉的词
## JD-N …
## 合并去重总表
| 技能点 | 类型（hard_stack/architecture_skills/business_domain/engineering_practices） | 出现 JD 数 | must 或 nice | 个人项目是否可做 | 后续由哪个候选项目覆盖（0.4 回填） |
（表格行按出现 JD 数降序，must_have 优先）

机器对账需要时，把每份 JD 的 JSON 合并另存为 `00_JD技能点清单.json`（`scripts/skills_coverage_checker.py --skills-json` 读它）；没有 JSON 时脚本要人工抽，不允许只交 md。

【自检后再说完成】
- 每份 JD 四类标签（硬技术栈 / 架构能力 / 业务领域 / 工程规范）齐全；
- must / nice 已分开且写了判据；
- red_flags 已对照 docs/个人项目不可实现清单.md；
- 合并总表含「出现 JD 数」，后面能直接做缺口分析；
- 全文搜不到「熟悉微服务」「了解大数据」这类笼统词。
```

---

## 交付自检

- [ ] 每份 JD 都有独立小节，含岗位名/公司/薪资/学历要求
- [ ] 每份 JD 的 hard_stack / architecture_skills / business_domain / engineering_practices 四类齐全
- [ ] must_have 与 nice_to_have 已分开，且写了取自 JD 原文措辞的判据
- [ ] red_flags 已对照 `docs/个人项目不可实现清单.md`，逐条标出「个人项目做不了」
- [ ] 末尾有「合并去重总表」：技能点 / 类型 / 出现 JD 数 / must 或 nice / 是否可做 / 待 0.4 回填覆盖项目
- [ ] 笼统词已清零（搜「熟悉微服务」「了解大数据」「架构能力强」）
- [ ] 模糊/截断内容标了「[识别风险] 待用户补充」，没有编造
- [ ] 文件已落盘 `00_JD技能点清单.md`（必要时另有 `00_JD技能点清单.json`），0.2/0.3/0.4 可直接引用
