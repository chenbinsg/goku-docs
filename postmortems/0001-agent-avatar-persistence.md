# [0001] Agent 头像持久化

> **首次发现**：2026-05-28  
> **最近出现**：2026-05-28  
> **状态**：✅ 已修复  
> **关键词**：avatar, figure_url, icon, workspace, slug, sync_builtin_packages, Docker

---

## 症状

- 每次执行 `./start.sh` 或 Docker 镜像更新后，agent 卡片头像变回 emoji 占位符
- 部分 agent 头像始终无法显示（图片路径存在但文件找不到）
- 中文命名 agent 的头像尤其容易丢失

---

## 根本原因（共 4 个，相互叠加）

### RC-1：sync 脚本无条件覆盖 figure_url（**最隐蔽，最核心**）

`backend/scripts/sync_builtin_packages.py` 每次启动时执行，把 seed JSON 里的
`figure_url: null` **无条件 UPDATE 到 DB**，把用户通过 UI 上传的头像 URL 覆盖为 null。

```python
# 修复前（危险）
"figure_url": data.get("figure_url"),   # null → 覆盖用户上传的 URL
```

### RC-2：icon 字段被误用为图片路径

部分 seed JSON 和 export 流程把图片路径（如 `/icons/变更审查专员.svg`）写入了 `icon` 字段，
而前端 `AgentList.tsx` 只读 `figure_url` 渲染头像图片，`icon` 字段完全被忽略。

### RC-3：图标文件名使用 slug（含中文），导致文件无法稳定存活

`_persist_figure_to_icons()` 用 `{agent_slug}.{ext}` 命名图标文件：
- slug 允许 CJK 字符（`_slugify_filename` 保留 `一-鿿`）
- 中文文件名在 Docker 镜像构建、git 操作中不稳定
- agent 改名后 slug 变化，旧文件成为孤儿

### RC-4：图标目录存放在容器内文件系统（非 volume）

修复前 icons 存放于 `frontend/public/icons/`，该目录在 Docker 镜像内，不在持久化 volume 中。
每次更新镜像，自定义头像文件全部丢失。

---

## 排查路径

```
用户反馈"头像不见了"
  ↓
检查 workspace/icons/ → 文件存在（32个内置）
  ↓
检查 DB figure_url → 大部分 NULL
  ↓
检查 seed JSON → figure_url: null
  ↓
发现 sync 脚本对所有字段无条件 UPDATE
  → RC-1 确认
  ↓
发现部分 agent icon 字段存 /icons/ 路径
  → RC-2 确认
  ↓
检查文件名：变更审查专员.svg vs change-reviewer.svg
  → RC-3 确认
  ↓
检查 docker-compose.prod.yml volumes → workspace_data 挂载 /tmp/agent_workspace
frontend/public/icons 未挂载
  → RC-4 确认
```

---

## 修复方案

### 修复 RC-1：sync 脚本跳过 null figure_url

```python
# backend/scripts/sync_builtin_packages.py
update_keys = [
    k for k in values
    if k not in {"id", "tenant_id", "user_id"}
    and not (k == "figure_url" and not values.get("figure_url"))
]
```

### 修复 RC-2：前端兼容 icon 字段作为图片来源

```tsx
// frontend/src/pages/agents/AgentList.tsx
src={agent.figure_url || (agent.icon?.startsWith('/') ? agent.icon : undefined)}
```

并在后端保存/更新时自动规范：若 `icon` 字段以 `/` 开头，自动移到 `figure_url`。

### 修复 RC-3：图标文件名改为 UUID

```python
# backend/app/routers/agents.py _persist_figure_to_icons()
# 修复前
target_name = f"{agent_slug}{ext}"          # 依赖 slug，含中文，改名失效

# 修复后
target_name = f"{file_id}{ext}"             # upload UUID，永久稳定
```

导入时同样改为 UUID：
```python
target_name = f"{uuid.uuid4().hex}{ext}"   # 不再依赖 agent name
```

### 修复 RC-4：icons 目录迁移到 workspace volume

```python
# backend/app/routers/agents.py _icons_root()
workspace = os.environ.get("AGENT_WORKSPACE")
if workspace:
    return Path(workspace) / "icons"        # 持久化 volume
return Path(__file__).resolve().parents[3] / "frontend" / "public" / "icons"  # 本地开发 fallback
```

启动时自动 seed 内置图标到 workspace/icons（跳过已存在文件）。

---

## 防复发机制

| 机制 | 描述 |
|------|------|
| sync 脚本保护 | `figure_url` 为 null 时不 UPDATE，保留 DB 现有值 |
| UUID 命名 | 文件名与 agent 名/slug 完全解耦 |
| Workspace volume | Docker 更新不影响已上传文件 |
| 前端双字段兼容 | `figure_url` 优先，`icon` 作为 fallback |
| 后端自动规范 | 保存时自动将 `icon` 中的路径移至 `figure_url` |

---

## 关联文件

- `backend/scripts/sync_builtin_packages.py` — 跳过 null figure_url 覆盖
- `backend/app/routers/agents.py` — `_persist_figure_to_icons`、`_icons_root`、`_write_imported_figure`、import 流程、save/update 规范化
- `backend/app/main.py` — `_resolve_icons_dir`、workspace seed 逻辑、`is_file()` 过滤子目录
- `frontend/src/pages/agents/AgentList.tsx` — 头像渲染兼容 `icon` 字段
- `docker-compose.prod.yml` — `workspace_data` volume（已覆盖 `/tmp/agent_workspace/icons/`）

---

## 教训

> **sync 脚本的每次"全量 UPDATE"都是数据陷阱；用户通过 UI 修改的字段，seed 脚本必须用 `COALESCE` 或条件跳过，绝不能无条件覆盖。**
