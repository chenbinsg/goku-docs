---
name: baiwu-opportunity-intelligence
description: Use when the task is to find, qualify, summarize, or prioritize business opportunities for Baiwu Technology across enterprise messaging, SMS, 5G messaging, 95 short-code voice, AI Agent applications, and LLM infrastructure/routing.
tool_sequence:
  - step: 1
    required_tool: baiwu_daily_report
    args:
      send_email: false
      subject_prefix: "[AIOS]"
---

# Baiwu Opportunity Intelligence

## Purpose

Support the agent `商机情报员` in finding and qualifying sales, bidding, channel, and partnership opportunities for 百悟科技.

This skill is for actionable opportunity intelligence, not generic market-news summaries.

## Structured report tool

For recurring daily briefs, scheduled jobs, or user requests such as "生成/发送商机日报", use `baiwu_daily_report` first. This tool calls the structured Baiwu collector, market-signal enrichment, report renderer, quality gate, and optional email sender.

Do not start a recurring daily brief with free-form `web_search` unless `baiwu_daily_report` fails or the user asks for a one-off deep dive. Web search is a fallback/enrichment path, not the primary execution path for the daily report.

## Sibling skills (always engage these alongside)

This skill defines **what** counts as a Baiwu opportunity. Two sibling skills define **how** to scan and **whether** the brief is publishable:

- `multi-source-tender-playbook` — apply for every recurring scan to enforce layered, multi-pool, multi-source search behavior.
- `research-quality-gate` — apply at the end of every brief, before sending, to enforce the publishable-quality bar.

Engage both whenever this skill triggers. They are domain-agnostic by design; the references below provide the Baiwu-specific substance they operate on.

## MUST Read (before answering — self-report which references you loaded)

The following references are mandatory inputs. **Before producing any brief, declare which references you have read** by emitting a one-line preamble (no need to dump contents) so it is auditable that the skill was followed:

```
[skill-load] baiwu-opportunity-intelligence + research-quality-gate + multi-source-tender-playbook;
references read: baiwu-product-map, <add others as required>.
```

References (Read on demand based on the rule column):

| Rule | Reference |
|---|---|
| Always — to judge product fit | [`references/baiwu-product-map.md`](references/baiwu-product-map.md) |
| Always — for the publishable-quality bar (now also enforced by `research-quality-gate`) | [`references/report-quality-gate.md`](references/report-quality-gate.md) |
| Always — for the report structure | [`references/report-template.md`](references/report-template.md) |
| Always — for the qualification lens | [`references/opportunity-qualification.md`](references/opportunity-qualification.md) |
| For operator / public-sector communication leads | [`references/china-operator-tender-map.md`](references/china-operator-tender-map.md) |
| For bank / branch leads | [`references/china-bank-branch-map.md`](references/china-bank-branch-map.md) |
| For fintech / collections / customer-service leads | [`references/fintech-collections-map.md`](references/fintech-collections-map.md) |
| For competitive-overlap analysis | [`references/competitor-landscape.md`](references/competitor-landscape.md) |
| For ranking / rejecting sources (now also enforced by `multi-source-tender-playbook`) | [`references/source-directory.md`](references/source-directory.md) |
| When initial query families return too few results | [`references/query-matrix.md`](references/query-matrix.md) |
| For the per-scan execution sequence (now also enforced by `multi-source-tender-playbook`) | [`references/search-playbook.md`](references/search-playbook.md) |

If you have not read the rule-mandated references for the situation, stop and Read them before continuing.

## Reasoning discipline

Always separate, in your output:

- ✅ confirmed facts (with source URL)
- 🔍 inferred fit / hypothesis (with reasoning chain)
- ❓ follow-up questions / verifications needed

Other principles:

- Prioritize opportunities that can lead to **near-term commercial action**, not generic AI hype.
- Prefer enterprise communication / customer-operation scenarios over broad market commentary.

## Coverage

Focus on opportunities related to:

- SMS
- 5G消息 / RCS / 富媒体企业消息
- 95短号码语音 / 呼叫中心 / 外呼 / 通知语音
- 基于 AIOS 的企业 AI Agent 应用
- LLM 聚合、模型路由、AI 基础设施
- 中国电信 / 中国移动 / 中国联通各省、市、区县分支机构的相关招标、比选、采购与中标线索
- 与梦网科技直接重叠的企业消息、5G消息、运营商生态机会
- 与 Twilio 类 CPaaS / 通信 API / AI 客户互动平台重叠的国际化或 API 化机会
- 各类银行、分行、支行、信用卡中心、远程银行中心、客服中心
- 消费金融、小贷、网贷、催收、外呼、客服与质检密集型金融科技企业

## Source priorities

Look first for:

- 招标公告 / 采购公告 / 中标候选人
- 官方采购平台、政府与国企采购站点
- 中国电信 / 中国移动 / 中国联通集团、省分、市分、区县分公司的采购与比选公告
- 各省运营商采购平台、地市分公司公告页、集团集中采购与地市复制采购线索
- 银行总行、分行、支行、信用卡中心、远程银行中心、客服中心的采购与公告页
- 消费金融、催收、客服外包、金融科技公司的采购、招标、生态合作与技术升级公告
- 企业合作发布、生态伙伴计划、渠道招募
- 行业会议、解决方案征集、试点项目
- 客户公开需求、数字化转型项目、客服与营销升级项目

Lower priority:

- pure financing news
- vague PR without budget owner or use case
- trend articles with no buyer, partner, or project signal

## Qualification lens

For every lead, assess:

1. Demand scenario
2. Product fit
3. Buying role
4. Budget / procurement signal
5. Timing urgency
6. Competitive risk
7. Recommended next action
8. Branch level / province / city / district
9. Direct-sell vs partner-led probability

Use the qualification details in [`references/opportunity-qualification.md`](references/opportunity-qualification.md).

## Output modes

### Opportunity card

Use when one clear lead is found.

Required fields:

- Opportunity title
- Lead type
- Customer / buyer / owner
- Why it matters for Baiwu
- Best-fit offering
- Evidence
- Risks / unknowns
- Suggested next step

### Daily brief

Use when scanning multiple leads.

Required sections:

1. 今日高价值机会
2. 值得跟进的次级线索
3. 按产品线归类
4. 建议销售动作
5. 待验证事项

Use [`references/report-template.md`](references/report-template.md) when generating a structured brief.
Default to this mode for recurring scans unless the user explicitly asks for a single lead deep dive.

## Good judgment rules

- If the project is really “customer contact / notification / service reach”, test SMS, 5G消息, and 95语音 in parallel instead of forcing one channel.
- If the project mentions AI客服, AI营销, AI运营, or agent automation, also test whether Baiwu’s AI Agent application and LLM routing capabilities create an upsell path.
- For tenders, do not overstate fit if the qualification requirements are not visible.
- For partnerships, explain whether Baiwu should approach as product supplier, messaging channel partner, AI solution partner, or infrastructure partner.
- For China operator tenders, explicitly state whether the lead is from group, province, city, or district level, because that changes sales motion and partner strategy.
- Distinguish network-infrastructure procurement from communication-platform procurement; Baiwu should prioritize the latter unless a clear AI or messaging layer entry point exists.
- If a province-level pattern repeats across multiple city branches, call it out as a replication opportunity rather than reporting each branch as unrelated news.
- Treat China Mobile / China Telecom / China Unicom city-branch tenders as first-class signals, not secondary noise. Examples like Xiamen Mobile, Fuzhou Mobile, or district-level branches can still matter if the scope points to messaging, voice, customer service, QA, or AI operations.
- Treat bank branches, credit-card centers, remote-banking centers, and service centers as first-class signals too; branch-level and center-level projects can still represent scalable demand.
- For fintech, consumer finance, and collections leads, prioritize scenarios with customer contact, reminders, servicing, QA, collections workflow, call center, or AI customer operations.
- When a lead overlaps with 梦网科技, explicitly mention 梦网 as the most likely domestic benchmark competitor unless evidence suggests otherwise.
- When a lead is more API-first, multinational, omnichannel, or developer-platform oriented, explicitly mention Twilio as the international benchmark and explain Baiwu’s local differentiation path.
- If a scan returns sparse results, explain which pools and source types were searched and propose the next query expansion rather than ending with a generic empty report.
- Search-engine result pages are discovery aids only; they are not acceptable final evidence.
- Do not include internal screenshot paths or browser screenshots as report attachments unless the user explicitly asked for visual evidence review.

## Deliverable bar

Do not finish with only a list of links.
Do not finish with only generic observations either.
Do not finish with only search-engine result links either.

The output must tell the commercial team:

- what the opportunity is
- why Baiwu is relevant
- which offering should lead
- what to do next
