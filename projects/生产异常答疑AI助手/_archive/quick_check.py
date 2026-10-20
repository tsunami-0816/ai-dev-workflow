"""快速查 ticket + notification DB 关系"""
import sqlite3
db = sqlite3.connect("../../runtime/app.db")
print("=== T20261020-0007 ===")
for row in db.execute("SELECT id, route_type, severity, question FROM ticket WHERE id='T20261020-0007'"):
    print(" ", row)
print("\n=== notifications ref_id=T20261020-0007 ===")
for row in db.execute("SELECT id, user_id, type, title, ref_id FROM notification WHERE ref_id='T20261020-0007'"):
    print(" ", row)
print("\n=== user roles ===")
for row in db.execute("SELECT id, username, role FROM user WHERE is_active=1"):
    print(" ", row)
print("\n=== notifications per role for T20261020-0007 ===")
for row in db.execute("""
    SELECT u.role, COUNT(n.id) as cnt
    FROM notification n JOIN user u ON n.user_id = u.id
    WHERE n.ref_id='T20261020-0007'
    GROUP BY u.role
"""):
    print(f"  role={row[0]}, count={row[1]}")
print("\n=== 最新 5 个工单 ===")
for row in db.execute("SELECT id, route_type, severity FROM ticket ORDER BY id DESC LIMIT 5"):
    print(" ", row)
print("\n=== 最新 10 条通知（title 含 知识库）===")
for row in db.execute("SELECT user_id, title FROM notification WHERE title LIKE '%知识库%' ORDER BY id DESC LIMIT 10"):
    print(" ", row)
