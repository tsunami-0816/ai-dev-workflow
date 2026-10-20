# 第 8.5 步 · 安全扫描与渗透检查（👤 人工卡点，验收前强制）

- **角色**：资深安全工程师 / 渗透测试工程师
- **输入**：第 8 步全量测试通过的完整系统代码 + 部署配置 + 接口文档
- **输出物**（落盘 `08.5_安全扫描/docs/安全扫描报告.md`）：
  - 《安全扫描问题清单》（P0/P1 必修，P2/P3 留档）
  - 《安全扫描通过证明》（ checklist 逐项勾选）
- **卡点规则**：本步为**强制卡点**，扫描出 P0/P1 安全问题未修复前，禁止进入第 9 步最终验收。

---

## 为什么必须有这一步

AI 生成代码的经典安全问题，靠第 8 步功能测试**测不出来**：

| 问题类型 | 功能测试为什么测不出 | 真实后果 |
|---------|-------------------|---------|
| 硬编码密钥 / 密码 | 功能正常，密钥能用 | 源码泄露即系统沦陷 |
| SQL 注入 / 命令注入 | 正常输入功能正常 | 攻击者拖库、删库、RCE |
| 鉴权缺失 / 越权访问 | 普通用户走正常流程没问题 | 横向越权看别人数据、纵向越权调管理员接口 |
| 敏感信息泄露 | 功能正常，日志/返回体带敏感字段 | 用户隐私泄露、内部路径暴露 |
| 依赖包漏洞 | 功能正常，运行无报错 | 已知 CVE 被利用，供应链攻击 |
| 文件上传 / 路径穿越 | 正常上传功能正常 |  webshell 上传、任意文件读取 |

---

## 8.5.1 安全扫描 Prompt（代码级 + 配置级）

> 使用方式：Agent 扮演安全工程师，**用户配合执行自动化脚本**，把脚本结果和代码一起喂给 AI 分析。

```
你是资深安全工程师，对以下项目进行代码级安全扫描。请逐条检查，不要遗漏。

【检查清单】

## 一、敏感信息硬编码（最高优先级）
1. 搜索所有代码文件中的明文密码、API Key、Secret Key、Token、数据库连接字符串
2. 检查配置文件（.env、config.py、application.yml 等）是否包含真实密钥而非占位符
3. 检查日志、异常堆栈、返回体是否泄露敏感路径、内部 IP、数据库结构
4. 检查 Git 历史（如已提交）是否含密钥

## 二、注入类漏洞
5. SQL 注入：所有数据库查询是否使用参数化查询/ORM 预编译，禁止字符串拼接 SQL
6. 命令注入：是否用 os.system / subprocess / eval / exec 执行用户输入
7. 模板注入：是否将用户输入直接拼入模板渲染（如 Jinja2、Vue 模板）
8. 路径穿越：文件上传/下载/读取是否限制在指定目录，过滤 ../ 等路径穿越字符

## 三、鉴权与访问控制
9. 每个接口是否都有明确的权限校验（除公开接口如 /auth/login、/health 外）
10. 是否存在「只在前端隐藏、后端不校验」的假鉴权
11. 越权测试：普通用户能否通过修改 ID 访问/操作他人数据（水平越权）
12. 越权测试：普通用户能否直接调用管理员接口（垂直越权）
13. 登录态是否可伪造（如 JWT 未校验签名、Session 固定攻击）

## 四、数据安全与隐私
14. 敏感字段（密码、身份证、手机号）是否加密存储，返回体是否脱敏
15. 密码是否使用强哈希（bcrypt / argon2 / scrypt），禁止 MD5 / SHA1 明文
16. 会话/Cookie 是否设置 HttpOnly、Secure、SameSite
17. 是否存在敏感数据明文落盘（日志、临时文件、数据库明文）

## 五、输入校验与输出编码
18. 所有用户输入是否经过白名单校验（长度、类型、格式、范围）
19. 前端输出是否转义，防止 XSS（反射型、存储型）
20. 文件上传是否校验后缀、MIME、文件头，禁止可执行文件
21. 分页/导出是否限制最大条数，防止数据拖库

## 六、依赖与组件安全
22. 所有依赖版本是否真实存在（配合 dependency_checker.py 脚本验证）
23. 依赖是否包含已知高危 CVE（可运行 pip-audit / npm audit / safety）
24. 是否使用了已废弃、不再维护的库

## 七、部署与配置安全
25. 调试模式（DEBUG=True、FastAPI docs 开启）在生产是否关闭
26. 默认账号密码是否已修改，是否存在弱密码（admin/admin、123456）
27. 数据库、Redis、消息队列是否监听在公网 0.0.0.0 且无密码
28. CORS 是否配置为 *（允许任意域），应限制为具体域名
29. 错误返回是否暴露堆栈、SQL 语句、内部路径

## 八、AI 生成代码特有风险（AI-Specific）
30. 是否存在 AI 臆造的接口/函数/库（代码里写了但根本不存在）
31. 是否存在 AI 为「让代码看起来完整」而写的假实现（如 TODO 注释后接空函数）
32. 是否存在 AI 为「方便调试」而留的后门/硬编码测试账号
33. 是否存在 AI 为「兼容旧逻辑」而保留的已知漏洞代码

【输出要求】
1. 按上述清单逐条输出检查结果：通过 / 存在风险 / 未覆盖（说明原因）
2. 存在风险的，按 P0/P1/P2/P3 分级：
   - P0：可直接导致系统沦陷、数据泄露、RCE 的漏洞（硬编码密钥、SQL 注入、未鉴权管理员接口）
   - P1：可导致数据越权、敏感信息泄露、依赖高危漏洞
   - P2：配置不当、弱密码策略、信息泄露但利用门槛高
   - P3：安全加固建议
3. 每个问题给出：漏洞描述、影响范围、复现步骤（如可复现）、修复建议（具体到代码改动）
4. 最后输出《安全扫描问题清单》和《安全扫描通过证明》 checklist

【强制规则】
- 禁止只给「建议加强安全」的空泛结论，必须逐条对照清单给出明确检查结果
- 禁止把「未检查」说成「通过」，未覆盖项必须显式标注原因
- 修复建议必须具体到文件、行号、修改后的代码片段
```

---

## 8.5.2 自动化安全扫描脚本（用户本地执行）

> 以下脚本由用户在本地运行，把结果贴给 AI 辅助分析。Agent 不得代跑。

### 脚本 1：硬编码密钥扫描（Python，跨平台）

```python
#!/usr/bin/env python3
# scripts/security_scan_secrets.py
# 扫描代码中的硬编码密钥、密码、Token

import os
import re
import sys
from pathlib import Path

# 常见密钥模式（正则）
PATTERNS = [
    (r'["\']?(?:api[_-]?key|apikey|api[_-]?secret|secret[_-]?key|access[_-]?key)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']', 'API Key/Secret'),
    (r'["\']?(?:password|passwd|pwd|db[_-]?pass|database[_-]?password)["\']?\s*[:=]\s*["\']([^"\']{4,})["\']', 'Password'),
    (r'["\']?(?:token|auth[_-]?token|access[_-]?token|refresh[_-]?token)["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-\.]{16,})["\']', 'Token'),
    (r'["\']?(?:private[_-]?key|rsa[_-]?private|ssh[_-]?key)["\']?\s*[:=]\s*["\']([^"\']{20,})["\']', 'Private Key'),
    (r'(?:mysql|postgres|mongodb|redis)://[^:]+:[^@]+@', 'Database Connection String'),
    (r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer Token'),
    (r'sk-[a-zA-Z0-9]{48}', 'OpenAI API Key'),
    (r'ghp_[a-zA-Z0-9]{36}', 'GitHub Token'),
    (r'xox[baprs]-[a-zA-Z0-9\-]{10,}', 'Slack Token'),
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', 'Private Key Block'),
]

# 排除目录
EXCLUDE_DIRS = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.next', 'data', 'uploads', 'chroma'}

# 排除文件（二进制、图片、压缩包等）
EXCLUDE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.zip', '.tar', '.gz', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.db', '.sqlite', '.pyc'}

def scan_file(filepath: Path) -> list:
    """扫描单个文件，返回 [(行号, 模式名, 匹配内容, 行内容)]"""
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for lineno, line in enumerate(f, 1):
                for pattern, name in PATTERNS:
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for m in matches:
                        # 排除明显的占位符
                        matched = m.group(0)
                        if any(x in matched.lower() for x in ['example', 'placeholder', 'change-me', 'your-', 'xxx', '...', 'todo', 'test']):
                            continue
                        results.append((lineno, name, matched[:80], line.strip()[:120]))
    except Exception as e:
        pass
    return results

def main(root_dir: str):
    root = Path(root_dir)
    all_results = []
    for filepath in root.rglob('*'):
        if filepath.is_dir():
            continue
        if any(d in filepath.parts for d in EXCLUDE_DIRS):
            continue
        if filepath.suffix.lower() in EXCLUDE_EXTS:
            continue
        results = scan_file(filepath)
        if results:
            all_results.append((filepath.relative_to(root), results))

    if not all_results:
        print("✅ 未发现硬编码密钥/敏感信息")
        return 0

    print(f"❌ 发现 {sum(len(r) for _, r in all_results)} 处疑似敏感信息：\n")
    for filepath, results in all_results:
        print(f"📄 {filepath}")
        for lineno, name, matched, line in results:
            print(f"   行{lineno:4d} | {name:20s} | {matched}")
            print(f"         | {line}")
        print()
    return 1

if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    sys.exit(main(root))
```

### 脚本 2：依赖漏洞扫描（Python + npm audit）

```bash
# scripts/security_scan_deps.sh
#!/bin/bash
# 依赖漏洞扫描：pip-audit + npm audit

echo "=== Python 依赖漏洞扫描 (pip-audit) ==="
if command -v pip-audit &> /dev/null; then
    pip-audit --format=json --output=pip_audit_report.json 2>/dev/null || pip-audit
    echo ""
    echo "报告已保存到 pip_audit_report.json"
else
    echo "pip-audit 未安装，运行: pip install pip-audit"
fi

echo ""
echo "=== Node.js 依赖漏洞扫描 (npm audit) ==="
if [ -f "package.json" ]; then
    npm audit --json > npm_audit_report.json 2>/dev/null || npm audit
    echo ""
    echo "报告已保存到 npm_audit_report.json"
else
    echo "未找到 package.json，跳过 npm audit"
fi

echo ""
echo "=== 依赖版本真实性校验 ==="
python scripts/dependency_checker.py .
```

---

## 8.5.3 人工渗透检查清单（用户执行）

> AI 扫描 + 脚本扫描后，用户必须亲手做以下检查：

| 检查项 | 操作 | 预期结果 |
|-------|------|---------|
| 未授权访问 | 退出登录，直接访问内部页面 URL | 应跳转登录页或返回 401 |
| 水平越权 | 用户 A 登录，把 URL 中的 ID 改成用户 B 的 ID | 应返回 403 或数据为空 |
| 垂直越权 | 普通员工登录，直接访问 /admin、/users 等管理接口 | 应返回 403 |
| 弱密码测试 | 尝试 admin/admin、test/123456 等常见弱密码 | 应全部失败 |
| SQL 注入 | 在搜索框输入 `' OR '1'='1` | 不应返回异常数据，不应报 SQL 错误 |
| XSS | 在输入框输入 `<script>alert(1)</script>` | 页面不应弹窗，应显示转义后文本 |
| 文件上传 | 上传 .php / .jsp / .exe 文件 | 应被拒绝或重命名 |
| 敏感信息 | 查看页面源代码、网络请求返回体 | 不应含密码、内部路径、完整堆栈 |

---

## 放行检查

- [ ] `security_scan_secrets.py` 运行通过，无硬编码密钥
- [ ] `pip-audit` / `npm audit` 无高危漏洞（或高危已修复）
- [ ] AI 安全扫描 Prompt 逐项检查完毕，P0/P1 问题清零
- [ ] 人工渗透检查 8 项全部通过
- [ ] 《安全扫描问题清单》中 P0/P1 问题全部修复并回归
- [ ] 修复后重新运行 `security_scan_secrets.py` 确认无回归
- [ ] 安全扫描报告落盘 `08.5_安全扫描/docs/安全扫描报告.md`
- [ ] 在 `_项目状态.md` 记录安全扫描结论

> ⚠️ **铁律**：安全扫描发现 P0（如硬编码真实密钥、SQL 注入、未鉴权管理员接口）未修复前，**禁止**进入第 9 步最终验收。
