# Query matrix

Use these query families when recurring scans need broader but still targeted coverage.

## Telecom families

- `<省名> 中国移动 分公司 招标 短信`
- `<省名> 中国移动 分公司 采购 客服`
- `<城市> 中国移动 质检 招标`
- `<城市> 中国电信 外呼 采购`
- `<城市> 中国联通 AI客服 比选`
- `<省名> 运营商 5G消息 招标`

## Bank families

- `<银行名> 分行 招标 短信`
- `<银行名> 支行 采购 客服`
- `<银行名> 信用卡中心 质检`
- `<银行名> 远程银行中心 外呼`
- `<城市> <银行名> 分行 AI客服`
- `<城市> <银行名> 支行 大模型`

## Fintech families

- `<公司名> 消费金融 招标 短信`
- `<公司名> 消费金融 采购 外呼`
- `<公司名> 催收 采购 质检`
- `<公司名> 客服中心 AI客服`
- `<公司名> 网贷 大模型`
- `<公司名> 电催 短信`

## Expansion strategy

If province-level terms are weak:

- switch to city-level branch names
- switch from `招标` to `采购`, `比选`, `中标候选人`, `中标结果`
- switch from generic `AI` to `客服`, `质检`, `外呼`, `通知`, `消息`

If bank names are too broad:

- add `分行`, `支行`, `信用卡中心`, `远程银行中心`
- add city name before the bank name

If telecom results are too infrastructure-heavy:

- add `客服`, `质检`, `消息`, `外呼`, `AI客服`, `5G消息`
- remove generic cloud-only terms unless there is a communication angle
