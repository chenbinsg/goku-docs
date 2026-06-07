# Feishu Bidirectional Bot Setup

> 适用范围：AIOS UniCall 飞书双向 Bot 第一阶段实验。
>
> 目标闭环：飞书用户发消息 -> AIOS UniCall 入站 -> 创建任务并即时回复 -> 任务完成后再回飞书。

---

## 1. 当前结论

AIOS 现在支持两种飞书发送方式：

| 能力 | 用途 | 关键配置 |
|------|------|----------|
| 应用机器人 Open API | 双向对话、按 `chat_id` / `open_id` 回复 | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` |
| 群自定义机器人 Webhook | AIOS 主动往固定群推通知 | `FEISHU_WEBHOOK_URL`, `FEISHU_WEBHOOK_SECRET` |

本实验要验证的是第一种：应用机器人双向对话。

不要把 `FEISHU_WEBHOOK_URL` 当成双向 Bot 的回复目标。Webhook 只能推到固定群，不能可靠地回到用户刚才发消息的会话。

---

## 2. 前置条件

实验机器需要具备：

1. 一个公网 HTTPS URL，可以被飞书开放平台访问。
2. AIOS 后端服务已启动。
3. 飞书企业自建应用的管理员权限。
4. AIOS 中至少有一个可登录用户，用于绑定飞书账号。

本地开发机不能直接把 `localhost` 填给飞书。可以使用：

- 正式域名 + 反向代理
- ngrok
- Cloudflare Tunnel
- 其他能提供公网 HTTPS 的隧道服务

本文以下用 `{PUBLIC_BASE_URL}` 表示公网地址，例如：

```text
https://aios.example.com
```

---

## 3. AIOS 回调地址

飞书事件订阅请求地址填写：

```text
{PUBLIC_BASE_URL}/api/v1/unicall/webhooks/feishu
```

示例：

```text
https://aios.example.com/api/v1/unicall/webhooks/feishu
```

注意：

- 推荐使用 UniCall 入口：`/api/v1/unicall/webhooks/feishu`
- 不推荐继续使用旧入口：`/api/v1/connectors/feishu/webhook`
- 旧入口主要是历史 connector 路径，不负责完整的 UniCall 用户绑定、任务分发和通知闭环

---

## 4. AIOS 环境变量

双向 Bot 必填：

```env
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
```

事件回调签名/安全校验可选，但建议配置：

```env
FEISHU_WEBHOOK_SECRET=xxxxx
```

如果还需要“AIOS 主动推消息到固定飞书群”，再额外配置：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx
FEISHU_WEBHOOK_SECRET=xxxxx
```

配置方式二选一：

1. 写入后端运行环境或 `.env` 后重启后端服务。
2. 在 AIOS 连接器配置页面写入 Feishu 配置，然后重启后端服务。

建议实验时重启一次后端服务，避免运行中已加载的 connector 仍使用旧环境变量。

---

## 5. 飞书开放平台配置

进入飞书开放平台，创建或打开一个“企业自建应用”。

### 5.1 添加机器人能力

在应用能力里添加：

```text
机器人
```

并确保机器人能力已启用。

### 5.2 记录应用凭证

复制：

```text
App ID
App Secret
```

填入 AIOS：

```env
FEISHU_APP_ID=...
FEISHU_APP_SECRET=...
```

### 5.3 配置事件订阅

在“事件订阅”或“事件与回调”里配置请求地址：

```text
{PUBLIC_BASE_URL}/api/v1/unicall/webhooks/feishu
```

添加事件：

```text
im.message.receive_v1
```

该事件用于接收用户发给机器人、或群里 @机器人的消息。

### 5.4 配置权限

建议先申请这些权限：

```text
im:message:send_as_bot
im:message.p2p_msg:readonly
im:message.group_at_msg:readonly
```

含义：

| 权限 | 用途 |
|------|------|
| `im:message:send_as_bot` | 允许应用以机器人身份发送消息 |
| `im:message.p2p_msg:readonly` | 允许接收用户发给机器人的单聊消息 |
| `im:message.group_at_msg:readonly` | 允许接收群聊中 @机器人的消息 |

如果实验需要机器人读取群里所有消息，而不是只处理 @ 消息，需要额外申请更高权限；第一阶段不建议这么做。

### 5.5 发布应用

权限和事件配置完成后，需要发布应用版本到企业可用范围。

如果不发布，常见现象是：

- 飞书后台能保存配置，但事件不触发
- Bot 能被看到，但不能接收消息
- AIOS 调发送接口时报权限不足

---

## 6. 用户绑定

AIOS 需要知道某个飞书 `open_id` 对应哪个 AIOS 用户。

推荐绑定流程：

1. AIOS 用户登录系统。
2. 在 UniCall / 移动工作台 / 账号绑定入口生成绑定码。
3. 用户通过飞书机器人发送绑定码，或由管理员调用绑定接口完成绑定。
4. AIOS 将该飞书账号绑定到当前用户。

绑定接口：

```http
POST /api/v1/unicall/bind-codes/redeem
```

示例请求体：

```json
{
  "code": "AB12CD34",
  "channel": "feishu",
  "external_user_id": "ou_xxxxx",
  "external_display_name": "张三"
}
```

绑定成功后，AIOS 会在用户的 `ChannelAccount.metadata` 中持续更新：

```json
{
  "open_id": "ou_xxxxx",
  "chat_id": "oc_xxxxx",
  "receive_id": "oc_xxxxx",
  "receive_id_type": "chat_id"
}
```

后续任务完成通知会优先使用这些字段回到飞书原会话。

---

## 7. 最小验收流程

### 7.1 检查后端健康

确认公网 URL 可访问 AIOS 后端，例如：

```bash
curl -i {PUBLIC_BASE_URL}/health
```

如果项目健康检查路径不同，以当前部署为准。

### 7.2 飞书后台验证事件地址

在飞书事件订阅页保存请求地址。

如果验证失败，优先检查：

- 公网 HTTPS 是否可访问
- 反向代理是否转发到 AIOS 后端
- 请求路径是否是 `/api/v1/unicall/webhooks/feishu`
- 后端日志中是否收到 `url_verification`
- 签名密钥是否和 AIOS 配置一致

### 7.3 未绑定账号测试

在飞书中给机器人发一条单聊消息：

```text
测试 AIOS
```

或在群中：

```text
@AIOS 测试 AIOS
```

预期结果：

```text
当前账号还没有绑定到 AIOS 用户，请先在 Goku-AIOS 中完成 UniCall 账号绑定。
```

这说明：

- 飞书事件已进入 AIOS
- AIOS 可以通过飞书应用机器人回消息
- 还缺用户绑定

### 7.4 绑定后测试

完成绑定后，再给机器人发：

```text
帮我创建一个测试任务
```

预期即时回复：

```text
已提交到 Goku-AIOS，任务 ID: ...
```

任务完成后，预期飞书收到：

```text
任务已完成
...
```

---

## 8. 常见问题

### 8.1 飞书能验证 URL，但发消息没有进入 AIOS

检查是否添加了事件：

```text
im.message.receive_v1
```

同时检查应用是否已发布到企业可用范围。

### 8.2 AIOS 收到消息，但飞书没有回复

检查：

```env
FEISHU_APP_ID
FEISHU_APP_SECRET
```

以及应用权限：

```text
im:message:send_as_bot
```

如果是群聊，还要确认机器人在群里，且用户消息中 @ 了机器人。

### 8.3 任务完成通知发不回原会话

检查用户绑定记录中是否存在：

```json
{
  "chat_id": "...",
  "open_id": "...",
  "receive_id": "...",
  "receive_id_type": "chat_id"
}
```

如果 metadata 为空，说明绑定后还没有收到过该用户的飞书入站消息。让用户重新给机器人发一条消息，AIOS 会刷新会话上下文。

### 8.4 配了 `FEISHU_WEBHOOK_URL` 仍然不能双向对话

这是预期的。

`FEISHU_WEBHOOK_URL` 是群自定义机器人 webhook，只适合固定群通知。

双向 Bot 必须配置：

```env
FEISHU_APP_ID
FEISHU_APP_SECRET
```

并使用：

```text
/api/v1/unicall/webhooks/feishu
```

### 8.5 修改配置后仍然使用旧凭证

重启 AIOS 后端服务。

当前 connector 在进程启动时读取部分飞书环境变量。实验机器修改 `.env` 或连接器配置后，建议重启后端，确保凭证刷新。

---

## 9. 实验记录模板

```text
实验日期：
实验机器：
PUBLIC_BASE_URL：
AIOS 版本/分支：

飞书应用：
- App ID：
- 机器人能力：已启用 / 未启用
- 事件 im.message.receive_v1：已添加 / 未添加
- 权限 im:message:send_as_bot：已开通 / 未开通
- 权限 im:message.p2p_msg:readonly：已开通 / 未开通
- 权限 im:message.group_at_msg:readonly：已开通 / 未开通
- 应用版本：已发布 / 未发布

AIOS 配置：
- FEISHU_APP_ID：已配置 / 未配置
- FEISHU_APP_SECRET：已配置 / 未配置
- FEISHU_WEBHOOK_SECRET：已配置 / 未配置
- FEISHU_WEBHOOK_URL：已配置 / 未配置 / 不需要

验收：
- URL 验证：通过 / 失败
- 未绑定账号回复：通过 / 失败
- 绑定成功：通过 / 失败
- 任务创建即时回复：通过 / 失败
- 任务完成回飞书：通过 / 失败

问题记录：
```

---

## 10. 参考文档

- Feishu Open Platform - 发送消息：<https://open.feishu.cn/document/server-docs/im-v1/message/create?lang=zh-CN>
- Feishu Open Platform - 接收消息事件：<https://open.feishu.cn/document/server-docs/im-v1/message/events/receive?lang=zh-CN>
- AIOS UniCall 渠道清单：`docs/unicall_channel_inventory.md`
