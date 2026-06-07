# Workflow Webhook P1 Rollout Checklist

> 适用范围：`security(p1): require signed workflow webhooks` 之后的版本  
> 目标：将 workflow webhook 从“可直接触发”迁移到“每个 workflow 独立 secret + 时间窗 + replay 防护”

## 1. 变更摘要

本次 P1 加固引入以下行为：

- workflow 的 `webhook` trigger 必须配置独立 secret 才能启用
- webhook 请求必须包含：
  - `X-AIOS-Timestamp`
  - `X-AIOS-Signature`
- 服务端会校验：
  - secret 是否配置
  - timestamp 是否在有效时间窗内
  - HMAC 是否匹配
  - 请求是否为 replay

任何缺少上述条件的请求都会被拒绝。

## 2. 影响范围

会受到影响的场景：

- 所有使用 `POST /api/v1/workflows/{workflow_id}/trigger` 的系统
- 任何尚未为 workflow webhook 配置独立 secret 的集成
- 重试机制依赖“完全重复请求”的调用方

不会受到直接影响的场景：

- 非 workflow 的普通 API 调用
- 没有使用 webhook trigger 的 workflow

## 3. 升级前检查

在生产切换前，逐项确认：

```text
[ ] 已列出所有使用 workflow trigger 的外部系统
[ ] 每个 workflow 都已生成独立 webhook secret
[ ] 调用方已支持附加 X-AIOS-Timestamp
[ ] 调用方已支持按 timestamp.raw_body 计算 sha256 HMAC
[ ] 调用方的时钟与 NTP 保持同步
[ ] 已确认调用方不会在重试时原样重复相同 timestamp+signature+body
[ ] 已准备回滚窗口和运维联系人
```

## 4. Secret 配置策略

建议规则：

- 一个 workflow 一个 secret
- 不同环境（dev / staging / prod）使用不同 secret
- secret 长度至少 32 字节随机值
- secret 不写入 Git，不写入工单，不出现在日志

生成方式示例：

```bash
python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
```

## 5. 请求签名规则

### 5.1 请求头

```text
X-AIOS-Timestamp: 1717526400
X-AIOS-Signature: sha256=<hex digest>
```

### 5.2 计算方法

```text
payload = f"{timestamp}.{raw_body}"
signature = "sha256=" + HMAC_SHA256(secret, payload)
```

注意事项：

- 必须使用原始请求体 `raw_body`
- JSON 序列化格式变化会影响签名
- timestamp 必须是 Unix epoch seconds

### 5.3 Python 示例

```python
import hashlib
import hmac
import json
import time

secret = "replace-with-your-workflow-secret"
body = json.dumps({"input": {"message": "hello"}}, separators=(",", ":")).encode("utf-8")
timestamp = str(int(time.time()))
payload = timestamp.encode("utf-8") + b"." + body
signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
headers = {
    "X-AIOS-Timestamp": timestamp,
    "X-AIOS-Signature": signature,
    "Content-Type": "application/json",
}
```

## 6. 时间窗与重放防护

- 默认时间窗：`AIOS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS=300`
- 最小允许值：30 秒
- 服务端会拒绝：
  - 超出时间窗的请求
  - 相同 path + timestamp + signature + body 的重复请求

调用方注意：

- 重试时请生成新的 timestamp 和新的 signature
- 不要缓存或重放旧请求体与旧签名

## 7. 灰度发布建议

### 阶段 A：准备

1. 给所有目标 workflow 配置 secret
2. 在 staging 环境完成签名联调
3. 监控 403 / 409 返回情况

### 阶段 B：灰度

1. 选一到两个低风险 workflow 先切
2. 观察：
   - 403（签名失败 / 时间戳失败）
   - 409（replay）
   - 调用方超时 / 重试异常
3. 确认调用成功率恢复后，再扩大范围

### 阶段 C：全面切换

1. 所有 workflow webhook 均切到签名版
2. 明确禁用任何旧的未签名调用方式
3. 更新对接文档和 runbook

## 8. 验证命令

### 8.1 正向验证

```bash
curl -i -X POST "https://aios.example.com/api/v1/workflows/<workflow_id>/trigger" \
  -H "Content-Type: application/json" \
  -H "X-AIOS-Timestamp: <ts>" \
  -H "X-AIOS-Signature: <sig>" \
  --data '{"input":{"message":"hello"}}'
```

期望：

- `202 Accepted`

### 8.2 负向验证

分别验证以下情况必须失败：

- 缺 `X-AIOS-Timestamp`
- 缺 `X-AIOS-Signature`
- 使用错误 secret
- 使用过期 timestamp
- 重放完全相同请求

期望：

- `403`：签名/时间戳无效
- `409`：replay

## 9. 回滚说明

如果必须临时回滚：

1. 优先回滚调用方签名逻辑到上一个稳定版本
2. 仅在本地/临时排障环境下，才考虑显式启用：

```dotenv
AIOS_ALLOW_INSECURE_WEBHOOKS=true
```

3. 生产环境不要把这个开关作为常态方案

## 10. 发布后观察项

发布后 24 小时内重点看：

- workflow trigger 403 数量
- replay 409 数量
- 调用方重试频率
- 与 webhook 相关的 5xx
- workflow 执行创建量是否异常下降

如果出现集中失败，先检查：

- secret 是否配错
- JSON 序列化是否改变
- timestamp 是否使用毫秒而不是秒
- 服务器与调用方时钟是否漂移
