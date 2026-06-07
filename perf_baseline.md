# AIOS GoKu — Performance Baseline

> **版本**: v1.9.13  
> **日期**: 2026-05-26  
> **工具**: [k6](https://k6.io/) (推荐) / Locust (备选)  
> **脚本目录**: `loadtest/`

---

## 一、测试场景说明

| 文件 | 并发用户 | 持续时间 | 用途 |
|------|---------|---------|------|
| `k6_smoke.js` | 1 VU | 30 s | 冒烟测试，验证 API 可达 |
| `k6_load_50vus.js` | 50 VUs | 7 min (1+5+1) | 小负载基准 |
| `k6_load_200vus.js` | 200 VUs | 12 min (2+8+2) | 中负载生产模拟 |
| `k6_load_500vus.js` | 500 VUs | 17 min (2+3+10+2) | 高负载压力测试 |

**场景权重**（200 VU / 500 VU 脚本）：

| 接口 | 权重 200VU | 权重 500VU |
|------|-----------|-----------|
| `GET /api/v1/agents` | 25 % | 40 % |
| `GET /api/v1/conversations` | 25 % | 25 % |
| `POST …/messages` (Chat) | 30 % | 15 % |
| `GET /api/v1/knowledge?q=…` | 10 % | 10 % |
| `GET /api/v1/analytics/dau` | 10 % | 10 % |

---

## 二、P99 目标值（SLA）

> 以下数值为**目标上限**，不是测量值。  
> 首次真实压测结果填入「三、实测结果」表格后更新。

| 接口类别 | P95 目标 | P99 目标 |
|---------|---------|---------|
| 只读 API（agents / conversations / analytics） | < 500 ms | < 1 000 ms |
| 知识库搜索（BM25 + Vector） | < 800 ms | < 2 000 ms |
| Chat（非 SSE，简单查询，fast-path） | < 3 000 ms | < 6 000 ms |
| Chat（ReAct loop，≤5 steps） | < 8 000 ms | < 15 000 ms |
| 端到端错误率 | < 1 % | — |
| Chat 错误率 | < 2 % | — |

---

## 三、实测结果（压测后填写）

### 3.1 50 VU 基准（`k6_load_50vus.js`）

| 指标 | 测量值 | 是否达标 |
|------|--------|--------|
| `http_req_duration` P95 | — ms | — |
| `http_req_duration` P99 | — ms | — |
| `chat_send_duration` P95 | — ms | — |
| `chat_send_duration` P99 | — ms | — |
| `http_req_failed` rate | — % | — |
| `chat_send_errors` rate | — % | — |

### 3.2 200 VU 生产模拟（`k6_load_200vus.js`）

| 指标 | 测量值 | 是否达标 |
|------|--------|--------|
| `http_req_duration` P95 | — ms | — |
| `http_req_duration` P99 | — ms | — |
| `chat_send_duration` P95 | — ms | — |
| `chat_send_duration` P99 | — ms | — |
| `http_req_failed` rate | — % | — |
| `chat_send_errors` rate | — % | — |
| `total_requests` | — | — |

### 3.3 500 VU 压力测试（`k6_load_500vus.js`）

| 指标 | 测量值 | 是否达标 |
|------|--------|--------|
| `http_req_duration` P95 | — ms | — |
| `http_req_duration` P99 | — ms | — |
| `chat_send_duration` P95 | — ms | — |
| `chat_send_duration` P99 | — ms | — |
| `http_req_failed` rate | — % | — |
| `chat_send_errors` rate | — % | — |
| 系统崩溃/重启 | — | — |

---

## 四、运行方式

### 4.1 前置准备

```bash
# 安装 k6（macOS）
brew install k6

# 启动 AIOS 本地实例
cd /path/to/agent && ./start.sh

# 获取 JWT（登录后从浏览器 Network tab 复制）
export TOKEN="eyJhbGciOi..."

# 获取或创建测试用 conversation id
export CONV_ID="$(curl -s -X POST http://localhost:8106/api/v1/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"k6 load test"}' | jq -r .id)"
```

### 4.2 执行顺序（建议）

```bash
# Step 1: 冒烟
k6 run loadtest/k6_smoke.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN

# Step 2: 50 VU
k6 run loadtest/k6_load_50vus.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN \
  -e CONV_ID=$CONV_ID \
  --out json=reports/k6_50vus.json

# Step 3: 200 VU
k6 run loadtest/k6_load_200vus.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN \
  -e CONV_ID=$CONV_ID \
  --out json=reports/k6_200vus.json

# Step 4: 500 VU（压力测试，确认系统稳定后再跑）
k6 run loadtest/k6_load_500vus.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN \
  -e CONV_ID=$CONV_ID \
  --out json=reports/k6_500vus.json
```

### 4.3 可视化（可选）

```bash
# InfluxDB + Grafana（k6 官方仪表盘）
k6 run loadtest/k6_load_200vus.js \
  -e BASE_URL=http://localhost:8106 \
  -e TOKEN=$TOKEN \
  -e CONV_ID=$CONV_ID \
  --out influxdb=http://localhost:8086/k6
```

---

## 五、Locust 备选方案

若环境中未安装 k6，可使用 Locust（Python）：

```bash
pip install locust

# 创建 loadtest/locustfile.py 后运行：
locust -f loadtest/locustfile.py \
  --host http://localhost:8106 \
  --headless \
  --users 200 \
  --spawn-rate 10 \
  --run-time 12m \
  -H "Authorization: Bearer $TOKEN"
```

---

## 六、基准劣化检测

将每次 CI/CD 部署后的压测 JSON 结果与本文档目标值对比：

```bash
# 解析 k6 JSON 输出
jq '.metrics.http_req_duration.values["p(99)"]' reports/k6_200vus.json
jq '.metrics.chat_send_duration.values["p(95)"]' reports/k6_200vus.json
```

若 P99 超出目标值 20 %，触发慢查询分析（参见 `docs/slow_query_audit.md`）。

---

## 七、已知限制

| 限制 | 说明 |
|------|------|
| LLM API 速率限制 | 500 VU 时 Chat P99 受 OpenAI/Claude API rate limit 影响，非 AIOS 本身瓶颈 |
| 单机内存 | 500 VU 需 ≥ 8 GB RAM；低于此值建议拆分测试 |
| DB 连接池 | 默认 `pool_size=20, max_overflow=40`；高并发时调整 `DATABASE_POOL_SIZE` env |
| Redis SSE | 多 worker 部署下需 `REDIS_URL`；否则 SSE 事件只送达持有连接的 worker |
