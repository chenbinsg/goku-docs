# China operator tender map

This file helps the agent identify commercially meaningful tender signals from
China Telecom, China Mobile, and China Unicom across province, city, and district levels.

## Why this matters for Baiwu

Operator tenders can indicate:

- direct messaging / notification procurement
- 5G消息 / RCS ecosystem build-out
- voice platform, call center, or 95-related service demand
- AI customer service, AI operations, and knowledge workflow projects
- AI gateway, model routing, or enterprise AI infrastructure opportunities

These tenders may become:

- direct supplier opportunities
- partner / subcontractor opportunities
- ecosystem cooperation leads
- proof points for vertical solution replication

## Core operators to monitor

### China Telecom

Common naming patterns:

- 中国电信
- 中国电信股份有限公司
- 中国电信集团有限公司
- 中国电信 <省名> 分公司
- 中国电信 <地市名> 分公司
- 天翼云 / 天翼数字生活 / 天翼物联 related entities

Typical opportunity signals:

- 短信平台、消息中台、触达平台
- 5G消息、富媒体消息、消息运营
- 客服热线、智能外呼、语音通知
- AI客服、知识库、智能运营、工单自动化
- 大模型平台、模型接入、推理网关、路由编排

### China Mobile

Common naming patterns:

- 中国移动
- 中国移动通信集团有限公司
- 中国移动通信集团 <省名> 有限公司
- 中国移动 <地市> 分公司
- 中移在线 / 中移互联网 / 咪咕 / 移动云 related entities

Typical opportunity signals:

- 短彩信、消息平台、触达运营
- 5G消息运营平台、消息门户、行业消息
- 呼叫中心、语音服务、外呼平台
- AI客服、数字员工、运营智能化
- 算力调度、大模型接入、多模型管理

### China Unicom

Common naming patterns:

- 中国联通
- 中国联合网络通信有限公司
- 中国联合网络通信有限公司 <省分公司>
- 中国联通 <地市> 分公司
- 联通在线 / 联通数科 / 联通云 related entities

Typical opportunity signals:

- 短信能力、消息触达、行业消息
- 5G消息、消息运营、富媒体交互
- 智慧客服、热线平台、语音通知
- AI助理、智能运营、流程自动化
- 大模型平台、模型路由、统一 AI 接入

## Administrative levels to track

The agent should explicitly note which level the opportunity belongs to:

- national / group level
- provincial branch
- prefecture-level city branch
- district / county branch
- operator-affiliated digital subsidiary

Higher priority:

- group-level frameworks
- province-level centralized procurement
- repeated city-level rollout under one provincial pattern

## Search heuristics

Always combine operator names with tender-intent terms.

### Base procurement terms

- 招标公告
- 采购公告
- 比选公告
- 询价公告
- 竞争性谈判
- 单一来源
- 中标候选人
- 中选结果
- 采购需求
- 项目公告

### Messaging terms

- 短信
- 短彩信
- 消息平台
- 通知平台
- 触达平台
- 5G消息
- 富媒体消息
- RCS

### Voice terms

- 95
- 呼叫中心
- 智能外呼
- 语音通知
- 语音平台
- 客服热线

### AI / infrastructure terms

- AI客服
- 智能客服
- 智能运营
- 数字员工
- 知识库
- 大模型
- 模型接入
- 模型路由
- AI平台
- AI中台
- 智能体
- Agent

## Region scanning method

For recurring scans, rotate or batch by:

- province
- municipality
- key prefecture-level cities
- strategic districts / counties when visible

Priority regions to watch more closely:

- Beijing
- Shanghai
- Guangdong
- Zhejiang
- Jiangsu
- Shandong
- Sichuan
- Hubei
- Fujian
- Henan

City-level examples that should not be ignored if procurement scope is relevant:

- Xiamen Mobile / Fujian Mobile Xiamen branch
- Shenzhen Mobile / Guangdong Mobile Shenzhen branch
- Hangzhou Mobile / Zhejiang Mobile Hangzhou branch
- Suzhou Mobile / Jiangsu Mobile Suzhou branch
- Qingdao Mobile / Shandong Mobile Qingdao branch

## What to capture from each tender

At minimum, extract:

- operator name
- branch level
- province / city / district
- project name
- project type
- procurement stage
- budget if visible
- qualification requirements if visible
- whether Baiwu can approach directly or via ecosystem partner
- whether the opportunity resembles a repeatable provincial / city template

## Baiwu relevance rules

Treat these as high-fit if they involve:

- enterprise message reach or notification capability
- 5G消息 / RCS deployment or operations
- voice customer contact / service restoration / hotline upgrade
- AI客服, AI运营, 工单自动化, 知识驱动服务
- multi-model access, AI platform control, routing, or governance

Treat with caution if:

- the project is pure network hardware / base station / transmission equipment
- the procurement scope is general cloud without communication or AI workflow relevance
- the incumbent operator-owned platform clearly dominates with no partner entry path

## Output expectation

When an operator tender is found, the agent should say clearly:

- which operator
- which branch and region
- which business line it maps to for Baiwu
- whether it is likely a direct deal, partner-assisted deal, or watchlist item
