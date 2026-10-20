"""测量向量距离分布，为相关性门槛提供数据（ACC-01 修复依据）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "05_代码", "backend"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from app.rag.vectorstore import get_vectorstore

vs = get_vectorstore()
QUERIES = {
    "库外问题(应拒)": "传送带跑偏怎么调？",
    "库外问题2(应拒)": "今天天气怎么样",
    "库内问题(应过)": "联调问题清单怎么整理",
    "库内问题2(应过)": "项目自动流程是什么",
    "库内问题3(应过)": "人工检查点是什么",
}
for label, q in QUERIES.items():
    hits = vs.similarity_search_with_score(q, k=8)
    ds = [round(float(d), 3) for _, d in hits]
    print(f"{label} 「{q}」 distances(top8,越小越相似): {ds}")
