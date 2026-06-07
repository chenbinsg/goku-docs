# [0007] AIOS 显示 LLM not available — Goku Router 后端进程无守护

> **首次发现**：2026-05-28  
> **状态**：✅ 已修复  
> **关键词**：llm, health, goku-router, port 8159, launchd, process guardian

---

## 症状

对话页显示「LLM not available」，但 AIOS 后端日志正常、`.env` 配置正确、
快照机制（复盘 #0005）也生效——健康探测打到 `http://localhost:8159/v1` 但超时。

---

## 根本原因

Goku Router 后端（端口 8159）进程自然崩溃后没有任何守护机制，
进程消失后无法自动恢复。AIOS 探测目标正确，但目标已不存在。

与 #0002、#0005 的区别：
- #0002 = 健康检查读错 env var（探测地址错）
- #0005 = env var 被运行时清空（探测地址变默认值）
- #0007 = 探测地址正确，但 Router 进程本身不在了

---

## 排查路径

1. Badge 红 → `curl /api/v1/llm/health` 看 base_url — 正确（`http://localhost:8159/v1`）
2. `curl http://localhost:8159/v1/models` — 无响应，确认 Router 挂了
3. `ps aux | grep 8159` — 无进程
4. Goku Router frontend（5159）仍在，backend（8159）已消失

---

## 修复方案

使用 macOS `launchd` 托管 Goku Router 后端，进程崩溃后 10 秒内自动重启，
登录时自动启动。

### 新增文件

| 文件 | 作用 |
|------|------|
| `/Users/chenbin/router/scripts/daemon_backend.sh` | launchd 启动脚本（source .env + exec uvicorn） |
| `~/Library/LaunchAgents/com.chenbin.goku-router.plist` | launchd plist（KeepAlive=true, ThrottleInterval=10s） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `/Users/chenbin/router/start.sh` | backend 改用 `launchctl load` 启动（nohup 作为 fallback） |
| `/Users/chenbin/router/stop.sh` | 停止前先 `launchctl unload`（告知 launchd 不要重启） |

### 关键设计

```
KeepAlive = true        → 崩溃或正常退出后都重启
ThrottleInterval = 10   → 重启间隔 10s，防止崩溃死循环
RunAtLoad = true        → 登录后自动启动
stop.sh 先 unload       → 手动停止时 launchd 不会重拉
```

---

## 紧急恢复（Router 挂了怎么办）

```bash
# 直接重启 Router（launchd 管理）
launchctl stop com.chenbin.goku-router
launchctl start com.chenbin.goku-router

# 或者完整重启
cd /Users/chenbin/router && ./start.sh
```

---

## 防复发机制

- launchd 守护确保 Router 进程任何形式崩溃后 10s 内自动恢复
- 开机自动启动，不再依赖手动 `start.sh`
- 联防链：#0002（env 读错）→ #0005（env 漂移）→ **#0007（进程无守护）**

---

## 教训

> **所有关键依赖服务都应该有守护进程，而不是手动 nohup。**  
> 健康探测的准确性建立在"探测目标存活"的前提上；  
> 进程管理和配置管理是独立的两个问题，都需要覆盖。
