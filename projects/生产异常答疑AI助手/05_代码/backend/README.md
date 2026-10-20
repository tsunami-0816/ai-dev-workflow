# 生产异常答疑 AI 助手 · 后端（FastAPI）

RAG 答疑 + 异常分级派单 + 知识沉淀的本地 MVP 后端。配套前端见 `../frontend/`。

## 环境要求

- Windows / Linux / macOS，Python 3.10–3.12（开发机：Python 3.11.9）
- 本地模型：Ollama（推荐，4GB 显存可跑 `qwen2.5:3b-instruct-q4_K_M`）
- 扫描件 OCR（可选 P1）：系统级安装 Tesseract（含 `chi_sim` 中文语言包）与 poppler
- 内存 ≥ 16GB

## 快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # Linux/macOS

# 2. 安装依赖
pip install -r requirements.txt

# 3. （可选）本地模型
ollama pull qwen2.5:3b-instruct-q4_K_M

# 4. 初始化数据库与种子账号
python scripts/init_db.py

# 5. 启动后端
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后：
- API 文档（Swagger）：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

## 默认账号（首次登录后请改密）

| 用户名 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 管理员（知识库/审核/评估/用户） |
| repair | repair123 | 维修负责人 |
| process | process123 | 工艺负责人 |
| safety | safety123 | 安全负责人 |
| employee | employee123 | 一线员工（提问） |

## 模型切换

编辑 `.env`：

- `MODEL_PROVIDER=local`：本地 Ollama（默认，省钱/离线）
- `MODEL_PROVIDER=api`：阿里云百炼 OpenAI 兼容端点（`API_BASE_URL` / `API_KEY` / `API_MODEL`）

Embedding 同理用 `EMBEDDING_PROVIDER`。

## 扫描件 OCR（P1）

- 安装 Tesseract-OCR，并把 `tessdata` 加入中文简体语言包 `chi_sim`；
- 安装 poppler（pdf2image 依赖），并把 `bin` 加入 PATH；
- 未安装时，文字版 PDF/Word 仍可正常入库，扫描件会报错提示。

## 冒烟主流程（第 6 步必达）

登录(employee) → 上传 1 份手册(admin) → 简单提问得到带来源答案 → 连续追问 → 复杂问题触发派单 → 负责人(repair)收到通知 → 领取/处理/关闭(勾选沉淀) → admin 审核入库 → 相似问题再问命中。

## 目录结构

见 `../../02_架构设计/第二轮技术架构设计文档.md` §9。
