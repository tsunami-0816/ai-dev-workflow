#!/usr/bin/env python3
"""
JD 技能点对账器（step00.5 卡点2 机器校验）
专治「JD 要 Kafka，设计书里只写了个 Kafka 名字就算覆盖」。

使用方法：
    python scripts/skills_coverage_checker.py \
        --skills-json 00_JD技能点清单.json \
        --design-doc projects/<项目>/00_项目设计书.md \
        [--portfolio-json 00_作品集画像库.json] \
        [--required-sections 6,7,8]     # 只校验指定节（缺任一即退出码 1）

skills-json 格式（step00.1 拆解 JD 的输出直接喂进来即可）：
    {
      "hard_stack": ["Java", "Spring Boot", "Kafka", ...],
      "architecture_skills": ["高并发", "缓存一致性", ...],
      "must_have": ["Java", "Kafka", ...]   // 可选，不填就 hard_stack 全算 must_have
    }

退出码：must_have 覆盖率 100% 且设计书 9 节齐全返回 0，否则返回 1。
（设计书缺节可用 --skip-sections 临时跳过，用于历史项目补跑；新项目不得跳过。）

REQUIRED_SECTIONS（step00.5 一页纸设计书必备 9 节）：
    1 一句话定位 / 2 业务场景 / 3 技术架构 / 4 硬骨头模块 / 5 JD 技能点对账表
    6 工作量拆解（人天×模块）/ 7 面试三问 / 8 主动砍掉项 / 9 风险点
"""

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    ("一句话定位", ["一句话定位", "一句话", "项目定位"]),
    ("业务场景", ["业务场景", "业务背景", "使用场景"]),
    ("技术架构", ["技术架构", "系统架构", "架构设计"]),
    ("硬骨头模块", ["硬骨头", "技术难点", "核心难点", "难点模块"]),
    ("JD 技能点对账表", ["技能点对账", "JD 对账", "技能点覆盖", "对账表"]),
    ("工作量拆解", ["工作量拆解", "工作量", "人天"]),
    ("面试三问", ["面试三问", "面试", "三问"]),
    ("主动砍掉项", ["主动砍掉", "砍掉", "不实现", "排除项"]),
    ("风险点", ["风险点", "风险", "约束"]),
]


# 同义词/简称映射：左边是 JD 里写的词，右边是设计书里可能出现的写法
ALIAS = {
    "spring boot": ["springboot", "spring boot", "spring-boot"],
    "spring cloud": ["springcloud", "spring cloud", "spring-cloud"],
    "kafka": ["kafka"],
    "rabbitmq": ["rabbitmq", "rabbit mq"],
    "rocketmq": ["rocketmq", "rocket mq"],
    "redis": ["redis"],
    "mysql": ["mysql"],
    "postgresql": ["postgres", "postgresql"],
    "mongodb": ["mongodb", "mongo"],
    "elasticsearch": ["elasticsearch", "es", "elastic"],
    "mybatis": ["mybatis"],
    "mybatis-plus": ["mybatis-plus", "mybatis plus", "mybatisplus"],
    "jpa": ["jpa", "hibernate"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git"],
    "pytest": ["pytest"],
    "jmeter": ["jmeter"],
    "jenkins": ["jenkins"],
    "github actions": ["github actions", "gh actions", "github-actions"],
    "ci/cd": ["ci/cd", "cicd", "ci cd", "持续集成"],
    "restful": ["restful", "rest", "restful api"],
    "graphql": ["graphql"],
    "websocket": ["websocket", "web socket"],
    "jwt": ["jwt", "json web token"],
    "oauth2": ["oauth2", "oauth 2.0", "oauth"],
    "mysql主从": ["主从", "mysql主从", "读写分离"],
    "读写分离": ["读写分离", "主从"],
    "分库分表": ["分库分表", "sharding", "shardingsphere"],
    "分布式事务": ["分布式事务", "seata", "tcc", "saga"],
    "缓存一致性": ["缓存一致", "缓存穿透", "缓存击穿", "缓存雪崩", "cache aside"],
    "高并发": ["高并发", "并发", "qps", "tps"],
    "高可用": ["高可用", "ha", "集群"],
    "消息队列": ["消息队列", "mq", "kafka", "rabbitmq", "rocketmq"],
    "微服务": ["微服务", "microservice", "spring cloud"],
    "ddd": ["ddd", "领域驱动"],
    "rag": ["rag", "检索增强", "retrieval-augmented"],
    "向量数据库": ["向量库", "向量数据库", "qdrant", "milvus", "chroma", "weaviate"],
    "langchain": ["langchain"],
    "llm": ["llm", "大模型", "gpt", "deepseek", "通义"],
    "openai": ["openai", "gpt"],
    "fastapi": ["fastapi"],
    "springboot": ["spring boot", "springboot"],
    "vue": ["vue"],
    "react": ["react"],
    "streamlit": ["streamlit"],
}


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def skill_in_text(skill: str, text_lower: str) -> tuple[bool, str]:
    """判断一个技能点是否在设计书里出现。返回 (是否命中, 匹配到的词)。"""
    key = normalize(skill)
    # 先查别名表
    aliases = ALIAS.get(key, [key])
    for a in aliases:
        if a.lower() in text_lower:
            return True, a
    # 直接 substring
    if key in text_lower:
        return True, key
    return False, ""


def parse_required_sections(spec: str) -> list[tuple[str, list[str]]]:
    """解析 --required-sections：支持 1-based 序号（6,7,8）或节名关键词。"""
    if not spec:
        return list(REQUIRED_SECTIONS)
    picked = []
    for raw in spec.split(','):
        token = raw.strip()
        if not token:
            continue
        if token.isdigit():
            idx = int(token) - 1
            if not 0 <= idx < len(REQUIRED_SECTIONS):
                raise ValueError(f"节号 {token} 超出范围 1~{len(REQUIRED_SECTIONS)}")
            picked.append(REQUIRED_SECTIONS[idx])
            continue
        matched = [sec for sec in REQUIRED_SECTIONS
                   if token in sec[0] or any(token in k for k in sec[1])]
        if not matched:
            raise ValueError(f"无法识别的节名: {token}")
        picked.extend(matched)
    # 去重保序
    seen, out = set(), []
    for sec in picked:
        if sec[0] not in seen:
            seen.add(sec[0])
            out.append(sec)
    return out


def check_sections(text_lower: str, sections: list | None = None) -> tuple[list[str], list[str]]:
    """设计书必备节存在性检查，返回 (已存在, 缺失)"""
    present, missing = [], []
    for name, keys in (sections if sections is not None else REQUIRED_SECTIONS):
        if any(k.lower() in text_lower for k in keys):
            present.append(name)
        else:
            missing.append(name)
    return present, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills-json", required=True, help="step00.1 输出的 JD 技能点 JSON")
    ap.add_argument("--design-doc", help="00_项目设计书.md 路径（--portfolio-mode 时可不填）")
    ap.add_argument("--portfolio-json", help="00_作品集画像库.json 路径，用于对账和撞车检测")
    ap.add_argument("--portfolio-mode", action="store_true",
                    help="对账模式：不看设计书，直接拿 JD 技能点 vs portfolio.json 里所有项目的 tech_stack")
    ap.add_argument("--skip-sections", action="store_true",
                    help="跳过设计书 9 节检查（仅限历史项目补跑，新项目不得跳过）")
    ap.add_argument("--required-sections", default="",
                    help="只校验指定节：序号（如 6,7,8）或节名关键词；缺任一并退出码 1。"
                         "默认校验全部 9 节（改进建议 #55）")
    args = ap.parse_args()

    skills_data = json.loads(Path(args.skills_json).read_text(encoding="utf-8"))
    hard = skills_data.get("hard_stack", [])
    arch = skills_data.get("architecture_skills", [])
    must = skills_data.get("must_have") or hard

    # ===== 对账模式：JD vs 已有作品集 =====
    if args.portfolio_mode:
        if not args.portfolio_json:
            print("❌ --portfolio-mode 必须配 --portfolio-json")
            return 2
        port = json.loads(Path(args.portfolio_json).read_text(encoding="utf-8"))
        projects = port.get("projects", [])
        print("=" * 60)
        print(f"JD vs 作品集对账：{args.skills_json}")
        print("=" * 60)
        print(f"作品集共 {len(projects)} 个项目\n")

        all_skills = [(s, "hard", s in must) for s in hard] + \
                     [(s, "arch", s in must) for s in arch]

        covered, missing = [], []
        for skill, cat, is_must in all_skills:
            hit_projects = []
            for p in projects:
                stack_lower = [x.lower() for x in p.get("tech_stack", [])]
                _, matched = skill_in_text(skill, " ".join(stack_lower))
                if matched:
                    hit_projects.append(p.get("project_name", "?"))
            if hit_projects:
                covered.append((skill, cat, is_must, hit_projects))
            else:
                missing.append((skill, cat, is_must))

        print("✅ 已有项目覆盖：")
        for s, cat, is_must, projs in covered:
            flag = " [MUST]" if is_must else ""
            print(f"  {flag} [{cat}] {s}  ← {', '.join(projs[:3])}")

        print(f"\n❌ 缺口（无项目覆盖）：")
        for s, cat, is_must in missing:
            flag = " [MUST]" if is_must else ""
            print(f"  {flag} [{cat}] {s}")

        must_missing = [s for s, _, is_must in missing if is_must]
        must_total = len(must)
        must_covered = must_total - len(must_missing)
        print(f"\nmust_have 覆盖率: {must_covered}/{must_total} = {must_covered/max(must_total,1)*100:.0f}%")

        if must_missing:
            print(f"\n→ 缺口技能点: {', '.join(must_missing)}")
            print("→ 走求职侧设计台补项目，或查硬件豁免清单")
            return 1
        print("\n✅ must_have 100% 覆盖，可直接出简历。")
        return 0

    # ===== 原模式：JD vs 设计书 =====
    if not args.design_doc:
        print("❌ 非 --portfolio-mode 必须传 --design-doc")
        return 2
    design_text = Path(args.design_doc).read_text(encoding="utf-8", errors="ignore").lower()

    all_skills = []
    for s in hard:
        all_skills.append((s, "hard_stack", s in must))
    for s in arch:
        all_skills.append((s, "architecture", s in must))

    covered, shallow, missing = [], [], []
    for skill, cat, is_must in all_skills:
        hit, matched = skill_in_text(skill, design_text)
        if hit:
            # 检查是否只是"提了个名字"：设计书里该词出现次数 ≤1 且附近没有机制描述词
            count = design_text.count(matched.lower())
            if count <= 1:
                shallow.append((skill, cat, matched, f"仅出现 {count} 次，疑似只是列了个名字"))
            else:
                covered.append((skill, cat, matched))
        else:
            missing.append((skill, cat))

    must_set = set(must)
    missing_must = [s for s, _ in missing if s in must_set]

    print("=" * 60)
    print(f"JD 技能点对账：{args.design_doc}")
    print("=" * 60)

    # 设计书 9 节存在性（缺 §6 工作量/§7 硬骨头/§8 砍掉项会让第 10 步复盘降级为定性）
    missing_sections = []
    if args.skip_sections:
        print("\n⏭️  已跳过设计书必备节检查（--skip-sections）")
    else:
        try:
            sections = parse_required_sections(args.required_sections)
        except ValueError as e:
            print(f"❌ --required-sections 参数错误: {e}")
            return 2
        present_sections, missing_sections = check_sections(design_text, sections)
        label = args.required_sections or "全部 9 节"
        print(f"\n设计书必备节检查（{label}）：{len(present_sections)}/{len(sections)} 存在")
        if missing_sections:
            print(f"  ❌ 缺失: {', '.join(missing_sections)}")
        else:
            print(f"  ✅ {len(sections)} 节齐全")

    print(f"\n总技能点 {len(all_skills)} 个（hard_stack {len(hard)} + architecture {len(arch)}）")
    print(f"must_have {len(must)} 个\n")

    print(f"✅ 已覆盖（{len(covered)}）：")
    for s, cat, m in covered:
        print(f"   [{cat}] {s}  (匹配: {m})")

    print(f"\n⚠️  浅覆盖（{len(shallow)}，需要人工确认是否真落地）：")
    for s, cat, m, note in shallow:
        flag = " [MUST]" if s in must_set else ""
        print(f"   [{cat}]{flag} {s}  ({note})")

    print(f"\n❌ 未覆盖（{len(missing)}）：")
    for s, cat in missing:
        flag = " [MUST]" if s in must_set else ""
        print(f"   [{cat}]{flag} {s}")

    # 撞车检测
    if args.portfolio_json and Path(args.portfolio_json).exists():
        port = json.loads(Path(args.portfolio_json).read_text(encoding="utf-8"))
        new_stack = set(s.lower() for s, _, _ in covered + shallow)
        print(f"\n--- 撞车检测 ---")
        for proj in port if isinstance(port, list) else port.get("projects", []):
            name = proj.get("project_name", "?")
            old_stack = set(x.lower() for x in proj.get("tech_stack", []))
            overlap = new_stack & old_stack
            if len(overlap) >= 3:
                print(f"   ⚠️  与 {name} 技术栈重叠 {len(overlap)} 个: {', '.join(list(overlap)[:5])}")
                print(f"      请确认业务领域/硬骨头是否有差异，否则算撞车")

    total = len(all_skills)
    must_total = len(must)
    must_covered = must_total - len(missing_must)
    print(f"\n{'='*60}")
    print(f"must_have 覆盖率: {must_covered}/{must_total} = {must_covered/must_total*100:.0f}%")
    print(f"总覆盖率: {len(covered)}/{total} = {len(covered)/total*100:.0f}%")

    if missing_must or missing_sections:
        if missing_must:
            print(f"\n❌ must_have 有 {len(missing_must)} 个未覆盖: {', '.join(missing_must)}")
            print("   → 补设计，或在设计书 §8 主动砍掉清单里写明「由项目 N 覆盖/不实现」")
        if missing_sections:
            print(f"\n❌ 设计书缺 {len(missing_sections)} 节: {', '.join(missing_sections)}")
            print("   → 按 step00.5 一页纸 9 节结构补齐后再进入 step01（历史项目补跑可用 --skip-sections）")
        return 1
    print("\n✅ must_have 覆盖率 100%、设计书必备节齐全，通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
