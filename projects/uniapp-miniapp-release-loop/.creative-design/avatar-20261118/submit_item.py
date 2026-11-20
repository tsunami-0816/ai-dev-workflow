import json
import subprocess
import sys
from pathlib import Path

workdir = Path(__file__).resolve().parent
cli_entry = ["design-cli"]
workspace_id = "cws_62304426642379010"
xml_name = sys.argv[1] if len(sys.argv) > 1 else "item-v1.xml"
tag = xml_name.replace(".xml", "")
xml_text = (workdir / xml_name).read_text(encoding="utf-8-sig")
payload = xml_text.encode("utf-8")
if not xml_text.strip() or len(payload) > 1024 * 1024:
    raise SystemExit("XML 为空或超过 1MB 上限，未提交。")

argv = cli_entry + [
    "design-workspace", "+create",
    "--canvas-workspace-id", workspace_id, "--input", "-",
]
result = subprocess.run(argv, input=payload, shell=False, cwd=str(workdir),
                        capture_output=True, timeout=180)
(workdir / (tag + ".stdout.bin")).write_bytes(result.stdout)
(workdir / (tag + ".stderr.bin")).write_bytes(result.stderr)
(workdir / (tag + ".exitcode.txt")).write_text(str(result.returncode), encoding="utf-8")
if result.returncode != 0:
    print((result.stderr.decode("utf-8", errors="strict"))[:2000])
    raise SystemExit("CLI 退出码 %d" % result.returncode)
response = json.loads(result.stdout.decode("utf-8", errors="strict"))
if response.get("code") != 0:
    raise SystemExit("响应未成功：" + json.dumps(response, ensure_ascii=False)[:1000])
print(response.get("xml_data"))
