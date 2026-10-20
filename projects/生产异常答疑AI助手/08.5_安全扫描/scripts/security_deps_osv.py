"""第 8.5 步安全扫描 · 依赖 CVE 检查（pip-audit 网络超时，改用同源 OSV API 直查）。
查询本地已安装的关键依赖版本在 OSV 漏洞库中的记录。
"""
import json
import subprocess
import urllib.request

PKGS = [
    "fastapi", "uvicorn", "pydantic", "pydantic-settings", "python-multipart",
    "httpx", "SQLAlchemy", "python-jose", "bcrypt", "langchain",
    "langchain-community", "langchain-text-splitters", "langchain-openai",
    "chromadb", "sentence-transformers", "rank_bm25", "jieba", "pypdf",
    "docx2txt", "pytesseract", "pdf2image", "python-dotenv", "numpy",
    "streamlit", "requests", "urllib3", "jinja2", "cryptography", " Pillow".strip(),
]


def installed_version(name):
    try:
        out = subprocess.run(
            ["pip", "show", name], capture_output=True, text=True, timeout=30
        ).stdout
        for line in out.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


queries = []
meta = []
for p in PKGS:
    v = installed_version(p)
    if v:
        queries.append({"package": {"name": p.lower(), "ecosystem": "PyPI"}, "version": v})
        meta.append((p, v))

body = json.dumps({"queries": queries}).encode()
req = urllib.request.Request(
    "https://api.osv.dev/v1/querybatch",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode())

print(f"查询 {len(meta)} 个已安装依赖：\n")
total_vulns = 0
for (name, ver), result in zip(meta, data.get("results", [])):
    vulns = result.get("vulns") or []
    if vulns:
        total_vulns += len(vulns)
        ids = [v.get("id", "?") for v in vulns]
        print(f"[有漏洞] {name}=={ver}: {len(vulns)} 条 -> {', '.join(ids[:8])}")
    else:
        print(f"[OK] {name}=={ver}")
print(f"\n合计漏洞数: {total_vulns}")
