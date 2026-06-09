# Goku Skills 编写标准 v2.0

> 本文档是 Goku Agent Runtime Skills Library 的唯一权威标准。  
> 所有新增、修改、审核 Skill 均须严格遵守本标准。  
> 版本：v2.0 · 生效日期：2026-06-09

---

## 一、什么是 Skill

**Skill = 可复用的任务方法论包**，封装了完成某类任务所需的：

- 任务目标（Purpose）
- 触发条件（When to use）
- 输入参数（Inputs）
- 执行步骤（Procedure）
- 工具策略（Tools）
- 输出格式（Output）
- 质量边界（Quality checks）

Skill 不是代码，是 **Agent 的行为规范**。Goku Runtime 加载 Skill 后，Agent 按照其定义的方法论执行任务。

---

## 二、技能库结构（60/30/10）

Skills Library 按用途分为三类，通过每个 Skill 的 `category` 字段标识：

| 类别 | category 值 | 占比 | 说明 |
|------|------------|------|------|
| **通用技能包** | `general` | 60% | 跨行业、跨部门通用，所有企业都可直接使用 |
| **行业技能包** | `industry` | 30% | 特定行业场景，可按包交付给同行业客户 |
| **企业定制技能** | `enterprise` | 10% | 特定客户专属，含客户业务逻辑和数据 |

### 通用技能包（general）子分类

| subcategory | 说明 | 典型技能 |
|-------------|------|---------|
| `office` | 通用办公，全部门适用 | 会议纪要、周报、SOP、KPI、FAQ |
| `hr` | 人力资源 | JD生成、面试评估、入职、离职 |
| `finance` | 财务 | 报销审核、发票核对、预算编制 |
| `sales` | 销售 | 拜访记录、竞品分析、提案、客户画像 |
| `marketing` | 市场 | 营销文案 |
| `legal` | 法务合规 | 合同初筛、监管更新、项目风险 |
| `tech` | 技术支持 | 工单分派、PRD质检、变更审核 |
| `document` | 文档处理 | PDF/Word/PPT/Excel |
| `design` | 设计创意 | 图标、海报、插画、UI |
| `travel` | 出行生活 | 机票、日本系列、行程规划 |

### 行业技能包（industry）子分类

| subcategory | 说明 |
|-------------|------|
| `ir` | 投资者关系（上市公司 IR 全套） |
| `fintech` | 金融科技（支付、交易分析） |

### 企业定制技能（enterprise）子分类

| subcategory | 说明 |
|-------------|------|
| `tianchuang` | 天创征信专属技能 |

---

## 三、文件结构规范

每个 Skill 独立存放于 `skills/[skill-name]/SKILL.md`，文件名全部小写，单词用连字符 `-` 分隔。

```
skills/
├── meeting-notes-generation/
│   └── SKILL.md
├── credit-risk-report/
│   └── SKILL.md
└── ...
```

---

## 四、SKILL.md 格式规范（强制）

每个 SKILL.md 必须包含以下内容，**章节顺序固定，章节名称固定**：

### 4.1 YAML Frontmatter（必填）

```yaml
---
name: skill-name                    # 与目录名一致，连字符格式
description: 一句话描述，不超过50字    # 用于 Runtime 路由和 README 展示
category: general                   # general / industry / enterprise（必填）
subcategory: office                 # 见第二节分类表（必填）
tags: [标签1, 标签2, 标签3]          # 3-5个关键词，用于搜索和过滤（必填）
---
```

**所有四个字段（name、description、category、subcategory、tags）均为必填。** 缺少任一字段的 Skill 视为不合格，不得上线。

### 4.2 七个标准章节（必填，顺序固定）

```markdown
# Skill: [skill-name]

## Purpose
## When to use
## Inputs
## Procedure
## Tools
## Output
## Quality checks
```

---

## 五、各章节编写规范

### § Purpose
- **长度**：2-3 句话，不超过 100 字
- **内容**：说明技能存在的原因、解决什么问题、适用的核心场景
- **禁止**：不写流程步骤，不写工具列表，不写禁止行为

```markdown
## Purpose

将原始会议录音或文字记录转化为结构清晰的标准会议纪要，自动识别决议、待办事项和责任人。
适用于内部例会、客户会议、跨部门协作等全场景，减少人工整理时间，确保信息不遗漏。
```

---

### § When to use
- 必须包含**中文触发关键词**（必填）
- 建议包含**英文触发关键词**（推荐）
- 涉及日语场景的 Skill 加**日文触发关键词**
- 每类关键词 5-15 个，覆盖常见表达方式

```markdown
## When to use

**触发关键词（中文）：**
会议纪要, 帮我整理会议, 录音转文字, 会议记录, 整理一下刚才开的会

**触发关键词（英文）：**
meeting notes, meeting minutes, summarize meeting, action items
```

---

### § Inputs
- 每个参数独占一行，格式：`` - `param_name`: 描述（必填/可选） ``
- 参数名使用 **snake_case**
- 必须标注是否必填，可选参数说明默认值
- 参数数量建议 3-8 个

```markdown
## Inputs

- `raw_text`: 会议录音转写文字或手写记录（必填）
- `meeting_date`: 会议日期，格式 YYYY-MM-DD（可选，未提供则标【未提供】）
- `attendees`: 参会人员名单（可选）
- `meeting_topic`: 会议主题（可选，未提供时从内容推断）
```

---

### § Procedure
- 使用**编号步骤**（1. 2. 3.），复杂流程可分阶段（### 阶段一：...）
- 每个步骤是**可执行的动作**，不是抽象描述
- 追问用户时，最多追问 **1 次**，格式固定：
  ```
  ask_user(question="具体问题")
  ```
- 代码示例、判断矩阵、分类表可内嵌在对应步骤中

```markdown
## Procedure

### 阶段一：信息提取

1. **解析输入内容**，识别：会议时间、参会人、议题列表
2. **补全缺失信息**：日期或参会人缺失时追问 1 次：
   ```
   ask_user(question="请提供会议日期和参会人员名单")
   ```

### 阶段二：结构化整理

3. **提炼决议**：明确已达成共识的结论，每条一句话
4. **整理待办**：每条格式为「负责人 + 事项 + 截止时间」
5. **生成纪要**，格式见 Output 章节
```

---

### § Tools
- 使用**表格格式**（必须）
- 列出所有可能调用的工具
- 标注工具用途，可选工具注明「可选」

```markdown
## Tools

| 工具 | 用途 |
|------|------|
| `ask_user` | 追问缺失的会议信息，最多追问 1 次 |
| `file_read` | 读取上传的录音转写文件（可选）|
| `email_draft` | 将纪要起草为邮件发送给参会者（可选）|
```

---

### § Output
- 提供**固定格式模板**，使用代码块包裹
- 模板中用 `[占位符]` 表示动态内容
- 复杂 Skill 可提供多种输出格式（按场景区分）

```markdown
## Output

```
# 会议纪要

**会议主题**：[主题]
**时间**：[日期 时间]
**参会人**：[姓名列表]

## 决议事项
1. [决议内容]

## 待办事项
| 负责人 | 事项 | 截止时间 |
|--------|------|---------|
| [姓名] | [事项] | [日期] |

## 讨论摘要
[关键讨论点，每条 1-2 句话]

---
*由 Goku 自动生成，请核实后归档。*
```
```

---

### § Quality checks
将验收标准、边界情况和禁止行为**合并为一节**，分三个部分：

**部分一：验收标准**（✅ 列表或文字）  
**部分二：边界情况**（表格，情况 + 处理策略）  
**部分三：禁止行为**（❌ 列表）

```markdown
## Quality checks

**验收标准：**
- ✅ 每条待办必须有明确责任人
- ✅ 决议与待办不混淆

**边界情况：**

| 情况 | 处理策略 |
|------|---------|
| **录音质量差，无法识别** | 提示用户提供文字版，不强行生成 |
| **无明确决议** | 输出"本次会议无明确决议"，不留空 |

**禁止行为：**
- ❌ 编造未在原文中出现的决议或待办
- ❌ 在信息不足时跳过追问强行生成
```

---

## 六、Skill 质量等级

| 等级 | 条件 | 状态 |
|------|------|------|
| **⭐⭐⭐ 生产就绪** | 全部 7 章节完整 + frontmatter 5字段齐全 + 有边界情况处理 | 可上线 |
| **⭐⭐ 可用** | 全部 7 章节完整 + frontmatter 5字段齐全 | 可上线，建议补充 |
| **⭐ 草稿** | 章节不完整或 frontmatter 缺字段 | 不可上线 |
| **❌ 不合格** | 缺少 Inputs 章节，或为 auto-generated | 禁止使用 |

---

## 七、新增 Skill 流程

```
1. 确认 Skill 不重复（搜索现有 README）
2. 创建目录：skills/[skill-name]/
3. 编写 SKILL.md（按本标准）
4. 自检：frontmatter 5字段 ✅ + 7章节 ✅ + Inputs ✅
5. 更新 skills/README.md 对应分类表
6. 提交前再过一遍 Quality checks
```

---

## 八、禁止事项（全局）

- ❌ **禁止** 使用 `auto-*` 前缀命名（自动提取的草稿，未经审核不得使用）
- ❌ **禁止** 省略 `## Inputs` 章节（这是 v2.0 核心新增要求）
- ❌ **禁止** 将 `## Edge Cases` 和 `## Don't` 分开写（统一合并为 `## Quality checks`）
- ❌ **禁止** 在 Skill 中写死特定用户名、密码、API Key
- ❌ **禁止** 一个 Skill 承担超过 3 个不同的任务类型（拆分为多个 Skill）
- ❌ **禁止** frontmatter 缺少 `category`、`subcategory`、`tags` 任一字段

---

## 九、版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.0 | 2026-06-09 | 新增 Inputs 章节为强制项；新增 frontmatter category/subcategory/tags 为强制字段；Quality checks 统一合并章节；废弃旧格式（Description/Workflow/Edge Cases/Don't） |
| v1.0 | 2025年初 | 初始版本（7章节但无 Inputs，frontmatter 无分类字段） |
