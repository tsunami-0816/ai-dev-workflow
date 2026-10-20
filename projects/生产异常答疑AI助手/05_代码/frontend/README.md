# 生产异常答疑 AI 助手 · 前端（Streamlit）

多页面 Streamlit 应用，与后端 FastAPI 联调。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 确保后端已启动（http://127.0.0.1:8000）
#    见 ../backend/README.md

# 3. 启动前端
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

## 页面说明

| 页面 | 路径 | 权限 | 说明 |
|---|---|---|---|
| 首页/登录 | app.py | 公开 | 登录、后端连通性检查、默认账号 |
| 异常问答 | pages/1_问答.py | 登录 | 多轮对话、来源展示、工单触发、反馈 |
| 工单中心 | pages/2_工单.py | 登录 | 工单列表/详情、领取、处理、关闭（可选沉淀） |
| 通知 | pages/3_通知.py | 登录 | 派单通知、未读数、标记已读 |
| 知识库 | pages/4_知识库.py | admin | 上传文档（PDF/Word，扫描件OCR）、列表、删除、重建 |
| 知识审核 | pages/5_知识审核.py | admin | 审核沉淀知识，通过后向量化入库 |
| 效果评估 | pages/6_评估.py | admin | 黄金用例展示、离线评估指引 |
| 用户管理 | pages/7_用户管理.py | admin | 用户列表、创建用户 |

## 配置

后端地址在 `api_client.py` 顶部：
```python
BASE_URL = "http://127.0.0.1:8000/api"
```
如需修改后端地址，改这一行即可。

## 默认账号

| 用户名 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员 |
| repair | repair123 | 维修负责人 |
| process | process123 | 工艺负责人 |
| safety | safety123 | 安全负责人 |
| employee | employee123 | 一线员工 |

## 冒烟主流程

1. employee 登录 → 异常问答
2. admin 登录 → 知识库上传 1 份手册
3. employee 简单提问 → 得到带来源的答案
4. employee 继续追问（多轮上下文）
5. employee 提复杂/安全问题 → 自动派单
6. repair/safety 登录 → 通知收到提醒 → 工单中心领取 → 处理 → 关闭（勾选沉淀）
7. admin 登录 → 知识审核 → 通过（自动入库）
8. employee 再问相似问题 → 命中沉淀知识
