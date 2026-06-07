# Test Failure Fix Roadmap

> 创建时间：2026-05-28  
> 背景：全量 `pytest` 跑出 20 个失败（4434 passed / 20 failed，覆盖率 54%）  
> 所有失败均为既存问题，与 v1.9.16.2 的 scheduler 重构无关  
> 目标：**全量跑 0 failed**

---

## 问题分类总览

| # | 分组 | 失败数 | 根本原因 |
|---|------|--------|----------|
| A | `test_encryption_service` | 4 | 全局单例 `_fernet_instance` 被前序测试污染，预期 raise 的测试不再 raise |
| B | `test_tool_registry` | 5 | DLP 服务单例 / 工具注册表 singleton 被前序测试修改，mock patch 失效 |
| C | `test_model_router` + `test_openrouter_provider` | 6 | slash-model 路由返回 `openai` 而非 `openrouter`，实现逻辑与测试预期不符 |
| D | `test_reviewer_agent` | 3 | mock LLM 响应缺少 `.id` 属性；reviewer 代码已更新但测试 mock 未跟进 |
| E | `test_p1_asset_exposure_regression` | 1 | 全量跑时路由/中间件状态被污染，独立跑通过 |
| F | `test_health` | 1 | health endpoint 返回字段与断言不一致，独立跑通过 → 全量跑前序路由修改了状态 |

---

## Task A — 修复 encryption_service 单例污染（优先级：高）

**失败测试：**
- `TestGetFernet::test_raises_if_no_key`
- `TestGetFernet::test_raises_if_invalid_key`
- `TestDecryptSecret::test_wrong_key_raises_decryption_failed`
- `TestDecryptSecret::test_corrupted_ciphertext_raises_decryption_failed`

**根本原因：**  
`backend/app/services/encryption.py` 使用模块级 `_fernet_instance` 缓存 Fernet 对象。  
`test_encryption.py`（字母序在前）在测试中设置了 `GOKU_SECRET_KEY` 环境变量并调用了加密函数，导致 `_fernet_instance` 被初始化并缓存。后续 `test_encryption_service.py` 的测试预期 `GOKU_SECRET_KEY` 未设置时 raise `SecretKeyMissing`，但缓存已有值，所以不 raise。

**修复方案：**  
在 `test_encryption_service.py` 中每个相关 test 前后重置缓存：

```python
# conftest.py 或 test 文件顶部
import pytest
import app.services.encryption as enc_mod

@pytest.fixture(autouse=True)
def reset_fernet_cache():
    """Reset module-level Fernet cache before each test."""
    original = enc_mod._fernet_instance
    enc_mod._fernet_instance = None
    yield
    enc_mod._fernet_instance = original
```

或在 `encryption.py` 中暴露一个 `_reset_cache()` 测试辅助函数。

**文件：**
- `backend/tests/test_encryption_service.py`（添加 fixture）
- `backend/app/services/encryption.py`（可选：暴露 reset 方法）

---

## Task B — 修复 tool_registry 全量跑 mock 污染（优先级：高）

**失败测试：**
- `TestRegistryExecute::test_execute_returns_tool_result`
- `TestRegistryExecute::test_execute_returns_error_dict_on_exception`
- `TestRegistryExecute::test_execute_dlp_process_output_called`
- `TestPermissionCheck::test_permission_granted_proceeds`
- `TestPermissionCheck::test_permission_0_skips_check`

**根本原因：**  
独立跑全通，全量跑失败 → 前序某个测试修改了 DLP 服务单例或工具注册表 singleton 的内部状态（mock patch 未 restore），导致 `execute()` 分支走向不同。

**修复方案：**
1. 在 `test_tool_registry.py` 中为每个 test class 添加 `autouse` fixture 重置注册表和 DLP 状态：
   ```python
   @pytest.fixture(autouse=True)
   def fresh_registry(self):
       from app.agent.tool_registry import ToolRegistry
       registry = ToolRegistry()
       yield registry
   ```
2. 确保所有 `patch` 使用 `with` 语句或 `@patch` 装饰器（有自动 restore），不手动 `start()` 后忘记 `stop()`。
3. 检查是否有测试在模块级修改了 `app.services.dlp` 的全局实例。

**文件：**
- `backend/tests/test_tool_registry.py`

---

## Task C — 修复 slash-model OpenRouter 路由逻辑（优先级：高）

**失败测试：**
- `test_model_router.py::test_openrouter_slash_model_gets_openrouter_provider` 
- `test_model_router.py::test_slash_model_gets_openrouter`
- `test_model_router.py::test_slash_model_openrouter`
- `test_openrouter_provider.py::test_slash_model_routes_to_openrouter`
- `test_openrouter_provider.py::test_catalog_openrouter_model_routes_correctly`
- `test_openrouter_provider.py::test_arbitrary_slash_model_auto_detected`

**根本原因：**  
所有 6 个测试断言：含 `/` 的模型名（如 `anthropic/claude-3-5-sonnet`）应被路由到 `openrouter` provider。  
实际返回 `openai`，说明 slash-model 自动检测逻辑缺失或被某次重构删除。

**排查路径：**
1. 查看 `backend/app/services/model_router.py` 中 provider 选择逻辑
2. 查看 `backend/app/services/llm_provider.py` 中 openrouter provider 匹配条件
3. 确认是 **实现回归**（代码逻辑被删）还是 **测试预期错误**（业务逻辑已改变）

**修复方案（若为实现回归）：**
```python
# model_router.py 或 llm_provider.py
def _detect_provider(model_name: str) -> str:
    if "/" in model_name:          # slash-model → OpenRouter
        return "openrouter"
    ...
```

**文件：**
- `backend/app/services/model_router.py`
- `backend/app/services/llm_provider.py`
- `backend/tests/test_model_router.py`（如测试预期本身有误则修测试）

---

## Task D — 修复 reviewer_agent mock LLM 响应缺 `.id` 属性（优先级：中）

**失败测试：**
- `TestReviewerLLMSuccess::test_valid_json_parsed`
- `TestReviewerLLMSuccess::test_missing_keys_default_to_safe_values`
- `TestReviewerInvalidJSON::test_invalid_json_falls_back_gracefully`

**根本原因：**  
`app/agent/reviewer.py` 的 LLM 调用结果现在会访问 `.id` 属性（如 `response.id` 用于 tracing），但测试 mock 使用 `types.SimpleNamespace` 构建 response 时没有设置 `id` 字段。reviewer 抛出 `AttributeError: 'types.SimpleNamespace' object has no attribute 'id'`，fallback 逻辑返回默认值 `'tool error'` 而非预期值。

**修复方案：**  
在测试 mock 的 response 对象中添加 `id` 字段：

```python
# test_reviewer_agent.py
mock_response = types.SimpleNamespace(
    id="test-response-id",          # ← 添加这行
    choices=[types.SimpleNamespace(
        message=types.SimpleNamespace(content='{"root_cause": "Tool timeout", ...}')
    )]
)
```

**文件：**
- `backend/tests/test_reviewer_agent.py`

---

## Task E — 修复 p1_asset_exposure 全量跑路由状态污染（优先级：中）

**失败测试：**
- `test_workspace_assets_blocks_html_and_allows_svg`

**根本原因：**  
独立跑通过，全量跑失败 → 前序某个测试（可能是 workspace/upload 相关测试）修改了 FastAPI TestClient 的路由挂载状态，导致 workspace assets 端点行为变化。

**排查路径：**
1. 找到全量跑时在 `test_p1_asset_exposure_regression.py` 之前执行的 workspace 相关测试
2. 确认是否有测试修改了 `app.main` 的静态文件挂载路径
3. 用 `--lf` 重现失败后加 `-v --tb=long` 查看完整 traceback

**修复方案：**  
为该测试 class 添加独立的 `TestClient` fixture（不复用全局 app 实例），或在 conftest 中隔离 workspace 路径设置。

**文件：**
- `backend/tests/test_p1_asset_exposure_regression.py`
- `backend/tests/conftest.py`

---

## Task F — 修复 health endpoint 全量跑状态污染（优先级：低）

**失败测试：**
- `test_health::test_health`

**根本原因：**  
`assert 'de...'`（截断）表明 health endpoint 返回了意外的 status 值。独立跑通过，全量跑时前序测试（可能是数据库/模型相关测试）使某个 health 检查组件状态变化。

**排查路径：**
1. 在全量运行中查看该测试完整 traceback（`--tb=long`）
2. 确认是 `status` 字段值（如 `"degraded"` vs `"ok"`）还是 response 结构不同
3. 找到在其之前跑的哪个测试影响了 health 状态

**修复方案：**  
mock health check 的所有外部依赖（DB / LLM provider / Redis），确保 health 测试不受其他测试的副作用影响。

**文件：**
- `backend/tests/test_health.py`

---

## 执行顺序建议

```
明早执行顺序：
1. Task D  →  最简单，只改 mock（5 分钟）
2. Task A  →  加 autouse fixture（10 分钟）
3. Task B  →  加 autouse fixture + 检查 patch restore（15 分钟）
4. Task C  →  先排查是实现回归还是测试错误（20 分钟）
5. Task E  →  需要定位前序污染测试（15 分钟）
6. Task F  →  最后做，依赖 E 的定位经验（10 分钟）
```

预计总耗时：**75 分钟**，完成后覆盖率目标从 54% 提升至 55%+（消除假阴性）。

---

## 验证命令

```bash
# 全量跑，确认 0 failed
cd ~/agent && .venv/bin/pytest

# 只跑这 20 个失败（快速验证）
.venv/bin/pytest \
  backend/tests/test_encryption_service.py \
  backend/tests/test_tool_registry.py \
  backend/tests/test_model_router.py \
  backend/tests/test_openrouter_provider.py \
  backend/tests/test_reviewer_agent.py \
  backend/tests/test_p1_asset_exposure_regression.py \
  backend/tests/test_health.py \
  -v
```
