#!/usr/bin/env bash
# clean_git_history.sh — 从 git 历史中彻底清除 .env 密钥文件
# 运行前提：pip3 install git-filter-repo
# ⚠️  此操作会重写所有 commit hash，请先备份仓库

set -e

REPO_ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "=== AIOS git 历史清理脚本 ==="
echo "仓库路径: $REPO_ROOT"
echo ""

# 1. 前置检查
if ! command -v git-filter-repo &>/dev/null; then
    echo "❌ 未找到 git-filter-repo，请先安装："
    echo "   pip3 install git-filter-repo"
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "❌ 工作区有未提交的修改，请先 commit 或 stash"
    exit 1
fi

# 2. 备份
BACKUP_DIR="/Users/chenbin/agent_backup_$(date +%Y%m%d_%H%M%S)"
echo "📦 创建备份: $BACKUP_DIR"
cp -r "$REPO_ROOT" "$BACKUP_DIR"
echo "   ✓ 备份完成"

# 3. 执行清理
echo ""
echo "🧹 从历史中移除 .env 文件..."
git filter-repo \
    --path backend/.env \
    --path .env \
    --invert-paths \
    --force

echo "   ✓ 历史清理完成"

# 4. 验证
echo ""
echo "🔍 验证清理结果..."
FOUND=0
git log --all --format="%H" | while read -r hash; do
    if git show "$hash:backend/.env" &>/dev/null 2>&1; then
        echo "   ⚠️  仍在 $hash 中发现 backend/.env"
        FOUND=1
    fi
    if git show "$hash:.env" &>/dev/null 2>&1; then
        echo "   ⚠️  仍在 $hash 中发现 .env"
        FOUND=1
    fi
done

if [ "$FOUND" -eq 0 ]; then
    echo "   ✓ 所有历史 commit 中已无 .env 文件"
fi

echo ""
echo "=== 完成 ==="
echo "⚠️  请务必在清理后轮换所有密钥（见 security/P0_S1_key_rotation.md）"
