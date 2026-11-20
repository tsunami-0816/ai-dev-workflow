import json
import subprocess
import sys
from pathlib import Path

workdir = Path(__file__).resolve().parent
cli_entry = ["design-cli"]
workspace_id = "cws_62304426642379010"
xml_name = sys.argv[1]
tag = xml_name.replace(".xml", "")
payload = (workdir / xml_name).read_text(encoding="utf-8-sig").encode("utf-8")
if len(payload) > 1024 * 1024:
    raise SystemExit("XML 超过 1MB，未提交。")

argv = cli_entry + ["design-workspace", "+create", "--canvas-workspace-id", workspace_id, "--input", "-"]
result = subprocess.run(argv, input=payload, shell=False, cwd=str(workdir), capture_output=True, timeout=180)
(workdir / (tag + ".stdout.bin")).write_bytes(result.stdout)
(workdir / (tag + ".stderr.bin")).write_bytes(result.stderr)
if result.returncode != 0:
    print(result.stderr.decode("utf-8", errors="strict")[:1500])
    raise SystemExit("CLI 退出码 %d" % result.returncode)
response = json.loads(result.stdout.decode("utf-8", errors="strict"))
if response.get("code") != 0:
    raise SystemExit("响应未成功：%s" % json.dumps(response, ensure_ascii=False)[:800])
print(response.get("xml_data"))
