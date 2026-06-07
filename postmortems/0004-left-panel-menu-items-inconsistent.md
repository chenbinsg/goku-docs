# [0004] 左侧菜单项显示不一致（企业SSO、外部记忆时隐时现）

> **首次发现**：2026-05-28  
> **最近出现**：2026-05-28  
> **状态**：✅ 已修复  
> **关键词**：menu, permissions, sessionStorage, cache, SSO, usePermissions, is_superuser

---

## 症状

左侧导航面板中，「企业 SSO」「外部记忆（外部知识源）」等需要权限的菜单项：

- 刷新页面后短暂消失，数百毫秒后重新出现（闪烁）
- 通过 SSO 登录后永久消失，直到手动刷新
- 后端 `/api/v1/me/permissions` 出现网络抖动时，消失直到下次刷新
- 不同标签页表现不同

---

## 根本原因（共 4 个，相互叠加）

### RC-1：`_cache` 仅存在于 JS 模块内存，刷新后清空（**最核心**）

`usePermissions.ts` 中的 `_cache: Map` 是模块级变量，每次页面刷新都会重置。

初始渲染时 `permissions: []`，所有权限门控项目隐藏，直到 `/api/v1/me/permissions`
异步请求完成（50–500 ms 不等）才恢复显示。

### RC-2：SSO 社交登录回调不返回 `user` 对象

`backend/app/routers/auth.py` 的 `/auth/sso/callback` 端点只返回：
```json
{ "access_token": "...", "refresh_token": "...", "expires_in": 1800 }
```
没有 `user` 字段。前端 `SSOCallback.tsx` 做：
```ts
const { access_token, user } = res  // user = undefined
setAuth(user, access_token, undefined)  // auth store 里 user = undefined
```
结果：`userId = undefined` → `usePermissions` 永远不发起权限请求 →
所有权限门控菜单项对 SSO 用户永久消失。

### RC-3：API 失败时直接降级为空权限，无重试

`.catch()` 块直接写入 `permissions: []`（当 `localIsSuperuser` 为 false 时），
没有任何重试机制。一次网络抖动即导致菜单项永久消失直到下次刷新。

### RC-4：`User` 接口未声明 `is_superuser`（类型缺口）

`frontend/src/stores/auth.ts` 的 `User` 接口没有 `is_superuser` 字段，
导致依赖这个字段的 `usePermissions` 超管快捷路径是隐式的 `(user as any)?.is_superuser`，
任何重构都可能无声地截断这个字段。

---

## 排查路径

```
"有的时候看不见企业SSO和外部记忆"
  ↓
检查 Layout.tsx → adminChildren / aiChildren 按 hasPermission / isAdmin 过滤
  ↓
检查 usePermissions.ts → _cache 是模块内存，刷新即清空
  ↓
发现 loading: true 时 permissions: [] → RC-1 确认
  ↓
检查 SSO callback 后的 user 对象 → auth store 里 user: undefined
  ↓
追溯 /auth/sso/callback 后端响应 → 无 user 字段 → RC-2 确认
  ↓
检查 .catch() 处理 → 直接设 permissions: [] → RC-3 确认
  ↓
检查 User 接口 → 无 is_superuser 声明 → RC-4 确认
```

---

## 修复方案

### RC-1：权限持久化到 sessionStorage

`usePermissions.ts` 新增 sessionStorage 读写层：
- 首次渲染时**同步**从 `sessionStorage('aios-perm-{userId}')` 读取
- 如果有缓存，立即初始化 `loading: false`、菜单完整渲染
- 成功请求后写入 sessionStorage（后续刷新直接命中缓存）
- 仅在 logout 时清除

```ts
// 初始化：memory cache → sessionStorage → superuser shortcut → empty
const mem = _memCache.get(userId)
if (mem) return { ...mem, loading: false }

const stored = _readStorage(userId)
if (stored) {
  _memCache.set(userId, stored)
  return { ...stored, loading: false }
}
```

### RC-2：SSO 社交登录回调添加 `user` 字段

`backend/app/routers/auth.py` 的 SSO callback 响应中增加：
```python
"user": {
    "id": user.id,
    "username": user.username,
    "email": user.email,
    "is_active": user.is_active,
    "is_superuser": user.is_superuser,
    "department": user.department,
},
```
与密码登录、token 刷新端点保持一致。

### RC-3：API 失败时保留已有缓存并自动重试

```ts
.catch(() => {
  const existing = _memCache.get(uid) ?? _readStorage(uid)
  if (!background || !existing) {
    // 第一次请求失败且无任何缓存 — 用超管快捷路径兜底
    setState({ permissions: localIsSuperuser ? ['*'] : [], ... })
  }
  // 有缓存 → 保持当前显示，8 秒后重试
  retryTimerRef.current = setTimeout(() => doFetch(uid, true), 8_000)
})
```

### RC-4：补充类型声明

`frontend/src/stores/auth.ts` `User` 接口增加：
```ts
is_superuser?: boolean
is_active?: boolean
department?: string
```

---

## 防复发机制

| 机制 | 描述 |
|------|------|
| sessionStorage 持久化 | 刷新页面后权限立即从缓存恢复，不再依赖 API 响应速度 |
| SSO 响应统一 | 所有登录端点（密码/SSO/企业SSO/LDAP）均返回包含 `is_superuser` 的 `user` 对象 |
| 失败保留缓存 | API 抖动不降级已显示的菜单，8 s 后静默重试 |
| 类型声明 | `is_superuser` 显式声明，重构时 TypeScript 会保护该字段 |

---

## 关联文件

- `frontend/src/hooks/usePermissions.ts` — sessionStorage 层、重试逻辑
- `frontend/src/stores/auth.ts` — `User` 接口补充 `is_superuser`
- `backend/app/routers/auth.py` — SSO callback 响应补充 `user` 对象
- `frontend/src/components/Layout.tsx` — 菜单项权限过滤逻辑（未修改，读此文件可理解门控规则）

---

## 教训

> **权限数据必须持久化（sessionStorage/localStorage），绝不能只放在 JS 模块内存里；
> 所有登录路径（密码/SSO/企业SSO/LDAP）的响应结构必须完全一致，包含 `user.is_superuser`。**
