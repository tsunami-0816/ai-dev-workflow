"""拉取 python-multipart / python-jose 漏洞详情（severity + summary）。"""
import json
import urllib.request

IDS = {
    "python-multipart==0.0.9": [
        "GHSA-59g5-xgcq-4qw3", "GHSA-5rvq-cxj2-64vf", "GHSA-6jv3-5f52-599m",
        "GHSA-mj87-hwqh-73pj", "GHSA-pp6c-gr5w-3c5g", "GHSA-v9pg-7xvm-68hf",
        "GHSA-vffw-93wf-4j4q", "GHSA-wp53-j4wj-2cfg",
    ],
    "python-jose==3.5.0": ["GHSA-3qf3-8w2g-rqmx", "PYSEC-2026-4298"],
}

for pkg, ids in IDS.items():
    print(f"\n===== {pkg} =====")
    for vid in ids:
        try:
            with urllib.request.urlopen(f"https://api.osv.dev/v1/vulns/{vid}", timeout=30) as r:
                d = json.loads(r.read().decode())
            sev = ""
            for s in d.get("severity", []):
                sev += f"{s.get('type')}:{s.get('score')} "
            aliases = ",".join(a for a in d.get("aliases", []) if a.startswith("CVE"))
            summary = (d.get("summary") or "")[:110]
            print(f"{vid} | {aliases} | {sev.strip() or 'no-cvss'} | {summary}")
        except Exception as e:
            print(f"{vid} | FETCH_FAIL {e}")
