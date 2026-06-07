# 0008 · VDI 模块从 AIOS 提取到 VDS-App

**日期**：2026-05-30
**版本**：v1.9.15
**影响范围**：后端 5 个文件删除、3 个文件修改；前端 1 个页面删除、5 个文件修改；1 条数据库迁移；`voice-quality-inspector` Agent 及 `voice-quality-rules-kb` Skill 一并移除

---

## 背景

VDI（Voice Data Inspection）是嵌入 AIOS 内的语音质检批处理模块，功能为：

1. 监听目录中的 `.xlsx` 文件（预转写文本）
2. 对每行通话内容做关键词规则匹配（疑似诈骗、敏感信息采集等）
3. 生成 Markdown / HTML / XLSX 报告，发送邮件

该模块约 1936 行代码，属于与 AIOS 核心能力（AI Agent 对话 / 工具调用 / 多租户）无关的独立批处理逻辑，造成代码边界模糊，且 VDS-App + VDS-Router 已经提供了功能更完整的替代实现（支持真实音频文件 ASR + QC，具备完整工作流、坐席维度统计、计费等）。

---

## 决策

从 AIOS 完整移除 VDI 批处理管道。保留：
- `backend/seeds/agents/voice-quality-inspector.json`：这是一个 AIOS AI Agent，通过 `code_execute` + 规则文件分析用户上传文件，与 VDI 批处理管道无关。
- `skills/voice-quality-rules-kb/`：规则库 JSONL，`voice-quality-inspector` Agent 仍在使用。

---

## 变更清单

### 删除文件
| 文件 | 说明 |
|------|------|
| `backend/app/routers/vdi.py` | VDI REST API（11 个端点） |
| `backend/app/services/vdi/pipeline.py` | 核心处理管道（771 行） |
| `backend/app/services/vdi/rules.py` | 规则加载（275 行） |
| `backend/app/services/vdi/emailer.py` | 邮件发送（44 行） |
| `backend/app/tasks/vdi_watcher.py` | APScheduler 调度器（65 行） |
| `frontend/src/pages/vdi/VDIDashboard.tsx` | 质检看板（406 行） |

### 修改文件
| 文件 | 修改内容 |
|------|---------|
| `backend/app/main.py` | 移除 `vdi` router import + `include_router` + scheduler 启停调用 |
| `backend/app/models.py` | 移除 `VDIJob` ORM class |
| `backend/app/config.py` | 移除 14 个 `VDI_*` 配置项 |
| `backend/app/services/permission.py` | 移除 `vdi.access` 权限定义 |
| `backend/app/agent/executor.py` | 清理注释中的 VDI 示例引用 |
| `frontend/src/App.tsx` | 移除 import 和 Route |
| `frontend/src/components/Layout.tsx` | 移除 `vdi.access` 菜单项 |
| `frontend/src/components/CollapsibleSidebar.tsx` | **同步** 移除 `vdi.access` 菜单项（遵循复盘 #0006） |
| `frontend/src/i18n/locales/{en,zh,ja}.json` | 移除 `layout_vdi_label` |

### 新增迁移
| 文件 | 说明 |
|------|------|
| `backend/alembic/versions/0071_drop_vdi_jobs.py` | 删除 `vdi_jobs` 表及其索引和唯一约束 |

---

## 注意事项

### Layout.tsx / CollapsibleSidebar.tsx 必须同步（复盘 #0006）
删除专项应用菜单项时，两个 sidebar 文件必须同步修改。本次变更已同步处理。

### 迁移包含幂等检查
`0071_drop_vdi_jobs.py` 的 `upgrade()` 先查 `information_schema.tables`，仅在表存在时删除，避免在已迁移环境重跑出错。

### 已有生产数据
如生产数据库中存有 `vdi_jobs` 记录，需在业务确认不再需要后执行 `make migrate`。迁移不可逆（`downgrade` 仅重建空表，不恢复数据）。

---

## 验证方式

```bash
# 后端语法检查
cd backend && python -m py_compile app/main.py app/models.py app/config.py app/services/permission.py

# 确认 VDI 路由已消失
python -c "from app.main import app; routes = [r.path for r in app.routes]; assert not any('vdi' in r for r in routes), 'VDI routes still present'"

# 前端构建
cd frontend && npm run build

# 运行测试
cd backend && pytest
```

---

## voice-quality-inspector Agent 移除

同步移除了 `voice-quality-inspector`（语音质量检测 / VQI Agent）及其配套 Skill：

| 删除项 | 说明 |
|--------|------|
| `backend/seeds/agents/voice-quality-inspector.json` | Agent seed，下次 `make seed-agents` 不会重建 |
| `skills/voice-quality-rules-kb/` | 规则库 Skill（SKILL.md + references/quality_rules_kb.jsonl），仅被该 Agent 使用 |

**⚠️ 数据库清理（需人工执行一次）：**

seed 文件删除只阻止重建，不删除 DB 已有记录。需在部署后执行：

```sql
-- 或通过管理后台 UI 删除
DELETE FROM agents WHERE slug = 'voice-quality-inspector';
```

或通过 API（需 superuser token）：
```bash
# 先查 ID
GET /api/v1/agents?slug=voice-quality-inspector
# 再删除
DELETE /api/v1/agents/{id}
```

## 对 VDS-App 的建议（供 VDS-App Agent 参考）

AIOS VDI 支持直接投递 `.xlsx`（预转写文本），VDS-App 目前只接受音频文件。
建议 VDS-App 补充 `POST /batches/import-xlsx` 端点，读取文本列（`通话内容/content/transcript`）直接创建 `AudioRecord`（跳过 ASR，`status=asr_done`），让上游仍依赖 XLSX 导出的业务系统可以平滑过渡。
