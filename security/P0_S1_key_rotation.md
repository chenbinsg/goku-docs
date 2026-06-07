# P0-S1 密钥泄露事件报告

**发现时间：** 2026-04-27  
**严重等级：** 🔴 严重  
**当前状态：** 密钥已从 git 追踪中移除，但仍存在于历史记录中，需立即轮换

---

## 事件摘要

git 历史中有 **7 个 commit** 包含明文密钥（初始提交 `72437583` 至 `41700266`）。
虽然 commit `29fb42d5` 已将 `.env` 文件从追踪中移除，但旧 commit 的快照仍可通过
`git show <commit>:backend/.env` 读取。

**好消息：** 本仓库目前无 remote，密钥从未推送到公网。风险范围仅限于本机访问者。

---

## 需要立即轮换的密钥

| 密钥 | 泄露途径 | 轮换方法 |
|------|---------|---------|
| `OPENAI_API_KEY` | git history (7 commits) | https://platform.openai.com/api-keys → 删除旧 key → 创建新 key |
| `ANTHROPIC_API_KEY` | git history (7 commits) | https://console.anthropic.com/settings/keys → Revoke → Create |
| `SMTP_PASS` | git history (7 commits) | 邮件账户 chuck.chen@netstars.co.jp → 修改密码或 App Password |
| `SECRET_KEY` | git history (旧值 `aipipe-deploy-app_26`) | 已在 .env 中更新为新值，需重启服务使旧 JWT 失效 |
| `DATABASE_URL` (password) | git history (root:123456) | MySQL: `ALTER USER 'root'@'localhost' IDENTIFIED BY 'NEW_PASS';` |
| `AIBI_TOKEN` | 当前 .env | 登录 AIBI 平台 → 重新生成 Token |
| `CNIPA_PASSWORD` | 当前 .env | 登录 CNIPA 系统修改密码 |

---

## 清理 git 历史（可选，推荐）

由于仓库无 remote，清理历史可彻底消除风险。执行前请确保所有工作已提交。

### 方法 A：安装 git-filter-repo（推荐）

```bash
pip3 install git-filter-repo

# 备份当前仓库
cp -r /Users/chenbin/agent /Users/chenbin/agent_backup_$(date +%Y%m%d)

# 从所有历史中删除 .env 文件
cd /Users/chenbin/agent
git filter-repo --path backend/.env --path .env --invert-paths --force

# 验证清理结果
git show 72437583:backend/.env 2>&1 || echo "✓ 已从历史中移除"
```

### 方法 B：git replace（不改写历史，仅本地屏蔽）

```bash
# 不推荐——仍可通过 git log --all 看到旧 commit
```

### 清理后验证

```bash
git log --all --oneline | while read hash rest; do
    if git show "$hash:backend/.env" &>/dev/null; then
        echo "FOUND in $hash"
    fi
done
echo "Scan complete"
```

---

## 已完成的防护措施

- [x] `backend/.env` 加入 `.gitignore`（`backend/.env` 和 `*.env`）
- [x] `.env.example` 提供无密钥模板
- [x] 当前工作树 `backend/.env` 已不被 git 追踪

## 待完成

- [ ] 按上表轮换所有密钥
- [ ] 执行 git-filter-repo 清理历史
- [ ] 若将来要 push 到 remote，必须先完成历史清理
