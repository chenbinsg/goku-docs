# [0002] LLM 状态显示不准（对话页右上角）

> **首次发现**：2026-05-28  
> **最近出现**：2026-05-28  
> **状态**：✅ 已修复  
> **关键词**：llm, health, OPENAI_BASE_URL, OPENROUTER_BASE_URL, LLMHealthBadge

---

## 症状

对话页右上角 LLM 状态 badge 频繁显示红色（error）或 degraded，
但实际 LLM 调用正常工作。重启后恢复，过一段时间再次变红。

---

## 根本原因

`GET /api/v1/llm/health` 端点读取 `OPENROUTER_BASE_URL` 作为探测地址，
而实际 LLM 调用（`services/llm_provider.py`）使用 `OPENAI_BASE_URL`。

两个 env var 指向不同地址：

| 变量 | 值 | 用途 |
|------|-----|------|
| `OPENAI_BASE_URL` | `http://localhost:8159/v1` | 实际 LLM 网关（Goku Router）|
| `OPENROUTER_BASE_URL` | 未设置 → 默认 `https://api.openai.com/v1` | 健康检查错误地探测这里 |

健康检查打到 `https://api.openai.com/v1`，API key 为空 → 返回 401 → 显示红色。

---

## 修复方案

```python
# backend/app/routers/system.py llm_health()
# 修复前
pri_base_url = os.environ.get("OPENROUTER_BASE_URL", "https://api.openai.com/v1")
pri_api_key  = os.environ.get("OPENROUTER_API_KEY", "")

# 修复后：与 llm_provider.py 保持一致
pri_base_url = (os.environ.get("OPENAI_BASE_URL")
                or os.environ.get("OPENROUTER_BASE_URL", "https://api.openai.com/v1"))
pri_api_key  = (os.environ.get("OPENAI_API_KEY")
                or os.environ.get("OPENROUTER_API_KEY", ""))
# 仅当明确配置了 OPENROUTER_API_KEY 且模型名含 '/' 时，才切换到 OpenRouter
```

---

## 防复发机制

健康检查 env var 解析逻辑现与 `llm_provider.py` 完全一致，
任何新增 LLM provider 时两处必须同步修改。

---

## 关联文件

- `backend/app/routers/system.py` — `llm_health()` 函数
- `backend/app/services/llm_provider.py` — 实际路由逻辑（参考基准）
- `frontend/src/components/LLMHealthBadge.tsx` — 前端展示（轮询 30s）

---

## 教训

> **健康检查探测的地址必须与实际调用路径完全一致；任何"并行"的 env var 解析都会产生幽灵状态。**
