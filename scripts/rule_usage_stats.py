#!/usr/bin/env python3
"""
规则执行率统计脚本
从所有项目的 _失败日志.md 里统计每个 R<id> 真的兜住了几次问题。

用途：step11 规则体检时，不用手动数失败日志，直接跑这个脚本看数据。
输出：每个规则的触发次数 + 按项目分布
"""

import re
import sys
from pathlib import Path
from collections import defaultdict

# 项目根目录
ROOT = Path(__file__).parent.parent

def parse_failure_log(log_path: Path) -> dict:
    """解析单个失败日志，返回 {rule_id: count}
    兼容两种格式：
    - 新格式：有"触发规则"列，直接统计
    - 旧格式：没有"触发规则"列，统计"根因"列作为参考
    """
    rule_counts = defaultdict(int)
    
    if not log_path.exists():
        return rule_counts
    
    text = log_path.read_text(encoding='utf-8')
    lines = text.split('\n')
    
    # 找表头行
    header_idx = None
    rule_col = None
    root_cause_col = None
    for i, line in enumerate(lines):
        if line.startswith('|') and ('触发规则' in line or '根因' in line):
            header_idx = i
            cols = [c.strip() for c in line.split('|')]
            for j, col in enumerate(cols):
                if '触发规则' in col:
                    rule_col = j
                if '根因' in col:
                    root_cause_col = j
            break
    
    if header_idx is None:
        return rule_counts
    
    # 解析数据行（跳过分隔线行 header_idx + 1）
    for line in lines[header_idx + 2:]:
        if not line.startswith('|'):
            continue
        cols = [c.strip() for c in line.split('|')]
        
        # 新格式：统计触发规则
        if rule_col is not None and len(cols) > rule_col:
            rule_cell = cols[rule_col]
            if rule_cell:
                matches = re.findall(r'R-?\d+', rule_cell)
                for m in matches:
                    rule_counts[m] += 1
        
        # 旧格式兼容：统计根因分类（标记为"根因:"前缀，方便区分）
        if rule_col is None and root_cause_col is not None and len(cols) > root_cause_col:
            root_cause = cols[root_cause_col]
            if root_cause:
                # 把根因分类也记下来，作为参考
                key = f"根因:{root_cause}"
                rule_counts[key] += 1
    
    return rule_counts

def main():
    # 找所有项目的失败日志
    projects_dir = ROOT / 'projects'
    if not projects_dir.exists():
        print("❌ projects/ 目录不存在")
        sys.exit(1)
    
    all_rules = defaultdict(int)  # 全局统计
    project_rules = {}  # 按项目统计
    
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith('_'):
            continue
        log_path = project_dir / '_失败日志.md'
        counts = parse_failure_log(log_path)
        if counts:
            project_rules[project_dir.name] = counts
            for rule, count in counts.items():
                all_rules[rule] += count
    
    # 输出
    print("=" * 60)
    print("规则执行率统计（从失败日志自动汇总）")
    print("=" * 60)
    print()
    
    if not all_rules:
        print("（没有找到任何规则触发记录）")
        return
    
    # 按触发次数排序
    sorted_rules = sorted(all_rules.items(), key=lambda x: -x[1])
    
    print(f"{'规则':<10} {'触发次数':<10}")
    print("-" * 30)
    for rule, count in sorted_rules:
        print(f"{rule:<10} {count:<10}")
    
    print()
    print("按项目分布：")
    print()
    
    for project, rules in project_rules.items():
        print(f"  {project}:")
        for rule, count in sorted(rules.items(), key=lambda x: -x[1]):
            print(f"    {rule}: {count}")
    
    print()
    print(f"总计：{len(all_rules)} 条规则被触发过，共 {sum(all_rules.values())} 次记录")

if __name__ == '__main__':
    main()
