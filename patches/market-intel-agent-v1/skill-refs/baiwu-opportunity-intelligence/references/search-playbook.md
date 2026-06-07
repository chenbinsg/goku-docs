# Search playbook

This file defines the minimum search behavior for recurring scans.

## Rule

Do not stop after one broad web search. Search in batches across named account pools and named source types. Use the specific platform URLs below before falling back to generic web search.

---

## Priority platforms — visit directly first

### 招标与采购公告平台

| 平台 | URL | 适用范围 |
|---|---|---|
| 中国政府采购网 | https://www.ccgp.gov.cn/ | 政府/国企采购公告与中标结果 |
| 中国招标投标公共服务平台 | https://www.cebpubservice.com/ | 全国招投标公告汇总 |
| 采购云（国采云） | https://www.zcygov.cn/ | 国家统一政府采购平台 |
| 上海联合产权交易所 | https://www.suaee.com/ | 国资招标 |
| 北京市政府采购 | http://www.czj.beijing.gov.cn/ | 北京市级采购 |
| 广东省政府采购 | https://gdgpo.czt.gd.gov.cn/ | 广东省级采购 |

### 运营商专属采购平台

| 平台 | URL | 适用范围 |
|---|---|---|
| 中国移动集中采购 | https://caict.cmcc.com.cn/ （或搜索"中国移动集采"） | 移动集团及省分采购 |
| 中国电信采购与招标网 | https://www.chinatelecom.com.cn/corp/invite/ | 电信集团采购 |
| 中国联通采购招标网 | https://www.chinaunicom.com.cn/about/invite/ | 联通集团采购 |
| 移动各省比选公告 | 搜索 `site:×× 中国移动 比选 <省名>` | 省分比选 |

### 搜索引擎定向招标搜索

```
# 招标文件快速搜索模板（在 web_search 中使用）
"<机构名>" "招标" "短信" site:ccgp.gov.cn
"<机构名>" "比选" "AI客服" site:cebpubservice.com
"中国移动" "<省名>" "采购" "质检" "2025"
"<银行名>" "分行" "招标" "外呼" "2025"
"消费金融" "招标" "智能客服" "大模型"
```

---

## Mandatory account pools

### Pool A: Banks and branches

Priority institutions to monitor:

**国有大行（重点分支）**
- 工商银行、农业银行、建设银行、中国银行、交通银行、邮储银行
- 重点监测：信用卡中心、远程银行中心、客服中心、各省/市分行

**股份制银行**
- 招商银行、浦发银行、中信银行、光大银行、华夏银行、民生银行、兴业银行、平安银行、浙商银行

**城商行（大型）**
- 上海银行、北京银行、江苏银行、宁波银行、南京银行、杭州银行

**搜索关键词组合**：
- `<银行名> <分行/信用卡中心> 招标 短信 2025`
- `<银行名> 采购 智能客服 大模型`
- `<银行名> 比选 外呼 质检`

### Pool B: Telecom operators and branches

**按层级覆盖**：

| 层级 | 搜索策略 |
|---|---|
| 集团集采 | 直接访问运营商采购平台 |
| 省分（重点省） | 搜索"中国移动/电信/联通 <省名> 分公司 招标 2025" |
| 地市分（高价值城市） | 搜索"<城市名> 移动/电信/联通 比选 AI 2025" |

**高优先级省份**：广东、浙江、上海、北京、江苏、四川、福建、山东

**典型关键词**：消息平台 / 短彩信 / 5G消息 / 智能客服 / 数字员工 / 大模型接入 / 质检 / 外呼 / AI运营

### Pool C: Fintech / consumer finance / collections

Priority companies:

- 蚂蚁集团、京东科技、度小满、360数科、乐信、信也科技、小赢科技
- 马上消费金融、招联消费金融、兴业消费金融、中银消费金融
- 催收外包商、客服外包商、AI质检平台商

**搜索关键词组合**：
- `<公司名> 招标 短信 催收 2025`
- `<公司名> 采购 AI客服 知识库`
- `消费金融 招标 外呼 大模型 2025`

---

## Search execution sequence

For each daily scan, execute in this order:

1. **Direct platform scan** (5 min): Visit ccgp.gov.cn + cebpubservice.com, search for 短信/5G消息/AI客服/外呼/质检 + 最近30天
2. **Operator pool** (5 min): Search Pool B top provinces + operator procurement sites
3. **Bank pool** (5 min): Search top 5 banks + city commercial banks for relevant procurement
4. **Fintech pool** (3 min): Search Pool C companies for AI/communication procurement
5. **Web search fallback** (5 min): Use web_search for any pool where platform search returned nothing

Total minimum: 5 search batches across different pools and source types.

---

## Keyword construction

Each search should combine:

- entity name (机构名)
- branch or geography (分行/省市/分公司)
- intent term (招标/采购/比选/中标候选人/中标结果)
- business scenario term (短信/5G消息/外呼/质检/AI客服/大模型/知识库/模型路由)

### Proven query templates

```
# 银行类
"<银行名>" "招标" OR "采购" "短信" OR "外呼" OR "质检" 2025
"<银行名>" "分行" "AI客服" OR "智能客服" OR "数字员工" 2025

# 运营商类
"中国移动" "<省名>" "比选" "AI" OR "5G消息" OR "大模型" 2025
"<运营商>" "<地市>" "采购" "质检" OR "外呼" OR "客服"

# 金融科技类
"消费金融" "招标" "外呼" OR "催收" OR "智能客服" 2025
"<公司名>" "采购" "大模型" OR "AI助理" OR "模型接入"

# 招标平台定向
site:ccgp.gov.cn "5G消息" OR "短信" 2025
site:ccgp.gov.cn "AI客服" OR "智能外呼" 2025
```

---

## Failure rule

If no concrete leads are found after completing the 5-batch sequence, the report must include:

- which account pools were searched (列出哪些机构池)
- which source types and platforms were touched (列出哪些平台和来源类型)
- which query families returned no useful results (列出哪些关键词组合无效)
- specific next-query expansions recommended (提出下一步定向扩展方向)

Do not output "暂无机会，建议继续观察" without this diagnostic.
