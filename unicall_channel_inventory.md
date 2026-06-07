# UniCall Channel Inventory

> **状态核对 · 2026-06-01**  
> 本文档是 UniCall Phase 0 交付物，记录每个渠道的当前能力、限制和接入状态。

---

## 渠道能力矩阵

| 功能 | 飞书 | Email | PWA | Teams | LINE | WeChat 企业微信 |
|------|:----:|:-----:|:---:|:-----:|:----:|:--------------:|
| 入站文本消息 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 出站文本 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 出站富卡片 | ✅ 飞书卡片 | ❌ 降级链接 | ✅ Web Push | ✅ Adaptive Card | ✅ Flex Message | ✅ textcard |
| 按钮动作回调 | ✅ | ❌ | ❌ | ✅ Action.Submit | ✅ postback | ❌ |
| 深链（打开移动页） | ✅ URL button | ✅ 文本链接 | ✅ PWA route | ✅ Action.OpenUrl | ✅ uri action | ✅ url button |
| Webhook 签名校验 | ✅ HMAC-SHA256 | ❌ 不需要 | ❌ N/A | ✅ JWT Bearer | ✅ HMAC-SHA256 | ✅ SHA1 + AES |
| 用户身份绑定 | ✅ OpenID | ✅ 邮箱匹配 | ✅ PWA subscription | ✅ AAD user ID | ✅ LINE userId | ✅ 企业微信 userid |
| 入站图片/附件 | ⚠️ 需扩展 | ⚠️ 需扩展 | ❌ | ⚠️ 需扩展 | ⚠️ 需扩展 | ⚠️ 需扩展 |
| UniCall Gateway 接入 | ✅ MVP | ✅ MVP | ✅ MVP | ✅ | ✅ | ✅ |
| Adapter 单元测试 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 渠道详情

### 飞书 (Feishu)

| 项目 | 详情 |
|------|------|
| **Webhook 接入路径** | `POST /api/v1/unicall/webhooks/feishu` |
| **签名算法** | `X-Lark-Signature` HMAC-SHA256（timestamp + body） |
| **出站 API** | Feishu Bot API `chat.message.create` |
| **用户 ID 类型** | `open_id`（需事件订阅权限） |
| **卡片按钮限制** | 最多 5 个 action，每个 label ≤ 30 字 |
| **环境变量** | `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, `FEISHU_VERIFICATION_TOKEN` |
| **接入状态** | ✅ 已接入，单元测试覆盖 |

### Email

| 项目 | 详情 |
|------|------|
| **Webhook 接入路径** | `POST /api/v1/unicall/webhooks/email` |
| **签名算法** | 无（IP 白名单或 SMTP relay 认证） |
| **出站 API** | SMTP / 已有 EmailConnector |
| **用户 ID 类型** | 邮箱地址（自动匹配 User.email） |
| **卡片支持** | 无，降级为 HTML 链接 |
| **环境变量** | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` |
| **接入状态** | ✅ 已接入 |

### PWA / Web Push

| 项目 | 详情 |
|------|------|
| **Webhook 接入路径** | N/A（仅出站） |
| **出站 API** | Web Push Protocol（VAPID） |
| **用户 ID 类型** | PushSubscription（存储在 `push_subscriptions` 表） |
| **限制** | 需 HTTPS；iOS 16.4+ 才支持 PWA Push |
| **环境变量** | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL` |
| **接入状态** | ✅ 已接入 |

### Microsoft Teams

| 项目 | 详情 |
|------|------|
| **Webhook 接入路径** | `POST /api/v1/unicall/webhooks/teams` |
| **签名算法** | Azure Bot Framework JWT Bearer（header `Authorization`） |
| **出站 API** | Bot Framework REST（`{serviceUrl}/v3/conversations/{convId}/activities`） |
| **用户 ID 类型** | Azure AD 用户 ID + conversation reference（JSON） |
| **卡片格式** | Adaptive Card v1.4（Action.Submit + Action.OpenUrl） |
| **限制** | 多租户 Bot 需 Azure Bot Service 注册 |
| **环境变量** | `TEAMS_APP_ID`, `TEAMS_APP_PASSWORD`, `TEAMS_TENANT_ID` |
| **接入状态** | ✅ Adapter 实现，单元测试覆盖；需真实 Bot 注册验证 |

### LINE

| 项目 | 详情 |
|------|------|
| **Webhook 接入路径** | `POST /api/v1/unicall/webhooks/line` |
| **签名算法** | `X-Line-Signature` HMAC-SHA256 |
| **出站 API** | LINE Messaging API `push` |
| **用户 ID 类型** | `userId`（LINE openId） |
| **卡片格式** | Flex Message（bubble）；按钮支持 postback + uri |
| **限制** | Push API 需 LINE Official Account；reply 有时间限制 |
| **环境变量** | `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN` |
| **接入状态** | ✅ Adapter 实现，单元测试覆盖 |

### WeChat Work 企业微信

| 项目 | 详情 |
|------|------|
| **Webhook 接入路径** | `POST /api/v1/unicall/webhooks/wechat` |
| **签名算法** | GET 验证：`echostr` echo；POST：`msg_signature` SHA1 + AES 解密 |
| **出站 API** | 企业微信 App API（`/cgi-bin/message/send`）或 Group Bot Webhook |
| **用户 ID 类型** | 企业微信 `userid`（英文用户名） |
| **卡片格式** | `textcard`（标题 + 描述 + URL）；无交互按钮 |
| **限制** | 需企业微信认证；textcard 不支持多按钮 |
| **环境变量** | `WECHAT_CORP_ID`, `WECHAT_CORP_SECRET`, `WECHAT_AGENT_ID`, `WECHAT_TOKEN`, `WECHAT_ENCODING_AES_KEY`, `WECHAT_BOT_WEBHOOK_KEY` |
| **接入状态** | ✅ Adapter 实现；需企业认证账号集成测试 |

---

## 统一消息 JSON Schema（第一版）

### 入站消息 (UnifiedInboundMessage)

```json
{
  "channel": "feishu",
  "external_user_id": "ou_abc123",
  "external_display_name": "张三",
  "external_message_id": "om_xxx",
  "tenant_hint": null,
  "message_type": "text",
  "text": "帮我查今天的审批",
  "attachments": [],
  "raw": {}
}
```

### 出站消息 (UnifiedOutboundMessage)

```json
{
  "message_type": "task_completed",
  "title": "任务已完成",
  "body": "Q4 销售报告已生成，共 15 页。",
  "actions": [
    {
      "id": "open_task",
      "label": "查看详情",
      "style": "primary",
      "target_type": "task",
      "target_id": "task-uuid",
      "payload": {}
    }
  ],
  "deep_link": "/mobile/tasks/task-uuid?uid=user-id&exp=1234567890&sig=abcd1234",
  "payload": { "task_id": "task-uuid" }
}
```

### 渠道动作 (ChannelActionRequest)

```json
{
  "channel": "feishu",
  "external_user_id": "ou_abc123",
  "action_type": "approve",
  "target_type": "approval",
  "target_id": "appr-uuid",
  "payload": { "comment": "同意" },
  "idempotency_key": "feishu:ou_abc123:appr-uuid:approve:20260601"
}
```

---

## 深链规范（第一版）

所有渠道通知中的深链均经过 HMAC-SHA256 签名，格式如下：

```
/mobile/{type}/{id}?uid={user_id}&exp={unix_ts}&sig={16char_hex}
```

| 参数 | 说明 |
|------|------|
| `uid` | AIOS user_id |
| `exp` | Unix timestamp（1 小时后过期） |
| `sig` | `HMAC-SHA256(SECRET_KEY, "{path}:{uid}:{exp}")[:16]` |

验证端点：`GET /api/v1/mobile/deep-link/resolve?path=...&uid=...&exp=...&sig=...`

---

## 待接入渠道（后续队列）

| 渠道 | 障碍 | 预计时间 |
|------|------|---------|
| WeChat 公众号 | 需通过微信认证审批（约 2 周） | TBD |
| DingTalk 钉钉 | connector 已有基础，待 adapter 封装 | 1 周 |
| Slack | 需 Slack App 配置 | 1 周 |
