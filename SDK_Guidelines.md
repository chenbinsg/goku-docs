# aios-sdk 使用手册

**版本**: 0.1.0  
**适用平台**: Goku-AIOS v1.7.0+  
**最后更新**: 2026-05-19

---

## 目录

1. [简介](#1-简介)
2. [安装](#2-安装)
3. [快速开始](#3-快速开始)
4. [AgentSession 参数说明](#4-agentsession-参数说明)
5. [核心方法](#5-核心方法)
   - 5.1 [run() — 提交并等待（最简方式）](#51-run--提交并等待最简方式)
   - 5.2 [submit() — 非阻塞提交](#52-submit--非阻塞提交)
   - 5.3 [wait() — 等待任务完成](#53-wait--等待任务完成)
   - 5.4 [status() — 单次轮询](#54-status--单次轮询)
   - 5.5 [stream() — SSE 流式订阅](#55-stream--sse-流式订阅)
6. [TaskResult 说明](#6-taskresult-说明)
7. [错误处理](#7-错误处理)
8. [完整示例](#8-完整示例)
9. [环境变量配置](#9-环境变量配置)
10. [常见问题](#10-常见问题)

---

## 1. 简介

`aios-sdk` 是 Goku-AIOS 开放 API 的官方 Python 客户端。它封装了 REST 调用、轮询逻辑和 SSE 流式订阅，让外部应用**三行代码**即可调用 Agent 能力。

**特性：**
- 零运行时依赖（仅用 Python 标准库）
- 支持阻塞式 `run()`、非阻塞 `submit()/wait()`、流式 `stream()`
- 内置超时控制与进度回调
- SSE 流式支持（可选依赖 `sseclient-py`）
- Python 3.9+

---

## 2. 安装

```bash
# 基础安装（无额外依赖）
pip install aios-sdk

# 含 SSE 流式支持
pip install "aios-sdk[streaming]"
```

从源码安装（开发环境）：

```bash
git clone https://github.com/chenbinsg/goku-core.git
cd Goku-AIOS/sdk
pip install -e ".[streaming]"
```

---

## 3. 快速开始

```python
from aios_sdk import AgentSession

# 创建会话
session = AgentSession(
    base_url="https://your-aios.example.com",
    api_key="goku_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)

# 调用 Agent（阻塞，等待完成）
result = session.run("用中文总结一下今天的市场动态")

if result.ok:
    print(result.result)
else:
    print(f"失败：{result.error}")
```

获取 API Key：**系统管理 → 开放 API Keys → 创建 API Key**。

---

## 4. AgentSession 参数说明

```python
AgentSession(
    base_url,        # str  AIOS 部署地址，如 "https://aios.example.com"
    api_key,         # str  Bearer API Key，以 "goku_" 开头
    agent=None,      # str  默认 Agent slug（可被各方法覆盖）
    timeout=300.0,   # float 等待超时（秒），默认 5 分钟
    poll_interval=2.0,  # float 轮询间隔（秒），默认 2 秒
)
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `base_url` | str | ✅ | AIOS 服务地址（不含末尾斜杠） |
| `api_key` | str | ✅ | 以 `goku_` 开头的 API Key |
| `agent` | str | — | 默认 Agent slug，创建会话时可省略，调用时单独指定 |
| `timeout` | float | — | 全局等待超时秒数（默认 300） |
| `poll_interval` | float | — | 轮询间隔秒数（默认 2） |

---

## 5. 核心方法

### 5.1 `run()` — 提交并等待（最简方式）

```python
result = session.run(
    message,           # str  用户消息 / 任务描述
    agent=None,        # str  指定 Agent slug（覆盖默认值）
    context=None,      # dict 附加上下文（写入 task.context）
    timeout=None,      # float 覆盖会话级超时
    on_progress=None,  # Callable[[TaskResult], None] 进度回调
)
# 返回 TaskResult
```

**示例：**

```python
# 最简调用
result = session.run("生成 Q2 季报摘要")

# 指定 Agent + 进度回调
result = session.run(
    "分析附件中的销售数据",
    agent="analyst",
    timeout=120,
    on_progress=lambda r: print(f"  [{r.status}] 处理中..."),
)
```

### 5.2 `submit()` — 非阻塞提交

```python
task_id = session.submit(
    message,        # str  用户消息
    agent=None,     # str  Agent slug
    context=None,   # dict 附加上下文
)
# 返回 str（task_id）
```

立即返回，不等待任务完成。适合批量提交或后台处理场景。

```python
# 批量提交
ids = [session.submit(f"分析第 {i} 季度数据") for i in range(1, 5)]

# 等待所有完成
results = [session.wait(tid) for tid in ids]
```

### 5.3 `wait()` — 等待任务完成

```python
result = session.wait(
    task_id,           # str 由 submit() 返回的任务 ID
    timeout=None,      # float 覆盖会话级超时
    poll_interval=None, # float 覆盖会话级轮询间隔
    on_progress=None,  # Callable[[TaskResult], None] 进度回调
)
# 返回 TaskResult
# 超时抛出 TimeoutError
```

```python
task_id = session.submit("生成月度报告")

# 做其他事...

result = session.wait(
    task_id,
    timeout=300,
    on_progress=lambda r: print(f"状态：{r.status}"),
)
```

### 5.4 `status()` — 单次轮询

```python
result = session.status(task_id)  # 返回 TaskResult（当前快照）
print(result.status)  # pending / in_progress / completed / failed / cancelled
```

适合自行实现轮询逻辑时使用。

### 5.5 `stream()` — SSE 流式订阅

```python
# 需要先 pip install "aios-sdk[streaming]"
task_id = session.submit("请写一篇关于 AI 的文章")

for event in session.stream(task_id):
    evt_type = event["event"]
    data = event["data"]

    if evt_type == "card_push":
        print(data.get("content", ""), end="", flush=True)
    elif evt_type == "task_completed":
        print("\n✅ 完成")
        break
    elif evt_type == "task_failed":
        print(f"\n❌ 失败：{data.get('error')}")
        break
```

**常见 SSE 事件类型：**

| 事件 | 说明 |
|------|------|
| `card_push` | Agent 输出内容卡片（文本、代码、表格等） |
| `tool_call` | Agent 正在调用工具 |
| `tool_result` | 工具返回结果 |
| `task_completed` | 任务成功完成 |
| `task_failed` | 任务失败 |
| `task_cancelled` | 任务被取消 |

> 未安装 `sseclient-py` 时，SDK 自动回退到内置的行解析器，功能等价，性能略低。

---

## 6. TaskResult 说明

```python
@dataclass
class TaskResult:
    task_id: str          # 任务 ID
    status: TaskStatus    # 当前状态（枚举）
    result: str | None    # 最终输出（completed 时有值）
    error: str | None     # 错误信息（failed 时有值）
    is_zombie: bool       # 是否为 Zombie 重试任务
    raw: dict             # API 原始响应
    ok: bool              # 属性：status == COMPLETED
```

**TaskStatus 枚举：**

| 值 | 含义 |
|----|------|
| `TaskStatus.PENDING` | 等待执行 |
| `TaskStatus.IN_PROGRESS` | 执行中 |
| `TaskStatus.COMPLETED` | 成功完成 |
| `TaskStatus.FAILED` | 执行失败 |
| `TaskStatus.CANCELLED` | 已取消 |

```python
result = session.run("Hello")

# 常用访问方式
if result.ok:
    print(result.result)
else:
    print(str(result))   # "[failed] 错误描述"

# 检查 Zombie 重试
if result.is_zombie:
    print("此任务经过自动重试")
```

---

## 7. 错误处理

```python
from aios_sdk import AgentSession
from aios_sdk.client import AIOSError

session = AgentSession(base_url="...", api_key="goku_...")

try:
    result = session.run("分析数据")
except AIOSError as e:
    # API 返回 HTTP 错误
    print(f"HTTP {e.status_code}: {e.detail}")
    if e.status_code == 401:
        print("API Key 无效或已过期")
    elif e.status_code == 429:
        print("超出 QPS 或月度配额限制")
    elif e.status_code == 404:
        print("Agent 不存在")
except TimeoutError:
    print(f"任务未在 {session.timeout} 秒内完成")
except Exception as e:
    print(f"网络错误：{e}")
```

**常见错误码：**

| HTTP 状态 | 原因 | 处理建议 |
|-----------|------|---------|
| 401 | API Key 无效、已过期或已吊销 | 重新生成 Key |
| 403 | Key 已禁用 | 联系管理员启用 |
| 404 | Agent slug 不存在 | 检查 agent 参数 |
| 429 | 超出 QPS 或月度配额 | 降低频率或联系管理员扩容 |
| 500 | 服务端内部错误 | 查看 AIOS 服务日志 |

---

## 8. 完整示例

### 示例 1：批量分析（非阻塞）

```python
from aios_sdk import AgentSession

session = AgentSession(
    base_url="https://aios.example.com",
    api_key="goku_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    agent="analyst",
    timeout=180,
)

quarters = ["Q1", "Q2", "Q3", "Q4"]
task_ids = {q: session.submit(f"分析 2025 年{q}营收，输出摘要") for q in quarters}

print("已提交所有任务，等待结果...")

for quarter, tid in task_ids.items():
    result = session.wait(tid)
    if result.ok:
        print(f"\n=== {quarter} ===\n{result.result}")
    else:
        print(f"\n=== {quarter} === 失败：{result.error}")
```

### 示例 2：流式输出

```python
from aios_sdk import AgentSession

session = AgentSession(
    base_url="https://aios.example.com",
    api_key="goku_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
)

task_id = session.submit("写一篇 500 字的产品发布公告", agent="writer")
print("开始流式输出：\n")

for event in session.stream(task_id):
    if event["event"] == "card_push":
        content = event["data"].get("content", "")
        print(content, end="", flush=True)
    elif event["event"] in ("task_completed", "task_failed"):
        print(f"\n\n状态：{event['event']}")
        break
```

### 示例 3：进度监控

```python
import time
from aios_sdk import AgentSession

session = AgentSession(base_url="https://aios.example.com", api_key="goku_...")

start = time.time()

result = session.run(
    "请对以下市场数据进行深度分析...",
    agent="researcher",
    on_progress=lambda r: print(f"  [{time.time()-start:.0f}s] 状态：{r.status}"),
)

print(f"\n耗时：{time.time()-start:.1f}s")
print(result.result if result.ok else f"错误：{result.error}")
```

### 示例 4：环境变量配置

```python
import os
from aios_sdk import AgentSession

def get_session(**kwargs) -> AgentSession:
    return AgentSession(
        base_url=os.environ["AIOS_BASE_URL"],
        api_key=os.environ["AIOS_API_KEY"],
        agent=os.environ.get("AIOS_DEFAULT_AGENT"),
        **kwargs,
    )

session = get_session(timeout=120)
result = session.run("你好")
print(result)
```

---

## 9. 环境变量配置

推荐通过环境变量管理敏感信息：

| 变量 | 说明 | 示例 |
|------|------|------|
| `AIOS_BASE_URL` | AIOS 服务地址 | `https://aios.example.com` |
| `AIOS_API_KEY` | API Key | `goku_xxxxxxxx...` |
| `AIOS_DEFAULT_AGENT` | 默认 Agent slug | `analyst` |

`.env` 示例（配合 `python-dotenv` 使用）：

```env
AIOS_BASE_URL=https://aios.example.com
AIOS_API_KEY=goku_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AIOS_DEFAULT_AGENT=analyst
```

```python
from dotenv import load_dotenv
load_dotenv()

import os
from aios_sdk import AgentSession
session = AgentSession(base_url=os.environ["AIOS_BASE_URL"], api_key=os.environ["AIOS_API_KEY"])
```

---

## 10. 常见问题

**Q: API Key 以什么格式开头？**  
A: 所有 Key 以 `goku_` 为前缀，后跟 32 位随机字符，共 37 字符。Key 仅在创建时完整显示一次，请立即复制。

**Q: 没有安装 sseclient-py，stream() 还能用吗？**  
A: 可以。SDK 内置了简化的 SSE 行解析器，无需额外依赖即可使用 `stream()` 方法，功能完全等价。

**Q: 如何指定使用哪个 Agent？**  
A: 两种方式：① 创建 `AgentSession` 时传 `agent="slug"`；② 每次调用 `run()/submit()` 时传 `agent="slug"`（覆盖默认值）。Agent slug 在 AIOS 管理界面「Agent 管理」中查看。

**Q: 任务超时怎么处理？**  
A: `wait()` 和 `run()` 超时后抛出 `TimeoutError`。此时任务仍在 AIOS 后台运行，可用 `session.status(task_id)` 继续查询结果。

**Q: 如何知道任务是否经过 Zombie 重试？**  
A: 检查 `result.is_zombie`。若为 `True`，表示原任务心跳超时后被系统自动重试。

**Q: 支持异步（asyncio）吗？**  
A: v0.1.0 仅支持同步调用。异步支持计划在后续版本中通过 `aiohttp` 实现。

---

*本手册随 aios-sdk 版本更新。最新版请查阅 [GitHub](https://github.com/chenbinsg/goku-core/tree/main/sdk)。*
