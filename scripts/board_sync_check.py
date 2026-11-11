#!/usr/bin/env python3
"""
看板同步检查脚本
检查看板上的进度和实际产物是否一致。

用途：每个步骤结束时跑一下，确认看板和产物同步。
运行：python scripts/board_sync_check.py <项目目录>
退出码：0 = 同步；1 = 不同步
"""

import re
import sys
from pathlib import Path

# 步骤目录映射
STEP_DIRS = {
    "0.1": "00_JD技能点清单.md",
    "0.2": "00_作品集画像库.json",
    "0.3": "00_缺口分析.md",
    "0.4": "00_选题矩阵.md",
    "0.5": "00_项目设计书.md",
    "1": "01_项目基线说明书.md",
    "2": "02_架构设计",
    "3": "03_评审报告",
    "4": "04_任务拆解与开发规范.md",
    "5A": "05_代码/backend",
    "5B": "05_代码/frontend",
    "5.5": "05.5_代码Review",
    "6": "06_冒烟",
    "6.5": "06.5_契约",
    "7": "07_联调",
    "7.5": "07_联调/数据重置记录.md",
    "8": "08_测试",
    "8.5": "08.5_安全扫描",
    "9": "09_验收",
    "10": "10_交付",
    "10.0": "10_交付/工作流自迭代报告.md",
    "10.5": None,  # 推送 GitHub，没有本地产物
    "10.6": "10_交付/简历项目描述.md",
}

# 步骤顺序（用于判断"应该有产物但没有"）
STEP_ORDER = ["0.1", "0.2", "0.3", "0.4", "0.5", "1", "2", "3", "4", "5A", "5B", "5.5", "6", "6.5", "7", "7.5", "8", "8.5", "9", "10", "11"]

def parse_board(board_path: Path) -> dict:
    """解析看板，返回 {current_step, status}"""
    text = board_path.read_text(encoding="utf-8")
    
    # 找当前阶段行（如"- 当前阶段：**已完成（第 11 步 · 工作流自迭代）**"）
    current_step = None
    for line in text.split('\n'):
        if '当前阶段' in line:
            # 在整行里找"第 X 步"
            step_match = re.search(r"第\s*(\d+\.?\d*[AB]?)\s*步", line)
            if step_match:
                current_step = step_match.group(1)
            break
    
    # 找状态
    status_match = re.search(r"总体状态[：:]\s*(\S+)", text)
    status = status_match.group(1) if status_match else None
    
    return {
        "current_step": current_step,
        "status": status,
    }

def check_products(project_dir: Path, current_step: str) -> list:
    """检查当前步骤之前的产物是否都存在"""
    issues = []
    
    if not current_step:
        issues.append("⚠️ 看板没有写当前步骤")
        return issues
    
    # 找当前步骤在顺序中的位置
    try:
        current_idx = STEP_ORDER.index(current_step)
    except ValueError:
        issues.append(f"⚠️ 未知步骤：{current_step}")
        return issues
    
    # 检查前面所有步骤的产物是否存在
    for i in range(current_idx + 1):
        step = STEP_ORDER[i]
        expected = STEP_DIRS.get(step)
        if expected is None:
            continue  # 跳过没有产物的步骤
        
        expected_path = project_dir / expected
        if not expected_path.exists():
            issues.append(f"❌ 看板已到 step{step}，但产物不存在：{expected}")
    
    return issues

def main():
    if len(sys.argv) < 2:
        print("用法：python scripts/board_sync_check.py <项目目录>")
        sys.exit(1)
    
    project_dir = Path(sys.argv[1])
    board_path = project_dir / "_项目状态.md"
    
    if not board_path.exists():
        print(f"❌ 看板不存在：{board_path}")
        sys.exit(1)
    
    board = parse_board(board_path)
    issues = check_products(project_dir, board["current_step"])
    
    print("=" * 60)
    print("看板同步检查")
    print("=" * 60)
    print()
    print(f"当前步骤：{board['current_step']}")
    print(f"状态：{board['status']}")
    print()
    
    if not issues:
        print("✅ 看板与产物同步")
        return 0
    else:
        print("❌ 发现不同步：")
        for issue in issues:
            print(f"  {issue}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
