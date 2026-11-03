"""F0 闸门补跑 + 看板写"""
import subprocess
from pathlib import Path
import re, datetime

root = Path(r"D:\lg\project\工作流测试")
source = Path(r"D:\lg\project\SparrowScheduler").resolve()
target = root / "projects" / "SparrowScheduler"

def count_files(d):
    return sum(1 for _ in d.rglob("*") if _.is_file())

def git_head(d):
    r = subprocess.run(["git","rev-parse","--short","HEAD"], cwd=str(d), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""

def git_remote(d):
    r = subprocess.run(["git","remote","get-url","origin"], cwd=str(d), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""

def count_files_clean(d):
    skip = {"node_modules", "dist", "target", "__pycache__", ".idea", ".vscode"}
    return sum(1 for _ in d.rglob("*") if _.is_file() and not any(part in skip for part in _.parts))

print(f"\n=== F0 闸门补跑 ===\n")

src_c = count_files(source)
tgt_c = count_files(target)
src_clean = count_files_clean(source)
tgt_clean = count_files_clean(target)
diff_clean = abs(src_clean - tgt_clean) / max(src_clean, 1)

git_ok = (target / ".git").exists()
remote = git_remote(target)
baseline = git_head(target)

print(f"源文件（含 node_modules/target）：{src_c}")
print(f"目标文件（排除垃圾目录）：{tgt_c}")
print(f"干净文件比对：源 {src_clean} vs 目标 {tgt_clean}，差异率 {diff_clean:.2%}")
print(f".git：{'有' if git_ok else '无'}")
print(f"remote：{remote or '（无）'}")
print(f"baseline：{baseline or '（无）'}")

print(f"\n干净文件比对（都排除垃圾目录）：源 {src_clean} vs 目标 {tgt_clean}，差异率 {diff_clean:.2%}")

issues = []
if diff_clean > 0.05:
    issues.append(f"文件差异率 {diff_clean:.2%} 超过 5%")
if not git_ok:
    issues.append("目标缺 .git")

if issues:
    print(f"\n🔴 闸门报红：{issues}")
else:
    print(f"\n🟢 闸门全绿！")
    # === 写看板 ===
    today = datetime.date.today().isoformat()
    board = target / "_项目状态.md"
    board.write_text(f"""# 项目状态看板 · SparrowScheduler

> 路线：**翻新线（野生入口）**
> 来源：`D:\lg\project\SparrowScheduler`
> 迁入日期：{today}
> git 基线 commit：`{baseline}`

---

## 基本信息

- 项目名：**SparrowScheduler · 分布式任务调度平台**
- 原始描述路径：`D:\lg\project\SparrowScheduler`
- 创建日期：**{today}**（翻新建档）
- 当前阶段：**F0 · 迁入建档 ✅** → 下一步 **F1 逆向建档**
- 总体状态：进行中（翻新线）
- **路线**：翻新（野生入口）
- **源路径**：`D:\lg\project\SparrowScheduler`
- **远程仓库 URL**：{remote or '（无，F4 交付时 push）'}
- **git 基线 commit**：`{baseline or '（无）'}`
- **体检报告路径**：F2_体检/体检报告.md（F2 完成后落盘）

### 端口分配

| 服务 | 端口 | 说明 |
|---|---|---|
| 后端 admin | 8087 | Spring Boot（翻新线自动分配） |
| 前端 web | 5180 | Vue 3 + Vite |
| MySQL | 3310 | 共用 |
| Redis | 6379 | 共用 |

---

## 步骤进度

| 步骤 | 名称 | 状态 | 产物路径 | 备注 |
|---|---|---|---|---|
| F0 | 迁入建档 | ✅ 已完成 | `projects/SparrowScheduler/` | 闸门全绿；干净文件 {src_clean} vs {tgt_clean}，差异 {diff_clean:.2%} |
| F1 | 逆向建档 | 未开始 | | 待扫描代码树逆向产出设计书+基线 |
| 👤 R-1 | 基线拍板 | 未开始 | | 用户确认设计书和基线目标值 |
| F2 | 七维度体检 | 未开始 | `F2_体检/体检报告.md` | 七维度机器校验 + AI 审查 |
| 👤 R-2 | 返修确认 | 未开始 | | 用户过分级清单，确认全面返修 |
| F3 | 返修 | 未开始 | | 按台账根因路由，强制走完生产线全序列 |
| F4 | 交付 | 未开始 | | = 生产线 step10→10.0→10.5→10.6→11 |

---

## 卡点待办

| 卡点 | 触发条件 | 状态 |
|---|---|---|
| 👤 R-1 基线拍板 | F1 逆向建档完成 | 未触发 |
| 👤 R-2 返修确认 | F2 体检报告落盘 | 未触发 |

---

## 轮次日志

| 日期 | 步骤 | 轮次 | 说明 |
|---|---|---|---|
| {today} | F0 | - | 野生入口迁入，闸门全绿（文件比对排除 node_modules/target/dist） |
""", encoding="utf-8")
    print(f"✅ 看板已写入：{board}")
    print(f"\n下一步：跑 F1 逆向建档")
