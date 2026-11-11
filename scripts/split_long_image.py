#!/usr/bin/env python3
"""
长截图切分脚本（step00.1 收 JD 长截图时用）
JD 截图经常 1224×5000+，Read 工具直接拒。本脚本按固定高度切段输出。

使用方法：
    python scripts/split_long_image.py <长图路径>
    python scripts/split_long_image.py <长图路径> --chunk-height 1600 --overlap 100

输出：在原图同目录生成 <原名>_part1.png / <原名>_part2.png ...
依赖：pip install Pillow
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("缺少 Pillow，请先运行: pip install Pillow")
    sys.exit(2)


def split_image(src: Path, chunk_h: int, overlap: int) -> list[Path]:
    img = Image.open(src)
    w, h = img.size
    if h <= chunk_h:
        print(f"图片高度 {h}px ≤ 阈值 {chunk_h}px，不需要切分。")
        return []

    out_dir = src.parent
    stem = src.stem
    ext = src.suffix or ".png"
    out_paths = []

    step = chunk_h - overlap  # 步长：每段往下走这么多，重叠 overlap 防止把文字从中间切断
    y = 0
    idx = 1
    while y < h:
        bottom = min(y + chunk_h, h)
        crop = img.crop((0, y, w, bottom))
        out = out_dir / f"{stem}_part{idx}{ext}"
        crop.save(out)
        out_paths.append(out)
        print(f"  ✅ {out.name}  (y={y}~{bottom}, 高 {bottom - y}px)")
        if bottom >= h:
            break
        y += step
        idx += 1
    return out_paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", help="长图路径")
    ap.add_argument("--chunk-height", type=int, default=1600, help="每段高度 px，默认 1600")
    ap.add_argument("--overlap", type=int, default=100, help="段间重叠 px，默认 100（防止切断文字）")
    args = ap.parse_args()

    src = Path(args.image).resolve()
    if not src.exists():
        print(f"文件不存在: {src}")
        return 1

    print(f"切分 {src.name}，每段 {args.chunk_height}px，重叠 {args.overlap}px")
    parts = split_image(src, args.chunk_height, args.overlap)
    if parts:
        print(f"\n共切出 {len(parts)} 段。请把这些 part 文件依次喂给 Read 工具识别 JD 内容。")
    return 0


def _force_utf8_output():
    """Windows 默认 cp936/GBK 控制台下打印中文/emoji 会 UnicodeEncodeError；入口处统一切 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


if __name__ == "__main__":
    _force_utf8_output()
    sys.exit(main())
