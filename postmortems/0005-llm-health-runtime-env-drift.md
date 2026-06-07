# [0005] LLM 状态变红——长时间运行后 os.environ 漂移

> **首次发现**：2026-05-28
> **最近出现**：2026-05-28
> **状态**：✅ 已修复
> **关键词**：llm, health, os.environ, OPENAI_BASE_URL, dotenv, runtime-drift, snapshot

---

## 症状

对话页右上角 LLM 状态 badge 红色（error），`/api/v1/llm/health` 返回：

```json
{
  "primary": {
    "status": "error",
    "model": "qwen3.6",
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",      ← 应该是 http://localhost:8159/v1
    "latency_ms": 5229,
    "error": "Illegal header value b'Bearer '"   ← api_key 空了
  }
}
```

**重启后端立即恢复**。`backend/.env` 内容并无变动，文件里的 `OPENAI_BASE_URL` / `OPENAI_API_KEY` 完全正确。

---

## 根本原因

后端进程长时间运行（本次 ≈ 7 小时）后，`os.environ` 中的 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 被某条代码路径或第三方库清空 / 弹出。`/api/v1/llm/health` 端点在每次请求时实时读取 `os.environ`：

```python
pri_base_url = (os.environ.get("OPENAI_BASE_URL")
                or os.environ.get("OPENROUTER_BASE_URL", "https://api.openai.com/v1"))
pri_api_key  = (os.environ.get("OPENAI_API_KEY")
                or os.environ.get("OPENROUTER_API_KEY", ""))
```

env 缺失 → `or` 短路到默认值 `https://api.openai.com/v1` + 空 API key → 探测打到公网 OpenAI、Authorization 头变成 `Bearer ` → httpx 抛 `Illegal header value`。

诊断过程中诡异点：
- `ps eww -p <pid>` 仍然显示这两个环境变量存在（macOS 上 `ps eww` 读 KERN_PROCARGS2，在进程后续 `os.environ.pop()` 后并不一定同步刷新）
- 全局 grep `os.environ.pop` / `del os.environ` 在 `backend/app/` 下无命中
- DB `SystemConfig` 表里没有覆盖项
- 重启进程后立即恢复，证明问题在运行时状态而非配置文件

直接元凶难以追溯到具体一行代码（疑似 dotenv 旧版本、某第三方 import side-effect、或并发场景下临时 `patch.dict` 未恢复）。无论谁是凶手，**健康探测**这种关键路径不应该依赖一个会被任意路径修改的全局 `os.environ`。

---

## 排查路径

1. 看到 badge 红，按 0002 经验先比较"探测地址 vs llm_provider.py 实际地址"——本次两者代码层面已经一致
2. `curl /api/v1/llm/health` 看到 `base_url=https://api.openai.com/v1`，确认是 fallback 默认值
3. `grep -E "OPENAI_BASE_URL" backend/.env` 显示 `http://localhost:8159/v1`，配置文件正常
4. `ps eww -p $BACKEND_PID` 显示进程 env 里 `OPENAI_BASE_URL` 也是对的 —— 与代码读到的结果矛盾
5. 怀疑 `set_runtime_default()` 副作用 → 看源码只动 `LLM_MODEL` / `LLM_PROVIDER`，不碰 `OPENAI_*`
6. `grep -rn "os.environ.pop\|del os.environ" backend/app` 无命中
7. 推断为运行时 env 漂移 → 重启后端 → badge 立刻恢复绿

---

## 修复方案

### 1. 启动时快照 LLM gateway 配置

在 `backend/app/main.py` 启动钩子里把已解析好的 LLM gateway 配置存入 `app.state.llm_gateway`，整个进程生命周期内复用这一份快照。`llm_health()` 不再读 `os.environ`，从快照取。

### 2. 健康探测日志带 base_url 摘要

在 `_probe_llm()` 入口打 `logger.info("probe target: base_url=%s api_key_len=%d", base_url, len(api_key or ""))`。即使再次复发，日志一行就能区分"env 被清"和"代码逻辑错"两类问题。

### 3. 重启即刻恢复（紧急 SOP）

把这条作为标准应急动作写入本文：

```bash
# 紧急恢复（badge 红 / 探测打到 api.openai.com）
cd /Users/chenbin/agent && ./start.sh
# 2-5 秒内 badge 应恢复绿，否则按代码 bug 处理（看 _probe_llm 的日志）
```

---

## 防复发机制

- **快照 + 不可变**：启动后 LLM gateway 配置进入只读 dataclass，运行时不允许变更（如需切换 base_url，必须重启或显式调用 setter，并打日志）
- **日志可观测**：每次探测都打 base_url 摘要，下次再红时直接看日志判断走的是哪个分支
- **复盘 #0002 + #0005 联防**：
  - #0002 防"代码读错 env"
  - #0005 防"env 被运行时清空"
  - 两者都依赖『健康探测必须与实际调用走同一份配置』这条原则

---

## 关联文件

- `backend/app/main.py` — 启动时调用 `_snapshot_llm_gateway()` 写入 `app.state.llm_gateway`
- `backend/app/routers/system.py` — `llm_health()` 改为读 `app.state.llm_gateway`；`_probe_llm()` 增加摘要日志
- `backend/app/services/llm_provider.py` — 真实调用路径，作为快照取值的参考基准
- `frontend/src/components/LLMHealthBadge.tsx` — 前端展示（轮询 30s）
- `docs/复盘记录/0002-llm-health-status-wrong-env.md` — 同主题的"代码 bug"分支

---

## 教训

> **关键路径不要依赖可变全局态。** 健康探测、计费、审计这类长期可观测面，必须在启动时把依赖快照下来——`os.environ` 看起来稳定，但任何 import 都有改它的能力，长时间运行的进程必然漂移。
