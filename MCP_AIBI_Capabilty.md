# MCP_AIBI_Capabilty

> AIBI MCP 能力清单。  
> 这些能力用于支持自然语言数据查询、统计分析、预测、报表生成、报表保存与导出等场景。

| 能力名称 | 描述 |
|---|---|
| `export_csv` | 把一次自然语言查询的结果导出为 CSV 文本（UTF-8 with BOM，Excel 兼容）。需要 `data:export` 权限，`viewer` 角色无法调用。上限 50000 行 / 5 MB；超出限制时应返回错误或提示缩小查询范围。 |
| `forecast_metric` | 基于历史时间序列数据预测企业指标，例如交易金额、交易笔数等未来取值。返回历史段 + 预测段两组数据点，包含 `lower` / `upper` 区间，客户端可绘制趋势图。不支持年度等过粗粒度预测，适合按日、周、月等时间序列分析。 |
| `generate_report` | 把多个自然语言问题编排成一份完整统计报告。每节包含 KPI、表格前 200 行、图表类型建议 `chart_hint` 和模板化文字摘要。最多 10 节。适合一次性产出月报、经营分析、业务复盘等报告。 |
| `get_saved_report` | 按 `report_id` 取回已保存的报表。返回结构化数据和图表建议，包括 KPI、表格行、`chart_hint` 等。ECharts option 已剥离，客户端按需自行渲染。权限：报表所有者本人或具备相应管理权限的用户可访问。 |
| `list_metadata` | 列出指定数据域的所有可查询指标 `metrics` 和维度 `dimensions`，包含中文 / 日文标签和单位信息。适合在新会话开始、字段不确定、或需要发现可用字段时调用。 |
| `query_statistics` | 把自然语言问题转化为结构化统计查询，返回 KPI、原始数据行和图表类型建议。适合“最近 7 天各地区交易额”“本月成功率”“2025 年各行业 GPV”等数据问题。 |
| `save_report` | 把一次自然语言查询执行并保存为可分享的报表。返回 `report_id` 和访问 URL，可通过 `get_saved_report` 取回。需要 `report:create` 权限。报表 `source` 字段标记查询来源和生成上下文。 |

## 建议使用方式

### 1. 查询前先发现元数据

当用户不确定字段、指标或维度时，优先调用：

```text
list_metadata
```

用于确认当前数据域支持哪些指标、维度、标签和单位。

### 2. 单个问题用统计查询

当用户提出单个统计问题时，调用：

```text
query_statistics
```

典型问题：

```text
最近7天各地区交易额
本月成功率
2025年各行业GPV
```

### 3. 趋势预测用预测能力

当用户希望预测未来趋势时，调用：

```text
forecast_metric
```

适合交易金额、交易笔数、成功率等有历史时间序列的数据。

### 4. 多问题汇总用报告生成

当用户提出一组经营分析问题，或要求生成月报、周报、经营分析报告时，调用：

```text
generate_report
```

该能力会把多个问题组织成多节报告，每节包含 KPI、表格、图表建议和文字摘要。

### 5. 需要长期访问时保存报表

当用户需要分享、复用或稍后查看报告时，调用：

```text
save_report
```

之后通过：

```text
get_saved_report
```

按 `report_id` 取回已保存报表。

### 6. 需要离线分析时导出 CSV

当用户需要在 Excel 或其他工具中继续分析数据时，调用：

```text
export_csv
```

注意导出存在行数和文件大小限制。

## 权限说明

| 能力 | 典型权限要求 |
|---|---|
| `export_csv` | `data:export` |
| `save_report` | `report:create` |
| `get_saved_report` | 报表所有者本人或管理权限 |
| `query_statistics` | 数据查询权限 |
| `forecast_metric` | 数据查询 / 分析权限 |
| `generate_report` | 数据查询 / 报告生成权限 |
| `list_metadata` | 元数据查看权限 |

## 输出设计原则

AIBI MCP 能力的输出应尽量保持结构化，便于前端、Agent 和 Workflow 复用。

建议统一包含以下内容：

```yaml
kpi: 核心指标
rows: 表格数据
chart_hint: 图表类型建议
summary: 文字摘要
metadata: 指标、维度、单位、时间范围等上下文
```

其中 `chart_hint` 只提供图表类型建议，不直接绑定具体前端图表库。前端可根据自身技术栈渲染为 ECharts、AntV、Chart.js 或其他图表。

## 典型调用链路

```text
用户自然语言问题
        ↓
list_metadata（可选）
        ↓
query_statistics / forecast_metric / generate_report
        ↓
返回 KPI、表格、图表建议、文字摘要
        ↓
save_report（可选）
        ↓
get_saved_report / export_csv（可选）
```

## 适用场景

- 经营数据查询
- 交易金额 / 交易笔数分析
- 成功率分析
- 地区、行业、商户、PSP、OEM 等维度分析
- 月报 / 周报 / 日报生成
- 趋势预测
- 报表保存与分享
- CSV 导出到 Excel

