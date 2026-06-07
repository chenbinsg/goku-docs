# StarPay 月度报告自动化 — 详细 Roadmap

**项目**：StarPay 月次運営レポート自動化  
**执行 Agent**：業務報告生成専門家  
**总工期**：6週間  
**开始日**：2026-05-20  
**目标上线**：2026-07-01（6月报告首次自动生成）

---

## 总体时间线

```
Week 1-2  (05/20–06/02)  ████████  Phase 1:   数据验证
Week 2-3  (06/02–06/06)  ████      Phase 1.5: StarPay MCP Server（新增）
Week 3-4  (06/06–06/16)  ████████  Phase 2:   图表模块
Week 5    (06/17–06/23)  ████      Phase 3:   PDF 图表组装
Week 6    (06/24–06/30)  ████      Phase 4:   审核流 & 自动化
07/01     🚀 Go-Live               6月报告首次自动生成
```

**关键风险节点**

| 任务 | 风险 | 对策 |
|------|------|------|
| TASK 1.2 业务线映射 | 字段不清晰可能延期1週 | 提前联系 DBA 确认 |
| TASK 1.5.1 MCP Server 开发 | FastMCP API 版本差异 | 固定版本 `fastmcp==0.9.x` |
| TASK 1.5.2 Goku-AIOS 注册 | MCP 授权配置需运维权限 | 提前申请 MCP 管理员权限 |
| TASK 3.1 PDF模板制作 | 需设计师确认模板样式 | 第一阶段末即发起 |
| TASK 4.2 定时任务 | 需生产环境权限 | 提前申请 |

---

## Phase 1 — 数据验证（2週間）
**2026-05-20 → 2026-06-02**

### TASK 1.1　确认数据库表结构和访问权限
**工期：Day 1–3**

```sql
-- Step 1: 确认可访问的数据库和表
SHOW DATABASES;
USE starpay_prod;
SHOW TABLES;

-- Step 2: 查看主要表结构
DESCRIBE transactions;
DESCRIBE merchants;
DESCRIBE oem_partners;

-- Step 3: 确认连接账号权限
SHOW GRANTS FOR CURRENT_USER();
```

**需确认的关键字段**

| 字段用途 | 预期列名（待确认） | 说明 |
|---------|------------------|------|
| 交易金额 | `amount` / `transaction_amount` | 单位：日元 or 円分？ |
| 交易时间 | `created_at` / `transaction_date` | 时区：JST or UTC？ |
| 交易状态 | `status` | 成功 = 'completed' / 'success'？ |
| 返金 | `type='refund'` or 独立表？ | 确认返金记录结构 |
| PSP 标识 | `psp_code` / `payment_provider` | 枚举值列表 |
| OEM 标识 | `oem_id` / `partner_code` | 与 OEM 主表关联键 |
| 业务线 | `business_line` / `channel` / `contract_id` | 16条业务线的分类键 |
| 加盟店 | `merchant_id` → `merchants.id` | 用于计数 active merchants |

**交付物**
- [ ] `db_schema_map.md` — 实际表名/列名对照表
- [ ] 只读报表账号申请并验证通过
- [ ] 时区处理方案确认（UTC → JST 转换方式）

---

### TASK 1.2　验证 16 个业务线的字段映射
**工期：Day 3–7**

**核心问题：16 条业务线如何从 DB 中区分？**

```sql
-- 方案A：business_line 枚举字段
SELECT DISTINCT business_line FROM transactions LIMIT 50;

-- 方案B：merchant 分类
SELECT m.business_category, COUNT(*)
FROM merchants m GROUP BY m.business_category;

-- 方案C：contract_type + oem_id 组合
SELECT oem_id, contract_type, COUNT(*)
FROM transactions GROUP BY oem_id, contract_type;
```

**16 条业务线映射表**

| # | 业务线名称 | DB 过滤条件（待填入） | 状态 |
|---|-----------|---------------------|------|
| 1 | Cogca | `business_line = ?` | 待确认 |
| 2 | OLC | `business_line = ?` | 待确认 |
| 3 | 微信&支付宝 | `psp_code IN (?, ?)` | 待确认 |
| 4 | 机场① | `merchant_category = 'airport' AND ...` | 待确认 |
| 5 | 机场② | `merchant_category = 'airport' AND ...` | 待确认 |
| 6 | 机场③ | `merchant_category = 'airport' AND ...` | 待确认 |
| 7 | DAISO | `merchant_name LIKE 'DAISO%'` | 待确认 |
| 8 | SMCC next stera | `psp_code = ?` | 待确认 |
| 9 | OENBAM 麻将館 | `business_line = ?` | 待确认 |
| 10 | 吉野家 | `merchant_id IN (...)` | 待确认 |
| 11 | Smooth | `contract_type = ?` | 待确认 |
| 12 | DCM | `oem_id = ?` | 待确认 |
| 13 | 関西エアポート | `merchant_id = ?` | 待确认 |
| 14 | ポイント | `payment_type = 'points'` | 待确认 |
| 15 | Starpay-Biz 酒店 | `business_line = ?` | 待确认 |
| 16 | Stripe 案件 | `psp_code = 'stripe'` | 待确认 |

**交付物**
- [ ] `business_line_mapping.json` — 每条业务线的实际 SQL 过滤条件
- [ ] 确认字段缺失的业务线，制定替代方案

---

### TASK 1.3　用历史数据跑通 SQL 查询，对比手工报告数值
**工期：Day 7–12**

验证月份：**202503（2025年3月）**，与现有手工报告逐项对比。

```sql
-- 【验证1】月度核心 KPI
SELECT
  SUM(amount) / 100000000.0          AS gpv_oku,
  COUNT(*) / 10000.0                 AS txn_man,
  ROUND(
    SUM(CASE WHEN type='refund' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
  )                                   AS refund_pct
FROM transactions
WHERE created_at >= '2025-03-01 00:00:00'
  AND created_at <  '2025-04-01 00:00:00'
  AND status IN ('completed', 'success');

-- 【验证2】PSP 占比
SELECT
  psp_code,
  COUNT(*) / 10000.0                                       AS txn_man,
  SUM(amount) / 100000000.0                                AS gpv_oku,
  ROUND(SUM(amount) * 100.0 / SUM(SUM(amount)) OVER (), 2) AS share_pct
FROM transactions
WHERE created_at >= '2025-03-01'
  AND created_at <  '2025-04-01'
  AND status = 'completed'
GROUP BY psp_code
ORDER BY gpv_oku DESC;

-- 【验证3】单一业务线（以 Cogca 为例）
SELECT
  COUNT(*)                        AS txn_count,
  SUM(amount) / 100000000.0       AS gpv,
  COUNT(DISTINCT merchant_id)     AS active_merchants
FROM transactions
WHERE business_line = 'cogca'
  AND created_at >= '2025-03-01'
  AND created_at <  '2025-04-01'
  AND status = 'completed';
```

**验证对比表（每项误差需 ≤ 1%）**

| 指标 | 手工报告值 | SQL 查询值 | 差异 | 通过？ |
|------|----------|---------|------|--------|
| 月度 GPV（億円） | ___ | ___ | ___ | □ |
| 取引件数（万件） | ___ | ___ | ___ | □ |
| 返金率（%） | ___ | ___ | ___ | □ |
| PSP① 占比 | ___ | ___ | ___ | □ |
| Cogca GPV | ___ | ___ | ___ | □ |
| OEM 活跃数 | ___ | ___ | ___ | □ |

**交付物**
- [ ] `sql_validation_report.md` — 所有指标对比表及差异分析
- [ ] `queries/core_kpi.sql` — 生产就绪的核心查询文件
- [ ] `queries/business_lines.sql` — 16 条业务线查询模板

---

### TASK 1.4　确认日文字体在服务器上的可用性
**工期：Day 10–14**

```bash
# 检查已安装字体
fc-list | grep -i "japanese\|noto\|ipa\|gothic\|mincho"

# 如无日文字体，安装 IPA 字体
sudo apt-get install fonts-ipafont        # Ubuntu/Debian
sudo yum install ipa-gothic-fonts         # CentOS/RHEL

# Python 验证可用字体
python3 -c "
import matplotlib.font_manager as fm
fonts = [f.name for f in fm.fontManager.ttflist]
jp = [f for f in fonts if any(k in f for k in ['IPA','Noto','Gothic','Mincho'])]
print('Available JP fonts:', jp)
"

# 渲染测试
python3 -c "
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'IPAGothic'
fig, ax = plt.subplots()
ax.set_title('テスト 月次レポート 2025年3月')
ax.set_xlabel('取引件数（万件）')
plt.savefig('/tmp/font_test.png', dpi=150)
print('Saved: /tmp/font_test.png')
"
```

**字体优先順位**

1. `IPAGothic` — 推荐，开源，完整日文支持
2. `Noto Sans CJK JP` — 备选，Google 字体
3. `MS Gothic` — 仅 Windows 服务器

**交付物**
- [ ] 服务器字体安装完成并验证
- [ ] `/tmp/font_test.png` 日文标题正常显示截图
- [ ] `config/chart_config.py` — 字体及品牌配色常量文件

---

### Phase 1 完成标准

> ✅ 能用 SQL 精确还原 202503 手工报告所有核心数字（误差 < 1%）  
> ✅ 16 条业务线全部有明确的 DB 过滤条件  
> ✅ 日文字体在服务器正常渲染

---

## Phase 1.5 — StarPay MCP Server（4 天）
**2026-06-02 → 2026-06-06**

> **为什么在这里引入 MCP？**
>
> Phase 1 的 SQL 是开发验证手段（开发者手动跑），不是生产路径。  
> 但从 Phase 2 起，Agent 在运行时需要动态获取补充指标，若直接调用 `aibi_query(raw SQL)`，
> 存在三个问题：LLM 可能生成危险语句、表结构变更会破坏所有历史 Prompt、
> 无法利用 Goku-AIOS 现有 MCP 授权/配额/审计体系。
>
> **解决方案**：把 Phase 1 验证通过的 SQL 封装成 **StarPay MCP Server**，
> 对外只暴露语义化工具（`get_monthly_kpi` / `get_business_line_stats` / …）。
> Agent 永远不接触裸 SQL，MCP Server 内部维护所有查询逻辑。

---

### TASK 1.5.1　开发 StarPay MCP Server
**工期：Day 1–3**

```bash
pip install fastmcp pymysql python-dotenv
```

```python
# mcp_servers/starpay/server.py
"""StarPay 数据查询 MCP Server
封装 Phase 1 验证通过的全部 SQL，对外暴露语义化工具。
LLM 只能调用工具名，无法访问裸 SQL。
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import pymysql
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

mcp = FastMCP(
    name="starpay-data",
    description="StarPay 月度运营数据查询工具集（只读）",
)

# ── DB 连接 ───────────────────────────────────────────────────────────────────
def _conn():
    return pymysql.connect(
        host=os.environ["STARPAY_DB_HOST"],
        port=int(os.environ.get("STARPAY_DB_PORT", 3306)),
        user=os.environ["STARPAY_DB_USER"],
        password=os.environ["STARPAY_DB_PASS"],
        database=os.environ["STARPAY_DB_NAME"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=30,
    )

def _period_bounds(period: str) -> tuple[str, str]:
    """'2026-05' → ('2026-05-01 00:00:00', '2026-06-01 00:00:00') JST"""
    y, m = int(period[:4]), int(period[5:7])
    start = f"{y:04d}-{m:02d}-01 00:00:00"
    if m == 12:
        end = f"{y+1:04d}-01-01 00:00:00"
    else:
        end = f"{y:04d}-{m+1:02d}-01 00:00:00"
    return start, end


# ── Tool 1: 核心 KPI ──────────────────────────────────────────────────────────
@mcp.tool()
def get_monthly_kpi(period: str) -> dict[str, Any]:
    """
    获取指定月度核心 KPI。

    Args:
        period: 月份字符串，格式 'YYYY-MM'（如 '2026-05'）

    Returns:
        {
          "period": "2026-05",
          "gpv_oku": 31.2,        # 億円
          "txn_man": 156.8,       # 万件
          "refund_rate_pct": 0.42,
          "gpv_mom_pct": 3.2,     # MoM %（与上月比）
          "txn_mom_pct": 1.8,
        }
    """
    start, end = _period_bounds(period)
    # 上月用于 MoM 计算
    y, m = int(period[:4]), int(period[5:7])
    prev_m = 12 if m == 1 else m - 1
    prev_y = y - 1 if m == 1 else y
    prev_period = f"{prev_y:04d}-{prev_m:02d}"
    prev_start, prev_end = _period_bounds(prev_period)

    sql_cur = """
        SELECT
          SUM(amount) / 100000000.0  AS gpv_oku,
          COUNT(*) / 10000.0         AS txn_man,
          ROUND(
            SUM(CASE WHEN type='refund' THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 4
          )                          AS refund_rate_pct
        FROM transactions
        WHERE created_at >= %s AND created_at < %s
          AND status IN ('completed', 'success')
    """
    sql_prev = sql_cur  # 同结构，不同时间范围

    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_cur, (start, end))
            cur_row = cur.fetchone()
            cur.execute(sql_prev, (prev_start, prev_end))
            prev_row = cur.fetchone()

    def _mom(cur_val, prev_val):
        if not prev_val or prev_val == 0:
            return None
        return round((cur_val - prev_val) / prev_val * 100, 2)

    return {
        "period":          period,
        "gpv_oku":         round(cur_row["gpv_oku"] or 0, 2),
        "txn_man":         round(cur_row["txn_man"] or 0, 2),
        "refund_rate_pct": round(cur_row["refund_rate_pct"] or 0, 4),
        "gpv_mom_pct":     _mom(cur_row["gpv_oku"], prev_row["gpv_oku"]),
        "txn_mom_pct":     _mom(cur_row["txn_man"], prev_row["txn_man"]),
    }


# ── Tool 2: 业务线统计 ────────────────────────────────────────────────────────
@mcp.tool()
def get_business_line_stats(period: str, line_id: str) -> dict[str, Any]:
    """
    获取单条业务线月度指标。

    Args:
        period:  月份 'YYYY-MM'
        line_id: 业务线标识符，来自 business_line_mapping.json
                 （如 'cogca', 'olc', 'daiso', ...）

    Returns:
        {
          "line_id": "cogca",
          "period": "2026-05",
          "gpv_oku": 2.3,
          "txn_man": 11.2,
          "success_rate_pct": 99.2,
          "refund_rate_pct": 0.31,
          "active_merchants": 142,
          "gpv_mom_pct": 5.1,
        }
    """
    # business_line_mapping.json 在 Phase 1 生成，运行时加载
    import json, pathlib
    mapping_path = pathlib.Path(__file__).parent / "business_line_mapping.json"
    with open(mapping_path) as f:
        mapping: dict = json.load(f)

    if line_id not in mapping:
        raise ValueError(f"Unknown business line: {line_id!r}. "
                         f"Available: {list(mapping)}")

    filter_clause = mapping[line_id]["sql_where"]  # Phase 1 验证通过的条件
    start, end = _period_bounds(period)

    sql = f"""
        SELECT
          COUNT(*)                         AS txn_count,
          SUM(amount) / 100000000.0        AS gpv_oku,
          COUNT(DISTINCT merchant_id)      AS active_merchants,
          ROUND(
            SUM(CASE WHEN status IN ('completed','success') THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 2
          )                                AS success_rate_pct,
          ROUND(
            SUM(CASE WHEN type='refund' THEN 1 ELSE 0 END)
            * 100.0 / COUNT(*), 4
          )                                AS refund_rate_pct
        FROM transactions
        WHERE created_at >= %s AND created_at < %s
          AND ({filter_clause})
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start, end))
            row = cur.fetchone()

    return {
        "line_id":          line_id,
        "period":           period,
        "gpv_oku":          round(row["gpv_oku"] or 0, 3),
        "txn_man":          round((row["txn_count"] or 0) / 10000, 2),
        "success_rate_pct": round(row["success_rate_pct"] or 0, 2),
        "refund_rate_pct":  round(row["refund_rate_pct"] or 0, 4),
        "active_merchants": row["active_merchants"] or 0,
        "gpv_mom_pct":      None,   # 如需 MoM 可追加上月查询
    }


# ── Tool 3: PSP 占比 ──────────────────────────────────────────────────────────
@mcp.tool()
def get_psp_breakdown(period: str) -> list[dict[str, Any]]:
    """
    获取指定月度各 PSP 的交易件数、GPV 及占比。

    Args:
        period: 月份 'YYYY-MM'

    Returns:
        [
          {"psp_code": "visa",  "txn_man": 42.1, "gpv_oku": 12.3, "share_pct": 39.4},
          ...
        ]
    """
    start, end = _period_bounds(period)
    sql = """
        SELECT
          psp_code,
          COUNT(*) / 10000.0                                        AS txn_man,
          SUM(amount) / 100000000.0                                  AS gpv_oku,
          ROUND(SUM(amount) * 100.0 / SUM(SUM(amount)) OVER (), 2)  AS share_pct
        FROM transactions
        WHERE created_at >= %s AND created_at < %s
          AND status IN ('completed', 'success')
        GROUP BY psp_code
        ORDER BY gpv_oku DESC
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start, end))
            rows = cur.fetchall()

    return [
        {
            "psp_code":  r["psp_code"],
            "txn_man":   round(r["txn_man"] or 0, 2),
            "gpv_oku":   round(r["gpv_oku"] or 0, 3),
            "share_pct": round(r["share_pct"] or 0, 2),
        }
        for r in rows
    ]


# ── Tool 4: OEM 排名 ──────────────────────────────────────────────────────────
@mcp.tool()
def get_oem_ranking(period: str, top_n: int = 15) -> list[dict[str, Any]]:
    """
    获取指定月度 OEM 活跃度排名（按 GPV 降序）。

    Args:
        period: 月份 'YYYY-MM'
        top_n:  返回前 N 条，默认 15

    Returns:
        [
          {"oem_id": "oem_001", "oem_name": "XXX", "gpv_oku": 8.1,
           "txn_man": 40.2, "active_merchants": 312, "rank": 1},
          ...
        ]
    """
    start, end = _period_bounds(period)
    sql = """
        SELECT
          t.oem_id,
          o.oem_name,
          SUM(t.amount) / 100000000.0   AS gpv_oku,
          COUNT(*) / 10000.0            AS txn_man,
          COUNT(DISTINCT t.merchant_id) AS active_merchants
        FROM transactions t
        LEFT JOIN oem_partners o ON t.oem_id = o.id
        WHERE t.created_at >= %s AND t.created_at < %s
          AND t.status IN ('completed', 'success')
        GROUP BY t.oem_id, o.oem_name
        ORDER BY gpv_oku DESC
        LIMIT %s
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start, end, top_n))
            rows = cur.fetchall()

    return [
        {
            "rank":             i + 1,
            "oem_id":           r["oem_id"],
            "oem_name":         r["oem_name"] or r["oem_id"],
            "gpv_oku":          round(r["gpv_oku"] or 0, 3),
            "txn_man":          round(r["txn_man"] or 0, 2),
            "active_merchants": r["active_merchants"] or 0,
        }
        for i, r in enumerate(rows)
    ]


# ── Tool 5: 日次 GPV 时序（供图表用）────────────────────────────────────────
@mcp.tool()
def get_daily_gpv(period: str) -> list[dict[str, Any]]:
    """
    获取指定月每天的 GPV，用于日次趋势图。

    Args:
        period: 月份 'YYYY-MM'

    Returns:
        [{"date": "2026-05-01", "gpv_oku": 1.02}, ...]  # 按日升序
    """
    start, end = _period_bounds(period)
    sql = """
        SELECT
          DATE(created_at)             AS txn_date,
          SUM(amount) / 100000000.0    AS gpv_oku
        FROM transactions
        WHERE created_at >= %s AND created_at < %s
          AND status IN ('completed', 'success')
        GROUP BY DATE(created_at)
        ORDER BY txn_date
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (start, end))
            rows = cur.fetchall()

    return [
        {"date": str(r["txn_date"]), "gpv_oku": round(r["gpv_oku"] or 0, 4)}
        for r in rows
    ]


# ── Tool 6: 36 个月 GPV 历史（供趋势图）────────────────────────────────────
@mcp.tool()
def get_monthly_gpv_history(end_period: str, months: int = 36) -> list[dict[str, Any]]:
    """
    获取截至指定月的近 N 个月 GPV + 件数，用于 36 月趋势图。

    Args:
        end_period: 最新月份 'YYYY-MM'
        months:     取多少个月，默认 36

    Returns:
        [{"period": "2023-06", "gpv_oku": 18.4, "txn_man": 92.1}, ...]
    """
    sql = """
        SELECT
          DATE_FORMAT(created_at, '%%Y-%%m')  AS period,
          SUM(amount) / 100000000.0            AS gpv_oku,
          COUNT(*) / 10000.0                   AS txn_man
        FROM transactions
        WHERE status IN ('completed', 'success')
          AND DATE_FORMAT(created_at, '%%Y-%%m') <= %s
        GROUP BY period
        ORDER BY period DESC
        LIMIT %s
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (end_period, months))
            rows = cur.fetchall()

    return [
        {
            "period":  r["period"],
            "gpv_oku": round(r["gpv_oku"] or 0, 2),
            "txn_man": round(r["txn_man"] or 0, 2),
        }
        for r in reversed(rows)  # 升序返回
    ]


if __name__ == "__main__":
    mcp.run()
```

**`business_line_mapping.json` 格式（Phase 1 产出，运行时加载）**

```json
{
  "cogca":        { "name": "Cogca",            "sql_where": "business_line = 'cogca'" },
  "olc":          { "name": "OLC",              "sql_where": "business_line = 'olc'" },
  "wechat_alipay":{ "name": "微信&支付宝",      "sql_where": "psp_code IN ('wechat','alipay')" },
  "airport1":     { "name": "机场①",            "sql_where": "merchant_category='airport' AND terminal_id=1" },
  "daiso":        { "name": "DAISO",            "sql_where": "merchant_name LIKE 'DAISO%'" },
  "stripe":       { "name": "Stripe 案件",      "sql_where": "psp_code = 'stripe'" }
}
```

> ⚠️ 实际值在 Phase 1 TASK 1.2 完成后填入，此处为示意。

**交付物**
- [ ] `mcp_servers/starpay/server.py` — 6 个工具全部实现并通过单元测试
- [ ] `mcp_servers/starpay/business_line_mapping.json` — 16 条业务线映射完整填入
- [ ] `mcp_servers/starpay/requirements.txt` — 固定 `fastmcp==0.9.x`
- [ ] `pytest mcp_servers/starpay/tests/` 全绿（mock DB）

---

### TASK 1.5.2　在 Goku-AIOS 注册 MCP Server 并配置授权
**工期：Day 3–4**

在 Goku-AIOS 管理后台操作：

```
1. 进入【MCP 服务器管理】→【新建 MCP Server】
   名称：starpay-data
   启动命令：python mcp_servers/starpay/server.py
   传输方式：stdio

2. 进入【能力授权管理】→ 为以下 Agent 开放全部 6 个工具权限：
   - business-report-expert（月报生成，全量权限）
   - 其他 Agent 默认拒绝（DefaultDeny）

3. 配置外部连接（MCP External Connections）：
   类型：database
   连接参数（非敏感）：host, port, database
   密钥（加密存储）：user, password

4. 在 MCP 能力黑名单中添加保护：
   禁止任何工具执行 DELETE / DROP / UPDATE / INSERT
   （在 server.py 中以 SQL 只读账号保证，双重防护）
```

**验证步骤**

```bash
# 在 Goku-AIOS 对话框中发送
调用 starpay-data 工具 get_monthly_kpi，查询 2025-03 的核心 KPI
```

预期输出：
```json
{
  "period": "2025-03",
  "gpv_oku": 28.5,
  "txn_man": 142.3,
  "refund_rate_pct": 0.42,
  "gpv_mom_pct": 3.2,
  "txn_mom_pct": 1.8
}
```

**与 Phase 1.3 验证值对比，误差需 < 1%。**

**交付物**
- [ ] Goku-AIOS MCP Server 注册完成（状态：Running）
- [ ] `business-report-expert` 授权配置截图
- [ ] get_monthly_kpi(2025-03) 输出与 Phase 1.3 手工报告数值一致截图

---

### TASK 1.5.3　所有 6 个工具端到端验证
**工期：Day 4**

```python
# tests/e2e/test_starpay_mcp.py
"""通过 Goku-AIOS Agent 调用 MCP 工具，验证所有工具均可正常返回数据"""
import pytest

TEST_PERIOD = "2025-03"

def test_get_monthly_kpi(agent_client):
    result = agent_client.call_mcp("starpay-data", "get_monthly_kpi",
                                    {"period": TEST_PERIOD})
    assert result["gpv_oku"] > 0
    assert result["txn_man"] > 0
    assert 0 <= result["refund_rate_pct"] <= 100

def test_get_business_line_stats(agent_client):
    result = agent_client.call_mcp("starpay-data", "get_business_line_stats",
                                    {"period": TEST_PERIOD, "line_id": "cogca"})
    assert result["gpv_oku"] > 0
    assert result["active_merchants"] > 0

def test_get_psp_breakdown(agent_client):
    results = agent_client.call_mcp("starpay-data", "get_psp_breakdown",
                                     {"period": TEST_PERIOD})
    assert len(results) > 0
    assert abs(sum(r["share_pct"] for r in results) - 100) < 0.5

def test_get_oem_ranking(agent_client):
    results = agent_client.call_mcp("starpay-data", "get_oem_ranking",
                                     {"period": TEST_PERIOD, "top_n": 10})
    assert len(results) <= 10
    assert results[0]["rank"] == 1

def test_get_daily_gpv(agent_client):
    results = agent_client.call_mcp("starpay-data", "get_daily_gpv",
                                     {"period": TEST_PERIOD})
    assert len(results) >= 28  # 至少 28 天

def test_get_monthly_gpv_history(agent_client):
    results = agent_client.call_mcp("starpay-data", "get_monthly_gpv_history",
                                     {"end_period": TEST_PERIOD, "months": 12})
    assert len(results) <= 12
```

**交付物**
- [ ] 6 个工具全部通过 e2e 测试
- [ ] MCP Server 调用日志可在 Goku-AIOS Audit Log 中查到

---

### Phase 1.5 完成标准

> ✅ StarPay MCP Server 在 Goku-AIOS 中状态为 Running  
> ✅ 6 个工具全部通过端到端测试，数值与 Phase 1 验证结果误差 < 1%  
> ✅ `business-report-expert` 授权配置完成，其余 Agent 默认拒绝  
> ✅ Agent 对话中可通过工具名调用，**无法**直接执行 SQL

---

## Phase 2 — 图表模块（2週間）
**2026-06-06 → 2026-06-16**

### TASK 2.1　实现全部图表类型
**工期：Day 1–8**

```bash
pip install matplotlib pandas numpy scipy
```

#### 图表类型① 折线图（日次 GPV 趋势）

```python
# charts/line_daily.py
def make_daily_trend(df: pd.DataFrame, month: str, output_path: str):
    """
    Input:  df columns: ['date', 'gpv']  (date=YYYY-MM-DD, gpv=億円)
    Output: PNG 1200x400px
    """
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(df['date'], df['gpv'], color='#0066CC', linewidth=2.5,
            marker='o', markersize=4)
    ax.fill_between(df['date'], df['gpv'], alpha=0.1, color='#0066CC')
    ax.set_title(f'{month} 日次GPV推移', fontsize=14, fontproperties=JP_FONT)
    ax.set_ylabel('GPV（億円）', fontproperties=JP_FONT)
    ax.tick_params(axis='x', rotation=45)
    ax.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

#### 图表类型② 36ヶ月柱状 + 折线复合图

```python
# charts/bar_36m.py
def make_36m_trend(df: pd.DataFrame, output_path: str):
    """
    Input:  df columns: ['month', 'gpv', 'txn_count']
    Output: 主轴=GPV柱状，副轴=件数折线
    """
    fig, ax1 = plt.subplots(figsize=(14, 5))
    ax2 = ax1.twinx()
    colors = ['#FF6600' if m == df['month'].iloc[-1] else '#0066CC'
              for m in df['month']]
    ax1.bar(df['month'], df['gpv'], color=colors, alpha=0.8, width=0.6)
    ax2.plot(df['month'], df['txn_count'], color='#999999',
             linewidth=1.5, linestyle='--', marker='s', markersize=3)
    ax1.set_ylabel('GPV（億円）', fontproperties=JP_FONT)
    ax2.set_ylabel('取引件数（万件）', fontproperties=JP_FONT)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

#### 图表类型③ 饼图（支付类型占比）

```python
# charts/pie_share.py
BRAND_COLORS = ['#0066CC','#FF6600','#33AADD','#FFAA33',
                '#006699','#CC4400','#66BBEE','#FFCC66']

def make_pie(labels, values, title, output_path, colors=None):
    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, _, autotexts = ax.pie(
        values, labels=None, autopct='%1.1f%%',
        colors=colors or BRAND_COLORS[:len(values)],
        startangle=90, pctdistance=0.8,
        wedgeprops={'linewidth': 1, 'edgecolor': 'white'}
    )
    ax.legend(wedges, labels, loc='lower center',
              ncol=2, bbox_to_anchor=(0.5, -0.15), prop=JP_FONT)
    ax.set_title(title, fontproperties=JP_FONT, fontsize=13)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

#### 图表类型④ 带状预测图（Forecast Band）

```python
# charts/forecast_band.py
from scipy import stats

def make_forecast(df_hist: pd.DataFrame, n_months: int, output_path: str):
    """
    Input:  df_hist columns: ['month_idx', 'gpv']
    Output: 历史实绩 + 预测区间（80% & 95%）
    """
    x = df_hist['month_idx'].values
    y = df_hist['gpv'].values
    slope, intercept, _, _, se = stats.linregress(x, y)

    future_x  = np.arange(x[-1] + 1, x[-1] + 1 + n_months)
    pred_y    = slope * future_x + intercept
    margin_80 = 1.282 * se * np.sqrt(1 + 1 / len(x))
    margin_95 = 1.960 * se * np.sqrt(1 + 1 / len(x))

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(x, y, color='#0066CC', linewidth=2, label='実績')
    ax.plot(future_x, pred_y, color='#FF6600', linewidth=2,
            linestyle='--', label='予測')
    ax.fill_between(future_x, pred_y - margin_80, pred_y + margin_80,
                    alpha=0.25, color='#FF6600', label='80%区間')
    ax.fill_between(future_x, pred_y - margin_95, pred_y + margin_95,
                    alpha=0.12, color='#FF6600', label='95%区間')
    ax.legend(prop=JP_FONT)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

#### 图表类型⑤ 业务线 MoM 对比横向柱状图

```python
# charts/bar_mom.py
def make_mom_bar(current, previous, metric_name, output_path):
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.barh(['先月', '今月'], [previous, current],
            color=['#CCCCCC', '#0066CC'])
    delta_pct = (current - previous) / previous * 100 if previous else 0
    color = '#FF6600' if delta_pct >= 0 else '#CC0000'
    ax.text(max(current, previous) * 1.02, 1,
            f'{delta_pct:+.1f}%', va='center', color=color,
            fontproperties=JP_FONT, fontsize=12, fontweight='bold')
    ax.set_xlabel(metric_name, fontproperties=JP_FONT)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

#### 图表类型⑥ OEM 活跃度排名（横向条形图）

```python
# charts/bar_ranking.py
def make_ranking(df: pd.DataFrame, metric: str, title: str, output_path: str):
    df_sorted = df.sort_values(metric, ascending=True).tail(15)
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(df_sorted['oem_name'], df_sorted[metric],
                   color='#0066CC')
    bars[-1].set_color('#FF6600')   # 最高値をハイライト
    ax.set_title(title, fontproperties=JP_FONT)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
```

**交付物**
- [ ] `charts/` 模块目录，6 个图表函数全部实现
- [ ] 每个函数有单元测试（mock 数据验证输出文件存在且 > 10 KB）

---

### TASK 2.2　建立 StarPay 品牌配色规范
**工期：Day 1–2（与 TASK 2.1 并行）**

```python
# config/brand.py

BRAND = {
    # 主色系
    'primary':      '#0066CC',   # 深蓝 — GPV 主数据
    'accent':       '#FF6600',   # 橙色 — 当月 / 强调

    # 辅色系
    'blue_light':   '#33AADD',   # 浅蓝 — 辅助线
    'orange_light': '#FFAA33',   # 浅橙 — 预测区间
    'gray':         '#999999',   # 灰色 — 件数副轴
    'gray_light':   '#CCCCCC',   # 浅灰 — 历史对比

    # PSP 固定配色
    'psp_colors': {
        'visa':       '#1A1F71',
        'mastercard': '#EB001B',
        'jcb':        '#003087',
        'amex':       '#007BC1',
        'wechat':     '#07C160',
        'alipay':     '#1677FF',
        'other':      '#AAAAAA',
    },

    # 字体
    'font_jp':   'IPAGothic',
    'font_en':   'Arial',
    'font_size': {'title': 14, 'label': 11, 'tick': 9},

    # 图表尺寸规范（对应 PPT 占位符）
    'size': {
        'full_width': (14, 5),   # 横幅趋势图
        'half_width': (7,  5),   # 半幅饼图
        'small':      (5,  3),   # MoM 对比小图
        'ranking':    (10, 6),   # 排名图
    },
}
```

**交付物**
- [ ] `config/brand.py` 最终版
- [ ] 品牌色板 PNG 文档（供人工核对）

---

### TASK 2.3　Agent 测试：给定数据 → 输出图片，人工审核图表质量
**工期：Day 9–14**

在 Goku-AIOS 对话框中发送测试指令（**使用 MCP 工具取数，不再手动传入数据**）：

```
请用 starpay-data MCP 工具获取 2025-03 的日次 GPV 数据，
生成日次趋势图并保存到工作区，输出文件：trend_test_202503.png
```

Agent 预期调用链：
```
get_daily_gpv(period="2025-03")
  → 返回 31 天日次数据
  → make_daily_trend(df, "2025-03", "trend_test_202503.png")
```

**人工审核清单**

| 图表 | 检查项 | Pass 标准 |
|------|--------|----------|
| 折线图 | 日文标题渲染 | 无方块字 / 乱码 |
| 折线图 | 品牌色 | #0066CC 蓝色 |
| 饼图 | 百分比标注 | 合计 = 100% |
| 36月柱状 | 最新月高亮 | 当月 = 橙色 |
| 预测图 | 置信区间带 | 两层阴影可见 |
| MoM 对比 | 正负色区分 | 正 = 橙色，负 = 红色 |

**交付物**
- [ ] `test_charts/` — 6 张测试图片
- [ ] 人工审核通过记录（截图存档）

---

### Phase 2 完成标准

> ✅ 6 种图表全部能从 mock 数据生成，日文正常显示  
> ✅ 品牌配色规范文件确立  
> ✅ 人工审核通过，图表质量达到手工报告水准

---

## Phase 3 — PDF 图表组装（1週間）
**2026-06-17 → 2026-06-23**

### TASK 3.1　确认 PDF 报告样式规范
**工期：Day 1–3**

与 `business_report` 工具对齐，确认各模块 PDF 页面的布局、字体和图表嵌入方式：

```
# Slide 1: 封面
txt_report_month          "2025年3月度"
txt_generated_date        "2025-04-01 生成"

# Slide 2: 核心 KPI
txt_gpv_value             "28.5"
txt_gpv_unit              "億円"
txt_gpv_mom               "+3.2%"
txt_txn_value             "142.3"
txt_txn_unit              "万件"
txt_txn_mom               "+1.8%"
txt_refund_rate           "0.42%"
img_trend_mini            右侧小趋势图

# Slide 4–6: 趋势分析
img_daily_trend           日次折线图
img_36m_trend             36月柱状图
img_refund_trend          返金率趋势图

# Slide 7: 支付类型
img_pie_cpm_mpm           CPM/MPM 饼图
img_pie_psp               PSP 饼图
txt_cpm_pct / txt_mpm_pct / txt_psp_pct

# Slide 8–23: 业务线（每页相同结构）
txt_biz_name              "Cogca"
txt_biz_gpv               "2.3"
txt_biz_gpv_mom           "+5.1%"
txt_biz_txn               "11.2"
txt_biz_success_rate      "99.2%"
txt_biz_refund_rate       "0.31%"
txt_biz_merchants         "142"
img_biz_trend             趋势图
img_biz_mom               MoM 对比图

# Slide 32–35: 预测
img_forecast_next_month   下月预测图
img_forecast_annual       全年预测图
txt_forecast_low          "26.8"
txt_forecast_mid          "29.1"
txt_forecast_high         "31.4"
```

**交付物**
- [ ] PDF 样式规范确认（与手工报告比对）
- [ ] `docs/pdf_layout_spec.md` — 各页布局说明文档

---

### TASK 3.2　验证 business_report 工具输出
**工期：Day 2–5**

```python
# 调用内置 business_report 工具生成 PDF
# 工具已内置 reportlab 渲染，无需额外开发

TEMPLATE_PATH = 'template/starpay_monthly_template.pptx'

BIZ_LINES = [
    'cogca', 'olc', 'wechat_alipay', 'airport1', 'airport2', 'airport3',
    'daiso', 'smcc', 'oenbam', 'yoshinoya', 'smooth', 'dcm',
    'kansai_ap', 'points', 'starpay_biz', 'stripe',
]

def _set_text(slide, name: str, text: str):
    for shape in slide.shapes:
        if shape.name == name and shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.text = text
                    return
            shape.text_frame.paragraphs[0].text = text
            return

def _set_image(slide, name: str, img_path: str):
    for shape in slide.shapes:
        if shape.name == name:
            left, top, width, height = (shape.left, shape.top,
                                        shape.width, shape.height)
            shape._element.getparent().remove(shape._element)
            slide.shapes.add_picture(img_path, left, top, width, height)
            return

def build_monthly_report(data: dict, chart_dir: str, output_path: str) -> str:
    prs = Presentation(TEMPLATE_PATH)
    s = prs.slides

    # Slide 1: Cover
    _set_text(s[0], 'txt_report_month',
              f"{data['year']}年{data['month']}月度")
    _set_text(s[0], 'txt_generated_date', data['generated_date'])

    # Slide 2: Core KPI
    kpi = data['kpi']
    _set_text(s[1], 'txt_gpv_value',    f"{kpi['gpv']:.1f}")
    _set_text(s[1], 'txt_gpv_mom',      f"{kpi['gpv_mom']:+.1f}%")
    _set_text(s[1], 'txt_txn_value',    f"{kpi['txn']:.1f}")
    _set_text(s[1], 'txt_txn_mom',      f"{kpi['txn_mom']:+.1f}%")
    _set_text(s[1], 'txt_refund_rate',  f"{kpi['refund_rate']:.2f}%")

    # Slides 4–6: Trends
    _set_image(s[3], 'img_daily_trend',   f"{chart_dir}/daily_trend.png")
    _set_image(s[4], 'img_36m_trend',     f"{chart_dir}/36m_trend.png")
    _set_image(s[5], 'img_refund_trend',  f"{chart_dir}/refund_trend.png")

    # Slides 8–23: 16 business lines
    for i, key in enumerate(BIZ_LINES):
        sl  = s[7 + i]
        biz = data['business_lines'][key]
        _set_text(sl, 'txt_biz_gpv',          f"{biz['gpv']:.2f}")
        _set_text(sl, 'txt_biz_gpv_mom',       f"{biz['gpv_mom']:+.1f}%")
        _set_text(sl, 'txt_biz_txn',           f"{biz['txn']:.1f}")
        _set_text(sl, 'txt_biz_success_rate',  f"{biz['success_rate']:.1f}%")
        _set_text(sl, 'txt_biz_refund_rate',   f"{biz['refund_rate']:.3f}%")
        _set_text(sl, 'txt_biz_merchants',     str(biz['active_merchants']))
        _set_image(sl, 'img_biz_trend', f"{chart_dir}/biz_{key}_trend.png")
        _set_image(sl, 'img_biz_mom',   f"{chart_dir}/biz_{key}_mom.png")

    # Slides 32–35: Forecasting
    fc = data['forecast']
    _set_image(s[31], 'img_forecast_next_month',
               f"{chart_dir}/forecast_next.png")
    _set_text(s[31], 'txt_forecast_low',  f"{fc['next']['low']:.1f}")
    _set_text(s[31], 'txt_forecast_mid',  f"{fc['next']['mid']:.1f}")
    _set_text(s[31], 'txt_forecast_high', f"{fc['next']['high']:.1f}")

    prs.save(output_path)
    return output_path
```

**交付物**
- [ ] 验证 PDF 包含全部报告模块
- [ ] 确认 reportlab 日文字体正常渲染

---

### TASK 3.3　完整跑通一次历史月份（202503）并对比手工版本
**工期：Day 5–7**

在 Goku-AIOS 对话框发送：

```
生成202503（2025年3月）StarPay月次レポートのテスト版を作成してください。
出力先：/reports/starpay/test/202503_test.pdf
手動レポートとの比較のため、全スライドを生成してください。
```

**对比验证清单**

| 检查项 | 手工报告 | 自动生成 | 一致？ |
|--------|---------|---------|--------|
| 封面月份 | 2025年3月度 | 2025年3月度 | □ |
| GPV 数值（億円） | ___ | ___ | □ |
| 全部 16 业务线页面存在 | 16 页 | 16 页 | □ |
| 图表日文标题正常 | ✓ | □ | □ |
| PSP 饼图占比正确 | ___% | ___% | □ |
| 预测图显示置信区间 | ✓ | □ | □ |
| 文件大小合理 | ~15 MB | □ | □ |

**交付物**
- [ ] `202503_test.pdf` — 自动生成版
- [ ] 与手工版并排截图对比（每个模块1张）
- [ ] 差异修复记录

---

### Phase 3 完成标准

> ✅ 202503 测试报告与手工版本数值误差 < 1%，外观基本一致  
> ✅ 35 页全部生成，无空白占位符

---

## Phase 4 — Workflow 设计 & 自动化（1週間）
**2026-06-24 → 2026-06-30**

> **架构决策：为什么改用 Workflow 而不是纯 Agent？**
>
> 月报生成是一个步骤固定、合规敏感的 SOP。原方案将全部 7 个步骤写入 Agent 系统提示词，
> 依赖 LLM 每次"理解"并执行，存在步骤跳跃、顺序错乱、LLM 版本升级导致行为漂移等风险。
>
> 调整方案：**Workflow 为主，Agent 节点为辅。**
> - Workflow 节点图保证 SOP 顺序不可跳过，每步独立记录、可重试
> - 全部确定性操作（HTTP 调用、条件判断、数据传递）交给 Workflow 节点
> - 只有 2 处真正需要自然语言生成的步骤才调用 Agent 节点（LLM）

---

### TASK 4.1　设计 Workflow 节点图
**工期：Day 1–2**

在 Goku-AIOS **工作流设计器**（`/workflows`）中创建名为 `starpay-monthly-report` 的工作流。

**完整节点拓扑：**

```
[触发节点]  Cron: 每月1日 00:00 UTC (= 09:00 JST)
     │
     ▼
[代码节点]  计算上月期间
           period = last_month("YYYY-MM")
           yyyymm = last_month("YYYYMM")
     │
     ▼
[HTTP节点]  调用 business_report 工具
           POST /api/v1/tools/execute
           body: { tool: "business_report", params: { period, lang: "both" } }
     │
     ▼
[条件节点]  result.ok == true ?
     ├─ No  ──→  [HTTP节点] Feishu 告警：报告生成失败，附 error_message
     │                ↓ 结束
     └─ Yes ─→  继续
     │
     ▼
[HTTP节点]  MCP: get_monthly_kpi(period)
           → 输出变量: kpi { gpv_oku, txn_man, refund_rate_pct, gpv_mom_pct }
     │
     ▼
[HTTP节点]  MCP: get_psp_breakdown(period)
           → 输出变量: psp_list
     │
     ▼
[HTTP节点]  memory_search("starpay_report_reviewers")
           → 输出变量: reviewers
     │
     ▼
[条件节点]  reviewers 非空 ?
     ├─ No  ──→  [Agent节点 ①] 确认审阅人            ← LLM 节点
     │           prompt: 询问用户确认审阅人邮箱列表
     │           执行后: memory_write 保存 reviewers
     └─ Yes ─→  继续
     │
     ▼
[Agent节点 ②]  生成邮件正文 & Feishu 摘要            ← LLM 节点
           输入: period, kpi, file_path, reviewers
           输出: email_body (日語), feishu_summary
     │
     ▼
[HTTP节点]  submit_email_draft
           to: reviewers
           subject: "[StarPay] {YYYY}年{MM}月 月次レポート / Monthly Report"
           body: email_body
           attachment: file_path
     │
     ▼
[等待节点]  等待审批回调
           timeout: 48h
     │
     ▼
[条件节点]  审批结果 == "approved" ?
     ├─ No  ──→  [HTTP节点] Feishu 告警：审批被拒绝或超时，请人工处理
     │                ↓ 结束
     └─ Yes ─→  继续
     │
     ▼
[HTTP节点]  feishu_message / teams_message
           content: feishu_summary
     │
     ▼
[HTTP节点]  文件存档
           workspace_move: file_path → /reports/starpay/{yyyymm}_monthly_report.pdf
     │
     ▼
[HTTP节点]  todo_write
           记录: { status: "completed", period, file_path, reviewers, timestamp }
     │
     ▼
[结束节点]  ✅ 完成
```

**节点说明**

| 节点类型 | 数量 | 说明 |
|----------|------|------|
| Cron 触发节点 | 1 | 每月 1 日 00:00 UTC 触发 |
| 代码节点 | 1 | 计算上月期间字符串 |
| HTTP 节点 | 9 | 工具调用 / MCP 调用 / 存档 |
| 条件节点 | 3 | ok 检查 / reviewers 检查 / 审批结果 |
| **Agent 节点** | **2** | **唯二使用 LLM 的节点** |
| 等待节点 | 1 | 审批回调，最长等 48h |
| 结束节点 | 1 | |

**交付物**
- [ ] Workflow 节点图在设计器中保存并截图存档
- [ ] 节点图 JSON 导出至 `workflows/starpay_monthly_report.json`

---

### TASK 4.2　实现各节点配置
**工期：Day 2–4**

#### 代码节点：计算上月期间

```javascript
// 节点内联代码（WorkflowDesigner 代码节点）
const now = new Date();
const firstOfThisMonth = new Date(now.getFullYear(), now.getMonth(), 1);
const lastMonth = new Date(firstOfThisMonth - 1);
const yyyy = lastMonth.getFullYear();
const mm   = String(lastMonth.getMonth() + 1).padStart(2, '0');

output.period = `${yyyy}-${mm}`;          // "2026-05"
output.yyyymm = `${yyyy}${mm}`;          // "202605"
output.report_year  = String(yyyy);
output.report_month = mm;
```

#### HTTP 节点：business_report 调用

```json
{
  "url":    "{{AIOS_BASE_URL}}/api/v1/tools/execute",
  "method": "POST",
  "headers": { "Authorization": "Bearer {{SYSTEM_TOKEN}}" },
  "body": {
    "tool":   "business_report",
    "params": {
      "period": "{{nodes.calc_period.output.period}}",
      "lang":   "both"
    }
  },
  "output_mapping": {
    "ok":        "$.ok",
    "file_path": "$.file_path",
    "error_msg": "$.error"
  }
}
```

#### HTTP 节点：MCP get_monthly_kpi

```json
{
  "url":    "{{AIOS_BASE_URL}}/api/v1/mcp/starpay-data/call",
  "method": "POST",
  "body": {
    "tool":   "get_monthly_kpi",
    "params": { "period": "{{nodes.calc_period.output.period}}" }
  },
  "output_mapping": {
    "kpi": "$"
  }
}
```

#### Agent 节点 ①：确认审阅人（仅在 reviewers 为空时执行）

```
角色：StarPay 报告管理助手
任务：审阅人名单未注册，请向用户确认本次报告的审阅人邮箱列表，
     确认后调用 memory_write 保存到 tag "starpay_report_reviewers"。
输入：period={{period}}
约束：只做确认和保存，不生成报告内容。
```

#### Agent 节点 ②：生成邮件正文

```
角色：StarPay 报告通知撰写助手
任务：根据下方数据，用日语撰写审批邮件正文和飞书摘要。

报告期间：{{period}}
GPV：{{kpi.gpv_oku}} 億円（MoM {{kpi.gpv_mom_pct}}%）
取引件数：{{kpi.txn_man}} 万件
返金率：{{kpi.refund_rate_pct}}%
ファイル：{{file_path}}

输出格式（JSON）：
{
  "email_body":     "日语邮件正文，含报告摘要和查看说明",
  "feishu_summary": "飞书消息，100字以内，含核心数字"
}

约束：只生成文字内容，不调用任何其他工具。
```

#### 等待节点：审批回调

```json
{
  "type":        "approval_callback",
  "approval_id": "{{nodes.submit_draft.output.approval_id}}",
  "timeout_hours": 48,
  "on_timeout":  "branch_rejected"
}
```

**交付物**
- [ ] 全部节点配置完成，Workflow 可手动触发运行
- [ ] `workflows/starpay_monthly_report.json` 节点配置导出文件

---

### TASK 4.3　配置 Cron 定时触发并验证告警分支
**工期：Day 4–5**

**Cron 触发配置**（在 WorkflowDesigner 触发节点中设置）：

```
触发类型：Cron
表达式：0 0 1 * *     （每月1日 00:00 UTC = 09:00 JST）
时区：UTC
工作流：starpay-monthly-report
```

**告警分支验证**（手动触发异常场景）：

| 测试场景 | 触发方式 | 预期结果 |
|----------|---------|---------|
| business_report 返回 ok=false | mock 工具返回失败 | 飞书告警发出，Workflow 终止 |
| reviewers 未注册 | 清空 memory 后触发 | Agent 节点 ① 介入确认 |
| 审批超时 48h | 等待节点超时模拟 | 告警发出，状态标记 timeout |
| 审批被拒绝 | 审批中心手动拒绝 | 告警发出，todo_write 记录 rejected |

**交付物**
- [ ] Cron 触发器在 Goku-AIOS Schedules 页面可见并已启用
- [ ] 4 种异常场景测试通过，告警消息飞书频道收到截图

---

### TASK 4.4　上线试运行（2026年6月报告）
**工期：Day 5–7**

**上线当天节点执行时序（2026-07-01 09:00 JST）**

```
09:00  Cron 触发 → Workflow 启动
09:01  代码节点：period = "2026-06", yyyymm = "202606"
09:01  HTTP: business_report("2026-06") → 开始生成
09:25  business_report 完成：ok=true, file_path 返回
09:25  HTTP: get_monthly_kpi → kpi 数据就绪
09:26  HTTP: memory_search → reviewers 已注册，跳过 Agent 节点 ①
09:26  Agent 节点 ②：生成日语邮件正文（~10s）
09:26  HTTP: submit_email_draft → 审批通知发至 nss.p3@netstars.co.jp
09:26  等待节点：挂起，等待审批回调（最长 48h）

     ↓ 审批人收到邮件，审查报告（预计 30 min）

10:00  审批人点击「批准」
10:00  等待节点收到回调：approved
10:00  HTTP: feishu_message → 摘要发送
10:01  HTTP: 文件存档 → /reports/starpay/202606_monthly_report.pdf
10:01  HTTP: todo_write → 状态记录完成
10:01  Workflow 结束节点 ✅
```

**上线验收标准**

- [ ] Workflow 在 09:00 JST 准时由 Cron 触发
- [ ] 全 35 页 PDF 生成，无空白 / 乱码
- [ ] 数值与手工核对（抽查 5 个核心指标，误差 < 1%）
- [ ] Workflow 节点逐步执行记录可在 task_steps 中查到
- [ ] 审批邮件正常送达
- [ ] 存档路径 `/reports/starpay/202606_monthly_report.pdf` 正确
- [ ] 总耗时（触发到存档完成）< 45 分钟

---

### Phase 4 完成标准

> ✅ `starpay-monthly-report` Workflow 在设计器中完整实现，节点图已导出  
> ✅ 4 种告警异常场景全部测试通过  
> ✅ 2026-07-01 自动执行 202606 月报，全流程无人工干预（审批除外）  
> ✅ 审批、存档、通知均正常完成，每步执行日志可追溯

---

## 附录 A — 报告结构速查（35 slides）

| 模块 | Slides | 内容 | 图表类型 |
|------|--------|------|---------|
| 1. 封面 | 1 | 报告月份、生成日期 | — |
| 2. 核心 KPI | 2 | GPV / 件数 / 返金率 + MoM/YoY | KPI 卡片 |
| 3. OEM 活跃度 | 3 | 活跃店舗数、活跃率排名 | 横向柱状图 |
| 4–6. 趋势分析 | 4–6 | 日次 / 36月 / 返金率推移 | 折线 + 柱状 |
| 7. 支付类型 | 7 | CPM / MPM / PSP 占比 | 饼图 |
| 8–23. 专项业务×16 | 8–23 | 各业务线全指标 + MoM + 趋势 | 折线 + 柱状 |
| 24–26. TOP 排名 | 24–26 | OEM / PSP / 行业 TOP | 排名条形图 |
| 27–31. 占比分析 | 27–31 | OEM / PSP / CPM / MPM / 行业 | 饼图系列 |
| 32–35. 预测 | 32–35 | 下月 + 全年 GPV 预测区间 | 带状预测图 |

---

## 附录 B — Agent 节点提示词

> **重要变更（Phase 4 Workflow 架构调整后）**
>
> 原"7步 SOP 全写入 Agent 提示词"方案已废弃。  
> SOP 顺序现由 **Workflow 节点图**强制保证，Agent（LLM）只在以下 **2 个节点**被调用。
> `business-report-expert` 的系统提示词已大幅精简，不再包含流程控制逻辑。

---

### Agent 节点 ① — 确认审阅人（仅在 reviewers 未注册时触发）

**触发条件**：`memory_search("starpay_report_reviewers")` 返回空

**节点提示词：**

```
你是 StarPay 报告管理助手。

当前任务：月度报告的审阅人名单未注册，需要确认并保存。

请向用户询问本次 {period} 月报的审阅人邮箱列表，
确认后调用 memory_write 保存：
  tags: ["starpay_report_reviewers"]
  content: 邮箱列表（每行一个）

约束：
- 只做确认和保存，不生成报告内容
- 保存成功后输出 reviewers 列表供下游节点使用
- 禁止调用 business_report / submit_email_draft 等其他工具
```

---

### Agent 节点 ② — 生成邮件正文 & 飞书摘要

**触发条件**：business_report 成功，kpi 数据就绪，reviewers 已知

**节点提示词：**

```
你是 StarPay 报告通知撰写助手。

根据以下数据，撰写两份文案：

【报告数据】
报告期间：{period}（{report_year}年{report_month}月）
GPV：{kpi.gpv_oku} 億円（前月比 {kpi.gpv_mom_pct}%）
取引件数：{kpi.txn_man} 万件（前月比 {kpi.txn_mom_pct}%）
返金率：{kpi.refund_rate_pct}%
ファイルパス：{file_path}

【输出要求】
以 JSON 格式输出，包含两个字段：

email_body:
  - 语言：日语
  - 格式：正式邮件正文（含称谓、报告摘要、查看说明、落款）
  - 说明审批后将正式分发
  - 字数：200–350字

feishu_summary:
  - 语言：日语
  - 格式：飞书消息，简洁明了
  - 包含：月份、GPV、件数、返金率、文件路径
  - 字数：80–120字

约束：
- 只输出 JSON，不调用任何工具
- 数字保持原始精度，不四舍五入
- 不得在正文中承诺或预测未来数据
```

---

### `business-report-expert` 种子文件系统提示词（精简版）

> Phase 4 完成后，将 `backend/seeds/agents/business-report-expert.json`
> 的 `system_prompt_override` 替换为以下精简版。
> **SOP 流程控制已移至 Workflow，此处只保留工具调用能力声明。**

```
你是 StarPay 月度运营数据专家，在 Workflow 节点中被调用时执行指定的单项任务。

【可用数据工具】
- business_report(period, lang)   → 生成月度 PDF 报告
- starpay-data MCP 工具集：
    get_monthly_kpi / get_business_line_stats / get_psp_breakdown
    get_oem_ranking / get_daily_gpv / get_monthly_gpv_history
- memory_search / memory_write    → 读写持久记忆

【规范】
单位：GPV→億円，件数→万件
语言：日语正文，英语副标题
配色：主#0066CC 辅#FF6600

【数据原则】
主数据来自 business_report(AIBI)
补充指标通过 starpay-data MCP 工具获取
禁止：sql_query / aibi_query / web_search / 人工估算 / 直接 email_send
```

---

*文档版本：v1.0　作者：Goku-AIOS　日期：2026-05-20*
