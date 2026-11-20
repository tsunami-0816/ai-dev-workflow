import sys
import urllib.request
from pathlib import Path
from PIL import Image

workdir = Path(__file__).resolve().parent
src_url = "https://aka.doubaocdn.com/s/WObuR72alL"
local_src = workdir / "avatar-2048.jpg"
local_144 = workdir / "avatar-144.png"
out_144 = Path(r"D:\lg\project\工作流测试\projects\uniapp-miniapp-release-loop\10_交付\小程序头像-144.png")

req = urllib.request.Request(src_url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=90) as resp:
    data = resp.read()
local_src.write_bytes(data)
print("downloaded bytes:", len(data))

img = Image.open(local_src).convert("RGB")
print("source size:", img.size)
img144 = img.resize((144, 144), Image.LANCZOS)
img144.save(local_144, format="PNG", optimize=True)
out_144.parent.mkdir(parents=True, exist_ok=True)
img144.save(out_144, format="PNG", optimize=True)
print("144 size:", Image.open(out_144).size, "bytes:", out_144.stat().st_size)
