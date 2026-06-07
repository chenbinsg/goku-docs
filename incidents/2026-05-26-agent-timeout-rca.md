# Incident RCA — Agent 执行引擎 Timeout 根本原因分析

> **日期**：2026-05-26  
> **分析工具**：`backend.log`（897 行）、MySQL `information_schema`、Goku Router `/health`  
> **结论**：**LLM Provider 不稳定（主因）+ 子 Agent 孤儿任务积压（次因）**；  
> 数据库锁、消息队列堆积均排除。

---

## 一、排查方法

```
backend.log (897 lines)
  ├─ grep timeout/error/failover/warning
  ├─ grep 165429 (parallel tool execution 异常耗时)
  ├─ 时间线重建（timestamps gap analysis）
  └─ 统计：timeout×5, error×20, 429×3, spawn_subagent×18

MySQL
  └─ information_schema.innodb_trx WHERE trx_wait_started IS NOT NULL → 0 行
  └─ information_schema.processlist WHERE time>5 AND command!='Sleep' → 0 行

Goku Router (localhost:8159)
  └─ GET /health → circuit_breakers: remote_qwen failures=2, last_failure 18385s ago
```

---

## 二、根本原因

### ✅ 根因 1：LLM Provider 不稳定（**主因**）

**证据**：

| 时间（UTC+8） | 日志 |
|------|------|
| `23:59:50` | `Parallel tool execution: 2 tools in 165429ms (step 4, task 43bb3015)` — 2 个工具并行耗时 **165 秒** |
| `00:14:48` | `Failover: openai/qwen3.6 failed: timed out` |
| `00:24:54` | `Failover: openai/qwen3.6 failed: Client error '400 Bad Request' for url 'https://subapprobatory-lyle-encephalographic.ngrok-free.dev/v1/chat/completions'` |
| `00:27:15` | `Failover: openai/qwen3.6 failed: Server disconnected without sending a response` |

**链路**：

```
AIOS Backend (:8106)
    ↓ OPENAI_BASE_URL=http://localhost:8159/v1
Goku Router (:8159)   ← 本地 LLM 路由代理
    ↓ 转发到上游
ngrok tunnel (subapprobatory-lyle-encephalographic.ngrok-free.dev)
    ↓ 反向代理到
实际 LLM 服务（qwen3.6）
```

**ngrok 隧道是瓶颈**：
- ngrok 免费账户隧道不稳定，会随机返回 `400 Bad Request` 或断开连接
- 当 LLM 响应挂起时，executor 的 ThreadPoolExecutor 等待 LLM 回包，导致整个 step 耗时超过 100 秒
- Goku Router 当前 circuit-breaker 状态：`remote_qwen: state=closed, failure_count=2`（已从失败中恢复）

**影响**：
- executor 等待 LLM → tool 调用挂起 → `spawn_subagent` 的子 Agent 也等 LLM → 链式超时
- 9 个孤儿子任务在 DB 残留为 `pending`（已于上一次清理中取消）

---

### ✅ 根因 2：`spawn_subagent` 超时连锁（**次因，由根因 1 引发**）

**证据**：

| 时间 | 日志 |
|------|------|
| `00:04:35` | `Tool run_e2e_test timed out after 180s` |
| `00:04:41` | `Adaptive replan #1 triggered: tool 'spawn_subagent' failed 2 times consecutively` |
| `00:08:38` | `Tool spawn_subagent timed out after 180s` |
| `00:12:08` | `Adaptive replan #2 triggered: circular call detected: 'spawn_subagent' called 3x with same arguments` |

**分析**：
- `spawn_subagent` 工具调用子执行器，子执行器调用 LLM，LLM 挂起 → 180s 后 tool_registry 超时保护触发
- 自适应 replan 连续触发，Agent 尝试重试但 LLM 仍不稳定，形成循环
- 9 个子任务以 daemon thread 身份创建，父任务失败后成为孤儿

---

### ✅ 根因 3：进程冻结（Mac 睡眠，**独立问题，非任务 timeout 原因**）

**证据**：

| 时间 | 事件 |
|------|------|
| `01:55:52` | 最后一条正常 APScheduler 日志 |
| `01:55:33` | `graph.microsoft.com` DNS 解析失败（网络断开） |
| `03:50:23` | 进程恢复，Outlook Poller 重试（仍无网络） |
| `04:41:01` | APScheduler 报 `missed by 0:01:08` ～ `0:03:08` |

**结论**：01:55 - 04:41 约 2 小时 45 分钟 **Mac 进入睡眠**，Python 进程暂停，APScheduler 计时器停止。唤醒后 APScheduler 报告任务 "missed"，属正常行为，不影响任务执行（APScheduler `misfire_grace_time` 窗口外自动跳过）。

---

### ❌ 排除：数据库锁

```sql
SELECT COUNT(*) FROM information_schema.innodb_trx 
WHERE trx_wait_started IS NOT NULL;
-- → 0 行：无活跃锁等待

SELECT COUNT(*) FROM information_schema.processlist 
WHERE time > 5 AND command != 'Sleep';
-- → 0 行：无慢查询
```

日志中也无 `Deadlock`、`Lock wait timeout exceeded`、`pymysql.err.OperationalError` 等 DB 锁相关错误。

---

### ❌ 排除：消息队列堆积

- AIOS 使用进程内 `threading.Semaphore(20)` + `event_bus`（无外部消息队列）
- 无 Redis、Celery、RabbitMQ 相关错误日志
- 任务队列（DB）当前状态：✓ 活跃任务 = 0（已清理）

---

## 三、附带 Bug：WebSocket `Set changed size during iteration`

**时间**：`23:05:16`  
**日志**：`RuntimeError: Set changed size during iteration` in `broadcast_to_conversation()`

**根因**：`ws.py` 中 `for uid, ws in _conversation_subscribers[conversation_id]:` 在迭代时，另一个协程断开连接并修改了集合。

**修复**（已于本次分析中提交）：

```python
# Before
for uid, ws in _conversation_subscribers[conversation_id]:

# After — snapshot set before iterating
for uid, ws in list(_conversation_subscribers.get(conversation_id, set())):
```

---

## 四、修复措施

| 措施 | 状态 | 说明 |
|------|------|------|
| WebSocket 并发 Bug 修复 | ✅ 已提交 | `ws.py` 迭代前 list() 快照 |
| 孤儿任务清理 | ✅ 已完成 | 9 个 pending 子任务 → cancelled；6 个 zombie 标记清除 |
| `GET /api/v1/agent/health` 端点 | ✅ 已提交 | 5 维度诊断：LLM/任务队列/并发槽/DB/定时任务 |
| `cleanup_stuck_tasks.py` 脚本 | ✅ 已提交 | 独立 DB 级清理工具，绕过 HTTP API |
| `POST /api/v1/tasks/admin/reset-concurrency` | ✅ 已提交 | 信号量在线重置端点 |

---

## 五、建议后续改进

### P0 — 立即执行

1. **更换 ngrok 为稳定端点**  
   ngrok 免费隧道随机返回 400 / 断连。改用固定域名、内网穿透（如 Cloudflare Tunnel）或直接将 qwen 模型部署到本地 Ollama / 公网服务器。

   ```bash
   # 验证当前端点
   curl -s http://localhost:8159/health | jq .circuit_breakers
   ```

2. **设置 LLM_FALLBACK_MODELS**  
   当主模型（qwen3.6）不可用时，自动切换到 OpenAI GPT-4o-mini 或 Anthropic Claude：

   ```dotenv
   LLM_FALLBACK_MODELS=gpt-4o-mini,claude-3-haiku-20240307
   LLM_FALLBACK_PROVIDERS=openai,anthropic
   ```

### P1 — 本周内

3. **spawn_subagent 孤儿任务回收**  
   父任务失败时，级联取消所有子任务。在 `executor.py` 的 finally 块中查找并取消同 parent_task_id 的子任务。

4. **LLM 超时加 per-request timeout**  
   当前 tool timeout = 180s，但 LLM 请求本身无独立 timeout。建议在 `llm_provider.py` 对每次请求设置 `timeout=60s`，让 Goku Router 决定何时切换 provider。

5. **APScheduler `misfire_grace_time` 告警**  
   将 missed job 数接入 `GET /api/v1/agent/health` 的 `background_jobs` 组件（已完成），同时配置 `cs_sla_check` 的通知渠道（当前日志为 `no channel configured`）。

### P2 — 下个迭代

6. **子 Agent 并发配额**  
   `spawn_subagent` 不消耗主信号量，存在潜在无限线程增长风险。建议在 `spawn_subagent.py` 中增加全局子 Agent 并发上限（如 `MAX_SUBAGENT_CONCURRENT=10`）。

---

## 六、监控查询

```bash
# 实时诊断（需 JWT）
curl -s http://localhost:8106/api/v1/agent/health \
  -H "Authorization: Bearer $TOKEN" | jq .

# 快速检查 LLM 路由器健康
curl -s http://localhost:8159/health | jq '.circuit_breakers'

# 孤儿任务检查
python backend/scripts/cleanup_stuck_tasks.py --dry-run --zombies
```
