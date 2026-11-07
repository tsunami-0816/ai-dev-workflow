#!/usr/bin/env python3
"""
作品集画像扫描器（step00.2）
扫描 D:\\lg\\project\\ 下每个项目目录，提取技术栈和中间件，输出 00_作品集画像库.json。
专治「已经做了 3 个 RAG，又做第 4 个」。

使用方法：
    python scripts/portfolio_scanner.py [--root D:\\lg\\project] [--out 00_作品集画像库.json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 跳过这些目录（顶层目录名）
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".idea", ".vscode",
             "_archive", ".screenshots", "logs", "runtime",
             ".cursor", ".trae", ".pytest_cache", ".github", "skills", "docs"}

# 工作流测试目录下，哪些子目录属于"工作流自身资源"而不是"产出的子项目"
WORKFLOW_INTERNAL_DIRS = {"scripts", "prompts", "skills", "docs", "workflow",
                          "workflow_cli", "workflow_cli.egg-info", ".cursor", ".trae",
                          ".github", ".pytest_cache", ".screenshots", "step00_产出_20261027"}

# 依赖关键词 → 技能点（粗匹配，够用就行）
SKILL_MAP = [
    # Java 生态
    (r"spring-boot-starter-web|spring-boot-starter\b", "Spring Boot"),
    (r"spring-cloud-starter-gateway", "Spring Cloud Gateway"),
    (r"spring-cloud-starter-alibaba-nacos|nacos", "Nacos"),
    (r"spring-cloud-starter", "Spring Cloud"),
    (r"spring-kafka|kafka-clients", "Kafka"),
    (r"spring-boot-starter-data-redis|lettuce|jedis", "Redis"),
    (r"mybatis-plus", "MyBatis-Plus"),
    (r"mybatis", "MyBatis"),
    (r"spring-boot-starter-data-jpa|hibernate", "JPA/Hibernate"),
    (r"mysql-connector|mysql:mysql", "MySQL"),
    (r"postgresql", "PostgreSQL"),
    (r"druid", "Druid 连接池"),
    (r"rocketmq", "RocketMQ"),
    (r"rabbitmq", "RabbitMQ"),
    (r"elasticsearch|spring-data-elasticsearch", "Elasticsearch"),
    (r"minio", "MinIO"),
    (r"jjwt|java-jwt", "JWT"),
    # Python 生态
    (r"fastapi", "FastAPI"),
    (r"streamlit", "Streamlit"),
    (r"flask", "Flask"),
    (r"django", "Django"),
    (r"uvicorn", "Uvicorn"),
    (r"langchain", "LangChain"),
    (r"langgraph", "LangGraph"),
    (r"llama-index", "LlamaIndex"),
    (r"qdrant", "Qdrant 向量库"),
    (r"chromadb|chroma", "Chroma 向量库"),
    (r"milvus", "Milvus 向量库"),
    (r"sentence-transformers|bge", "Embedding 本地模型"),
    (r"openai", "OpenAI API"),
    (r"pytest", "pytest"),
    (r"allure-pytest", "Allure"),
    (r"locust", "Locust 压测"),
    (r"selenium|playwright", "Web UI 自动化"),
    # 前端
    (r"\"vue\"", "Vue"),
    (r"\"react\"", "React"),
    (r"element-plus|element-ui", "Element UI"),
    (r"antd|ant-design", "Ant Design"),
    (r"axios", "Axios"),
    # 基础设施
    (r"docker-compose|docker compose", "Docker Compose"),
    (r"nginx", "Nginx"),
    (r"jenkins", "Jenkins"),
    (r"github-actions", "GitHub Actions"),
    (r"gitlab-ci", "GitLab CI"),
]


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def extract_skills(text: str) -> set[str]:
    found = set()
    for pattern, skill in SKILL_MAP:
        if re.search(pattern, text, re.IGNORECASE):
            found.add(skill)
    return found


def scan_project(proj_dir: Path) -> dict:
    info = {
        "project_name": proj_dir.name,
        "path": str(proj_dir),
        "business_domain": "",
        "tech_stack": [],
        "middleware_used": [],
    }

    # README 前几行当业务领域
    readme = proj_dir / "README.md"
    if readme.exists():
        lines = [l.strip() for l in readme.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]
        # 取第一个非标题非徽章的段落
        for l in lines[:30]:
            if not l.startswith("#") and not l.startswith("![") and not l.startswith(">") and len(l) > 10:
                info["business_domain"] = l[:80]
                break

    # 扫依赖文件
    all_text = ""
    for fname in ["pom.xml", "build.gradle", "requirements.txt", "pyproject.toml",
                  "package.json", "docker-compose.yml", "docker-compose.yaml",
                  "application.yml", "application.yaml", "application.properties"]:
        # 在项目根和 backend/ 下找
        for base in [proj_dir, proj_dir / "05_代码" / "backend", proj_dir / "backend"]:
            f = base / fname
            if f.exists():
                all_text += "\n" + read_text(f)

    skills = extract_skills(all_text)
    info["tech_stack"] = sorted(skills)
    return info


def has_artifact_at(d: Path) -> bool:
    candidate_bases = [d, d / "05_代码" / "backend", d / "backend"]
    return any(
        (base / f).exists()
        for base in candidate_bases
        for f in ["pom.xml", "requirements.txt", "package.json", "pyproject.toml", "README.md"]
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=r"D:\lg\project", help="作品集根目录")
    ap.add_argument("--out", default="00_作品集画像库.json", help="输出 JSON 路径")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"根目录不存在: {root}")
        return 1

    # 待扫描的项目目录列表
    targets: list[Path] = []

    # 1) 扫 root 下一级子目录（老项目、archive 里的项目、工作流测试本身）
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in SKIP_DIRS:
            continue
        targets.append(child)

    # 2) 工作流测试/projects/ 下的子项目单独扫（这些是工作流产出的项目）
    wf_projects = root / "工作流测试" / "projects"
    if wf_projects.exists():
        for child in sorted(wf_projects.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name.startswith("_"):
                continue
            if child.name in {"_TEMPLATE_新项目", "_队列"}:
                continue
            targets.append(child)

    # 3) archive/ 下的子目录也是项目（早期项目，有用）
    archive = root / "archive"
    if archive.exists():
        for child in sorted(archive.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name.startswith("_"):
                continue
            targets.append(child)

    projects = []
    seen = set()
    for d in targets:
        if d in seen:
            continue
        seen.add(d)
        if not has_artifact_at(d):
            continue
        print(f"扫描: {d.relative_to(root)}")
        info = scan_project(d)
        projects.append(info)
        print(f"  → {len(info['tech_stack'])} 个技能点: {', '.join(info['tech_stack'][:8])}")

    out = {
        "_meta": {"root": str(root), "project_count": len(projects)},
        "projects": projects,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共扫描 {len(projects)} 个项目，画像库已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
