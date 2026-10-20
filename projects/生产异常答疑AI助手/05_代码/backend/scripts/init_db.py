"""数据库初始化：建表 + 5 个种子账号 + 黄金测试用例。
用法：python scripts/init_db.py
"""
import os
import sys

# 让脚本可以从 backend 根目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.engine import engine  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import QATestCase, User  # noqa: E402

SEED_USERS = [
    ("admin", "admin123", "管理员", "admin"),
    ("repair", "repair123", "维修负责人", "repair"),
    ("process", "process123", "工艺负责人", "process"),
    ("safety", "safety123", "安全负责人", "safety"),
    ("employee", "employee123", "一线员工", "employee"),
]

SEED_CASES = [
    ("设备故障", "CNC 机床报警 E023 主轴过载怎么办？", "检查主轴负载、刀具磨损，必要时停机报修", "ticket", "P1"),
    ("设备故障", "空压机压力上不去是什么原因？", "检查进气阀、漏气点、压力传感器", "ticket", "P1"),
    ("设备故障", "传送带跑偏怎么调？", "调整两侧张紧轮，空载试运行", "answer", "P2"),
    ("工艺异常", "注塑件出现飞边怎么调参数？", "降低注射压力/保压，检查模具合模力", "ticket", "P1"),
    ("工艺异常", "反应釜温度一直降不下来，配方要求 80 度", "检查冷却水阀、温控仪表，联系工艺", "ticket", "P1"),
    ("工艺异常", "SMT 贴片偏移的标准公差是多少？", "查 IPC-A-610，通常 ≤0.1mm 或焊盘 25%", "answer", "P2"),
    ("安全规范", "进入有限空间作业要办什么票？", "有限空间作业票，气体检测，专人监护", "ticket", "P0"),
    ("安全规范", "灭火器多久检查一次？", "每月点检，每年年检", "answer", "P2"),
    ("安全规范", "高处作业安全带怎么挂？", "高挂低用，挂在牢固构件上", "answer", "P2"),
    ("其他", "班前点检表在哪里签字？", "在车间看板的点检表上签字", "answer", "P2"),
    ("其他", "设备保养周期是多久？", "日常点检每日，一级保养每月，二级保养每季度", "answer", "P2"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, pwd, name, role in SEED_USERS:
            if not db.query(User).filter(User.username == username).first():
                db.add(
                    User(
                        username=username,
                        password_hash=hash_password(pwd),
                        display_name=name,
                        role=role,
                    )
                )
                print(f"[+] 创建账号: {username}/{pwd}  角色={role}")
        for scenario, q, a, route, sev in SEED_CASES:
            if not db.query(QATestCase).filter(QATestCase.question == q).first():
                db.add(
                    QATestCase(
                        scenario=scenario,
                        question=q,
                        standard_answer=a,
                        expected_route=route,
                        severity=sev,
                    )
                )
        db.commit()
        print(f"\n初始化完成：用户 {db.query(User).count()} 个，黄金用例 {db.query(QATestCase).count()} 条")
        print("默认账号：admin/admin123、repair/repair123、process/process123、safety/safety123、employee/employee123")
    finally:
        db.close()


if __name__ == "__main__":
    main()
