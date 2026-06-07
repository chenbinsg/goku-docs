# [0006] 非管理员进入 AI 对话页后，左侧 sidebar 暴露全部管理员菜单

> **首次发现**：2026-05-28
> **最近出现**：2026-05-28
> **状态**：✅ 已修复
> **关键词**：rbac, permissions, sidebar, ChatLayout, CollapsibleSidebar, usePermissions

---

## 症状

非管理员用户登录后：

1. 默认进入 `Layout` 包裹的页面（如 `/dashboard`），左侧菜单**正确过滤**——只看到本人有权限的项
2. 一旦点击「AI 对话」（路径 `/` 或 `/chat`），进入 `ChatLayout`，左侧的 `CollapsibleSidebar`：
   - 点齿轮图标展开「系统管理」抽屉
   - **看到全部管理员菜单**：用户管理、角色管理、审计日志、企业 SSO、系统配置、连接器配置、智能体身份……

用户原话：

> 非Admin用户登陆，也能看到很多不该看到的功能。一个现象是正常登陆看不到所有的menu items，一旦click AI对话，就能看到所有的功能。

---

## 根本原因

`frontend/src/components/CollapsibleSidebar.tsx` 中的 `adminMenuItems` 是**完全硬编码**的，没有调用 `usePermissions()`，没有任何 `hasPermission()` 过滤。源代码注释甚至明确说"Mirrors Layout.tsx menuItems… single source of truth pending a shared nav config refactor; when editing, keep both files in sync"——也就是**作者知道两边应该同步，但只是写了 mirror，忘了 mirror 过滤逻辑**。

Layout.tsx 的同名菜单则正确使用了 `hasPermission()`：

```ts
// Layout.tsx — 正确
hasPermission('users.read') && { key: '/users', label: '用户管理' }

// CollapsibleSidebar.tsx — 错误
{ key: '/users', label: '用户管理' }   // 所有人都看得到
```

后端 API 本身有 `require_permission` 装饰器，所以即使非管理员点进去也拿不到敏感数据；但**菜单暴露本身就是 RBAC 漏洞**——它让普通用户：
- 误以为有权限去做这些事
- 看到系统的完整能力图谱（提供攻击面侦察便利）
- 体验到一堆 403，破坏信任感

---

## 排查路径

```
"非 admin 登陆能看到不该看到的功能 ... click AI对话就能看到所有功能"
  ↓
猜测 1：usePermissions 在 ChatPage 中被错误清空 → 排除（hook 状态自洽）
  ↓
猜测 2：路由切换时权限缓存被污染 → 排除（_memCache 只在登出时 clear）
  ↓
检查 ChatLayout 用的是哪个 sidebar → 发现 CollapsibleSidebar，而非 Layout.tsx 的 Sider
  ↓
读 CollapsibleSidebar.tsx → 发现 adminMenuItems 完全硬编码
  ↓
对比 Layout.tsx → 后者用 hasPermission 严格过滤
  ↓
确认这是「两份菜单实现，但只有一份做了 RBAC」的经典漂移问题
```

---

## 修复方案

### 1. CollapsibleSidebar 引入 `usePermissions`

```ts
import { usePermissions } from '../hooks/usePermissions'

const { hasPermission, isSuperuser: isAdmin } = usePermissions()
```

### 2. 重建 `aiChildren` / `adminChildren` 数组，使用与 `Layout.tsx` 完全一致的过滤门控

```ts
const aiChildren = [
  { key: '/agents', label: ... },                            // 所有人
  hasPermission('agents.write') && { key: '/agents/runtime', ... },
  hasPermission('tools.read')   && { key: '/tools',   ... },
  hasPermission('models.manage')&& { key: '/models',  ... },
  // ...
].filter(Boolean)

const adminChildren = [
  hasPermission('system.config.write') && { key: '/system/soul', ... },
  hasPermission('users.read')          && { key: '/users',       ... },
  hasPermission('roles.read')          && { key: '/roles',       ... },
  hasPermission('audit.logs.read')     && { key: '/audit/logs',  ... },
  isAdmin                              && { key: '/admin/sso',   ... },
  // ...
].filter(Boolean)
```

### 3. 顶层菜单数组里把"扩展 / 数据分析 / 系统管理"等都条件展开

```ts
...(hasPermission('mcp.manage')        ? [{ key: '/mcp', ... }]        : []),
...(hasPermission('connectors.manage') ? [{ key: '/connectors', ... }] : []),
...(hasPermission('costs.read')        ? [
   { key: '/analytics', ... },
   { key: '/billing',   ... },
   { type: 'divider' }
] : []),
...(adminChildren.length > 0 ? [{ key: 'admin', children: adminChildren }] : []),
```

### 4. 当用户对「系统管理」整段无权限时，**隐藏齿轮图标**本身

否则非管理员仍会看到一个空抽屉，体验诡异。

```ts
const showAdminColumn = adminMenuItems.some(item => item && !('type' in item))
{showAdminColumn && (<Tooltip ...><Button icon={<SettingOutlined />} .../></Tooltip>)}
```

---

## 防复发机制

| 机制 | 说明 |
|------|------|
| **Lint/CI 规则建议** | 在 `frontend` 增加自定义 ESLint 规则，禁止在 menu/sidebar 文件里出现未过滤的 `key: '/users'`、`key: '/audit'` 等敏感路径（短期可用 grep 兜底） |
| **复盘 #0006 强制阅读** | 把 CollapsibleSidebar / Layout / 其他 sidebar/menu 加入 CLAUDE.md "修改前必读"列表 |
| **菜单单一来源（计划）** | 长期方案：把 menu 定义抽到一个 `nav-config.ts`，所有 sidebar 共享同一份带 `requiredPermission` 字段的配置，渲染时统一 `.filter(item => !item.requiredPermission \|\| hasPermission(...))` |
| **新增菜单项必须同步两处** | 每次向 `Layout.tsx` 的 `aiChildren` / `adminChildren` / `menuItems` 新增条目，必须**同时**在 `CollapsibleSidebar.tsx` 对应位置添加相同条目（含 permission gate）。2026-05-28 再次触发：新增 `外部记忆`、`语音质检`、`租户管理`、`部门管理`、`组织架构`、`竹云用户同步`、`开放 API Keys` 只加了 Layout 未加 CollapsibleSidebar。 |
| **回归测试（计划）** | 增加 React Testing Library 测试：非超管 user，点开 admin 抽屉，断言菜单数组里 `/users`、`/audit/logs`、`/admin/sso` 等不存在 |

---

## 关联文件

- `frontend/src/components/CollapsibleSidebar.tsx` — 本次修复主体
- `frontend/src/components/Layout.tsx` — 正确实现，作为对照基准
- `frontend/src/hooks/usePermissions.ts` — 权限源（复盘 #0004 修复后正确持久化）
- `docs/复盘记录/0004-left-panel-menu-items-inconsistent.md` — 上一次同领域复盘

---

## 教训

> **任何渲染菜单或导航链接的组件都必须从 `usePermissions()` 出发，不允许出现硬编码的敏感路径数组。**
> 即使后端有权限装饰器，UI 上的暴露依然是 RBAC 漏洞——它泄漏能力图谱、误导用户、并破坏整个分级访问的信任契约。
