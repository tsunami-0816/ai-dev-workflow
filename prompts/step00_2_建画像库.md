# step 0.2 · 作品集画像扫描

- **角色**：技术架构师
- **输入**：`D:\lg\project\` 下已有项目目录（README、`pom.xml`/`build.gradle`/`requirements.txt`/`pyproject.toml`/`package.json`、`docker-compose.yml`、`application*.yml`/`.properties`、目录树）
- **输出物**：`00_作品集画像库.json` + `00_作品集画像库.md`（人类可读版）→ 落盘本轮 step00 设计工作目录
- **模块位置**：设计模块第 2 步（WORKFLOW_步骤定义.md 0.2；设计说明见 `docs/step00_JD选题模块设计.md` §1.2）
- **卡点**：自动步骤，无人工卡点。优先跑 `python scripts/portfolio_scanner.py --root "D:\lg\project" --out <设计工作目录>/00_作品集画像库.json`，脚本扫不到的字段再由 AI 兜底补

---

## 提示词（直接套用，代码块内为可粘贴全文）

```
你是技术架构师。下面是用户作品集里每个已有项目的 README、依赖文件、docker-compose 与目录结构。
你的任务：把每个项目覆盖了哪些技能点抽成一份「作品集能力画像库」，供 step00.3/0.4 做 JD 缺口分析与撞车检测。

【输入】
{{project_readme}}            ← 每个项目的 README 前 30-50 行
{{project_dependencies}}      ← pom.xml / build.gradle / requirements.txt / pyproject.toml / package.json
{{project_docker_compose}}    ← docker-compose.yml、application*.yml / .properties
{{project_tree}}              ← 目录树（前 2-3 层即可）
说明：脚本 scripts/portfolio_scanner.py 已先跑过时，把它的输出 JSON 一并给我，你的工作是核对 + 补漏，不是从零重写。

【扫描范围】
- 根目录：D:\lg\project\
- 只扫一级子目录里的项目；跳过 `.` 开头目录、`archive`、`工作流测试`、`node_modules`、`.venv`、`target`、`dist` 等依赖/构建目录
- 每个项目一条记录，不得合并、不得漏

【每个项目的输出 JSON】
{
  "project_name": "",
  "path": "D:\\lg\\project\\<项目名>",
  "business_domain": "一句话业务领域（读 README 首段；读不到写「未识别」）",
  "tech_stack": ["后端/前端/脚本语言与框架"],
  "middleware_used": ["MySQL/Redis/Kafka/Nacos/Qdrant/...（有配置文件证据才算）"],
  "covered_skills": ["可被 JD 对账直接匹配的技能点，命名与 00_JD技能点清单.md 一致"],
  "depth": "浅尝 / 中级 / 深入",
  "evidence": ["关键证据文件路径（pom.xml、docker-compose.yml、README 等）"],
  "human_notes": "人工补充打标（没有就留空；合并时禁止删除已有内容）"
}

【硬性要求】
1. 只按文件证据打标：依赖文件里出现才算 tech_stack/middleware_used；目录名、项目名不能单独当证据，猜的写「未识别」或「推断：…」。
2. covered_skills 的命名必须和 00_JD技能点清单.md 用同一套词（如 Kafka、Redis、Spring Cloud Gateway、pytest），否则 0.3 做不了交集/差集。
3. depth 三档判据写清楚：浅尝=只在依赖里出现、无实际调用链；中级=有完整功能模块但无深度设计；深入=有核心机制实现（如一致性/性能/幂等）可面试展开。
4. business_domain 必须是具体场景（SaaS 工单、企业管理后台、AI 评测），不要写「互联网项目」。
5. 已有画像库时做「合并更新」：以本项目扫描结果更新技能点，保留人工补充的 human_notes 打标，不删除历史项目记录。
6. 承认不确定：README 与代码矛盾时以依赖文件为准，并在 evidence 里写清冲突点。

【落盘（必须执行）】
1. `00_作品集画像库.json`（文件名必须逐字一致）：{"generated_at": "YYYY-MM-DD", "root": "D:\\lg\\project", "projects": [ ...每个项目一条... ]}
2. `00_作品集画像库.md`（人类可读版）：每个项目一节 —— 项目名 / 业务领域 / 技术栈 / 中间件 / 覆盖技能点 / 深度 / 证据文件；末尾附「技能点 × 项目覆盖矩阵」总表。
3. 自检计数打印并写进 md 末尾：扫描了多少个项目目录、识别出多少个不同技能点、跳过了哪些目录及原因。

【自检后再说完成】
- 项目数 = D:\lg\project\ 下实际项目数（不含跳过的）；
- 每个 covered_skills 都能在 evidence 里找到依据；
- 命名与 JD 技能点清单统一，0.3 可直接做差集；
- JSON 与 md 内容一致（md 是 JSON 的人读投影）。
```

---

## 交付自检

- [ ] `00_作品集画像库.json` 与 `00_作品集画像库.md` 都已落盘，文件名逐字一致
- [ ] 每个已有项目都有一条记录，无合并、无漏项；跳过目录已写明理由
- [ ] tech_stack / middleware_used 均有依赖或配置文件证据，不靠项目名猜
- [ ] covered_skills 与 `00_JD技能点清单.md` 同一套命名，0.3 可直接做交集/差集
- [ ] depth 按「浅尝/中级/深入」三档判据打分，不是随手写
- [ ] 合并更新场景下，人工补充的 `human_notes` 未被删除
- [ ] 末尾有「技能点 × 项目覆盖矩阵」+ 自检计数（扫描项目数 / 识别技能点数 / 跳过目录数）
- [ ] md 与 json 内容一致（md 是 json 的人读投影）
