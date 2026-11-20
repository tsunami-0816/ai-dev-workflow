# 5B 阶段 secrets/SAST 扫描结论（2026-11-19）

命令：`python scripts/security_scan_secrets.py --sast projects/uniapp-miniapp-release-loop`
原始输出：`evidence/secrets_scan_5b.txt`（exit 1，4 处命中 + SAST 6 条规则全通过）

| # | 文件 | 命中 | 判定 |
|---|---|---|---|
| 1 | `scripts/smoke.ps1:43` | `"account":"demo","password":"welcome1"` | **演示账号**（`db/init.sql` seed，README 公开），非密钥 |
| 2 | `scripts/smoke_cf.py:202` | 同上 | **演示账号**，冒烟脚本入参 |
| 3 | `05_代码/backend/后端开发实现文档.md:106` | 同上 | **文档示例**，非可执行代码 |
| 4 | `05_代码/frontend/src/pages/login/index.vue:31` | `:password="true"` | **误报**：Vue 布尔属性，控制密码框掩码，不是口令 |

结论：4 处均**不是真实密钥**，无私钥/AppSecret/数据库口令落入前端或仓库；
`APP_SECRET` 仍只在后端 `application.yml`（dev 默认值）+ 云函数 `.env`（未生成），未进前端。
SAST 代码级扫描：✅ 未发现已知风险模式。

后续（8.5 人工卡点）：
- 人工复核上述 4 条并在 8.5 报告里标「已确认为测试账号 / 误报」；
- step11 给 `security_scan_secrets.py` 增加「demo 账号字面量」与「Vue `:password` 属性」两条豁免口径，避免重复误报。
