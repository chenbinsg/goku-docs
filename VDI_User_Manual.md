# VDI 使用手册

> **[已归档 · 2026-05-30]** VDI 批处理模块已从 AIOS 移除（migration 0071）。
> 语音质检能力已迁移至独立服务 **VDS-App + VDS-Router**，请参阅 VDS-App 文档。
> 本文档保留作为历史参考，不再维护。

## 1. 功能说明

VDI（Voice Data Inspection）是 Goku-AIOS 的语音质检批处理能力。业务系统把语音转写数据放到指定目录后，AIOS 会按手动触发或定时触发方式读取文件，执行质检规则，生成统一报告，并可通过邮件发送给业务部门。

当前版本支持 `.xlsx` 文件，报告格式为 Markdown。

## 2. 默认目录

如果没有配置 `VDI_BASE_DIR`，系统默认使用：

```text
${AGENT_WORKSPACE}/vdi
```

默认目录结构如下：

```text
vdi/
  incoming/
    ready/       # 业务系统投递待处理文件
  processing/    # 系统处理中间目录
  processed/     # 成功处理后的源文件归档
  failed/        # 失败文件归档
  reports/       # 质检报告输出目录
```

报告会按日期归档：

```text
reports/YYYY/MM/DD/voice_qc_report_YYYYMMDD_<batch>.md
```

## 3. 输入文件要求

业务系统应将 `.xlsx` 文件写入 `incoming/ready` 目录。建议写入时先使用临时文件名，写完后再原子重命名为 `.xlsx`，避免系统扫描到半写入文件。

系统会自动识别以下字段：

| 字段用途 | 推荐列名 | 其他可识别列名 |
|---|---|---|
| 记录 ID | `record_id` | `record id`、`id`、`序号`、`记录id`、`记录编号` |
| 任务 ID | `task_id` | `task id`、`任务id`、`任务编号` |
| 转写文本 | `transcript` | `text`、`content`、`utterance`、`话术`、`转写`、`语音文本`、`通话内容`、`内容` |
| 坐席 | `agent` | `agent_name`、`坐席`、`员工`、`客服`、`销售` |
| 通话时间 | `call_time` | `time`、`created_at`、`通话时间`、`时间`、`日期` |

其中转写文本列是必需字段。缺少该字段时，任务会失败并移动到 `failed`。

## 4. 环境变量配置

```env
VDI_BASE_DIR=/data/vdi
VDI_INCOMING_DIR=
VDI_PROCESSING_DIR=
VDI_PROCESSED_DIR=
VDI_FAILED_DIR=
VDI_REPORTS_DIR=
VDI_RULES_PATH=/data/vdi/rules/quality_rules_kb.jsonl
VDI_REPORT_FORMATS=md,html,xlsx
VDI_MAX_FILES_PER_RUN=10
VDI_SCHEDULER_ENABLED=false
VDI_SCHEDULER_INTERVAL_MINUTES=15
VDI_PROCESSING_STALE_MINUTES=60
VDI_EMAIL_TO=voice-quality@example.com
VDI_EMAIL_SUBJECT_PREFIX=[VDI]
```

| 配置项 | 说明 |
|---|---|
| `VDI_BASE_DIR` | VDI 根目录。为空时使用 `${AGENT_WORKSPACE}/vdi` |
| `VDI_INCOMING_DIR` | 待处理目录。为空时使用 `${VDI_BASE_DIR}/incoming/ready` |
| `VDI_PROCESSING_DIR` | 处理中目录 |
| `VDI_PROCESSED_DIR` | 成功归档目录 |
| `VDI_FAILED_DIR` | 失败归档目录 |
| `VDI_REPORTS_DIR` | 报告输出目录 |
| `VDI_RULES_PATH` | 规则库 JSONL 路径。为空时优先使用内置 `skills/voice-quality-rules-kb/references/quality_rules_kb.jsonl` |
| `VDI_REPORT_FORMATS` | 报告输出格式，支持 `md`、`html`、`xlsx`，逗号分隔 |
| `VDI_MAX_FILES_PER_RUN` | 每次最多处理文件数 |
| `VDI_SCHEDULER_ENABLED` | 是否启用定时任务 |
| `VDI_SCHEDULER_INTERVAL_MINUTES` | 定时扫描间隔，单位分钟 |
| `VDI_PROCESSING_STALE_MINUTES` | 处理中任务超过该分钟数会被 stale recovery 视为异常 |
| `VDI_EMAIL_TO` | 默认报告收件人，支持逗号、分号或换行分隔 |
| `VDI_EMAIL_SUBJECT_PREFIX` | 邮件标题前缀 |

邮件发送复用系统已有 SMTP 配置，例如：

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=aios@example.com
SMTP_PASS=********
SMTP_FROM=aios@example.com
```

修改环境变量后需要重启 AIOS 后端。

## 5. 手动触发

VDI API 需要登录态或有效 Bearer Token。

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:8106/api/v1/vdi/health
```

```bash
curl -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"max_files": 10}' \
  http://127.0.0.1:8106/api/v1/vdi/run
```

临时指定收件人：

```bash
curl -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"max_files": 5, "email_to": "team@example.com"}' \
  http://127.0.0.1:8106/api/v1/vdi/run
```

## 6. 定时触发

开启定时任务：

```env
VDI_SCHEDULER_ENABLED=true
VDI_SCHEDULER_INTERVAL_MINUTES=15
```

重启后端后，系统会按间隔扫描 `incoming/ready`。定时任务使用 `max_instances=1`，避免同一时间多次并发处理。

## 7. 查询、下载和恢复任务

也可以在前端打开：

```text
/vdi
```

VDI 看板提供任务列表、报告下载、规则健康、目录/SMTP 健康检查、状态分布、风险分布和 30 天趋势。

查询最近任务：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://127.0.0.1:8106/api/v1/vdi/jobs?page=1&size=20"
```

按状态查询：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://127.0.0.1:8106/api/v1/vdi/jobs?status=failed"
```

查询单个任务：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:8106/api/v1/vdi/jobs/<JOB_ID>
```

查询报告索引：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://127.0.0.1:8106/api/v1/vdi/reports?page=1&size=20"
```

查询某个任务可下载的报告格式：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:8106/api/v1/vdi/jobs/<JOB_ID>/reports
```

下载报告：

```bash
curl -L -H "Authorization: Bearer <TOKEN>" \
  -o voice_qc_report.xlsx \
  http://127.0.0.1:8106/api/v1/vdi/jobs/<JOB_ID>/reports/xlsx
```

支持的下载格式包括 `md`、`html`、`xlsx`。

重试失败任务：

```bash
curl -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://127.0.0.1:8106/api/v1/vdi/jobs/<JOB_ID>/retry
```

强制重跑已完成或失败任务：

```bash
curl -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://127.0.0.1:8106/api/v1/vdi/jobs/<JOB_ID>/reprocess
```

恢复卡在处理中的任务：

```bash
curl -X POST \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"stale_minutes": 60}' \
  http://127.0.0.1:8106/api/v1/vdi/recover-stale
```

常见任务状态：

| 状态 | 含义 |
|---|---|
| `discovered` | 已发现文件并创建任务 |
| `claimed` | 任务已被当前进程领取 |
| `validating` | 正在校验文件结构 |
| `analyzing` | 正在执行规则分析 |
| `reporting` | 正在生成报告 |
| `emailing` | 正在发送邮件 |
| `completed` | 已完成 |
| `failed` | 处理失败 |

## 8. 当前质检规则

当前版本从 JSONL 规则库加载启用规则。默认规则库路径：

```text
skills/voice-quality-rules-kb/references/quality_rules_kb.jsonl
```

规则库每行一个 JSON 对象，主要字段包括：

| 字段 | 说明 |
|---|---|
| `id` | 规则唯一 ID |
| `rule_name` | 规则名称 |
| `quality_level` | `正常`、`异常` 或 `致命` |
| `status` | `启用` 的规则才参与质检 |
| `alert` | 是否告警 |
| `trigger_logic` | `满足一个条件` 或 `满足所有条件` |
| `conditions[].keywords` | 每个条件下的关键词数组 |

查看规则健康状态：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  http://127.0.0.1:8106/api/v1/vdi/rules/health
```

查看规则列表：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://127.0.0.1:8106/api/v1/vdi/rules?include_keywords=false"
```

按规则名搜索：

```bash
curl -H "Authorization: Bearer <TOKEN>" \
  "http://127.0.0.1:8106/api/v1/vdi/rules?q=投诉"
```

报告中的证据片段会对手机号、身份证号和长数字串做基础脱敏。

## 9. 幂等和重复文件

系统按文件 SHA-256 哈希做幂等控制。同一文件重复投递时，如果已经完成处理，会被标记为跳过，不会重复生成报告。

如果文件内容变化，即使文件名相同，也会被视为新的输入。

## 10. 排障

| 现象 | 排查方向 |
|---|---|
| API 返回 401 | 检查登录态或 Bearer Token |
| 没有发现文件 | 检查文件是否在 `incoming/ready`，后缀是否为 `.xlsx` |
| 文件进入 `failed` | 查看 `/api/v1/vdi/jobs?status=failed` 中的 `error_message` |
| 没有发邮件 | 检查 `VDI_EMAIL_TO` 和 SMTP 配置 |
| 定时任务没有运行 | 检查 `VDI_SCHEDULER_ENABLED=true`，并确认后端已重启 |
| 报告没有生成 | 检查 `reports` 目录权限和磁盘空间 |

## 11. 上线检查清单

- 已创建 VDI 根目录并授予 AIOS 后端读写权限。
- 业务系统只向 `incoming/ready` 投递完整 `.xlsx` 文件。
- 输入文件包含可识别的转写文本列。
- SMTP 配置已验证。
- `VDI_EMAIL_TO` 已配置为业务部门邮箱。
- 定时任务间隔符合业务时效要求。
- 已用一份测试文件验证完整链路：投递、触发、报告、邮件、归档、重试、重跑。
