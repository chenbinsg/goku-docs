# Goku Auth Bridge Protocol

> Cross-service JWT handoff between goku-core and goku-studio

---

## Problem

goku-core and goku-studio are separate frontend origins (`:5106` vs `:5107`).
`localStorage` is not shared across origins, so a user authenticated in goku-core
has no session in goku-studio — they would be redirected to a login page.

We solve this with a **URL token bridge**: the sending service appends the JWT to the
destination URL. The receiving service reads, hydrates, and immediately strips it.

---

## Protocol

### Step 1 — Sender appends tokens to URL

**goku-core → goku-studio** (via `StudioRedirect` component or sidebar links):

```
http://localhost:5107/agents?_token=<jwt>&_refresh_token=<rt>
```

**goku-studio → goku-core** (via "Return to Runtime" button):

```
http://localhost:5106/chat?_token=<jwt>&_refresh_token=<rt>
```

The `_token` and `_refresh_token` query params carry the same tokens that are
already stored in the sender's Zustand auth store.

### Step 2 — Receiver hydrates auth store

On first load, `main.tsx` runs a bootstrap function **before** React renders:

```typescript
(function bootstrapAuthBridge() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('_token')
  const refreshToken = params.get('_refresh_token')

  if (token) {
    try {
      // Decode JWT payload (base64url, no verification — backend already verified it)
      const payload = JSON.parse(
        atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
      )
      const user = {
        id:           payload.user_id || payload.sub,
        username:     payload.username || payload.sub,
        email:        payload.email || '',
        roles:        payload.roles || [],
        is_superuser: payload.is_superuser ?? false,
        is_active:    true,
        department:   payload.department,
        tenant_id:    payload.tenant_id,
      }
      useAuthStore.getState().setAuth(user, token, refreshToken || undefined)
    } catch {
      // Malformed token — ignore, user will hit PrivateRoute and be redirected to login
    }

    // Step 3 — Strip tokens from URL
    params.delete('_token')
    params.delete('_refresh_token')
    const qs = params.toString()
    window.history.replaceState(
      {},
      '',
      window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash
    )
  }
})()
```

### Step 3 — Tokens stripped from URL

`window.history.replaceState` rewrites the URL **without** the token params.
This means:
- Tokens never appear in browser history
- Refresh/bookmark after hydration works normally (no double-hydration)
- Copy-pasting the URL does not leak tokens

---

## Implementation Locations

| File | Role |
|------|------|
| `goku-core/frontend/src/App.tsx` — `StudioRedirect` component | Appends tokens when React Router navigates to a `/agents`, `/workflows`, etc. route |
| `goku-core/frontend/src/components/Layout.tsx` — `studioHref()` | Appends tokens to sidebar Studio links |
| `goku-core/frontend/src/components/CollapsibleSidebar.tsx` — `studioHref()` | Same, for the chat-page collapsed sidebar |
| `goku-studio/frontend/src/main.tsx` — `bootstrapAuthBridge()` | Reads + hydrates + strips on Studio load |
| `goku-studio/frontend/src/App.tsx` — `PrivateRoute` | Redirects to `VITE_RUNTIME_URL/login` if no auth after bridge runs |
| `goku-studio/frontend/src/components/StudioLayout.tsx` — `goToRuntime()` | Appends tokens when returning to goku-core |

---

## Security Properties

| Property | How it's achieved |
|----------|-------------------|
| Tokens not stored in browser history | `history.replaceState` strips params immediately after hydration |
| No cross-origin cookie issues | URL params work across origins; no `SameSite` / CORS issues |
| No extra backend round-trip | JWT is self-contained; receiver decodes payload locally |
| Token validity | Backend still enforces expiry on every API call — bridge only copies a token, it does not extend it |
| Refresh token rotation | `_refresh_token` is also bridged so the receiving app can silently renew the access token |

### What this does NOT protect against

- **Shoulder surfing** — token is briefly visible in the address bar during navigation
- **Referrer header leakage** — if the destination page loads third-party resources, the `Referer` header may include the token. Mitigate with `<meta name="referrer" content="no-referrer">` in Studio's `index.html` if needed.
- **Very long-lived tokens** — if `ACCESS_TOKEN_EXPIRE_MINUTES` is large, a leaked URL token has a longer window. Keep expiry short (≤ 60 min) and rely on refresh tokens for session continuity.

---

## Configuration

### goku-core `.env` / `frontend/.env`
```
VITE_STUDIO_URL=http://localhost:5107
```

### goku-studio `.env` / `frontend/.env`
```
VITE_RUNTIME_URL=http://localhost:5106
```

Both values must be set to the **browser-visible** origin of the target service
(i.e., what the user's browser navigates to — not a Docker-internal hostname).

---

## Sequence Diagram

```
User (browser)          goku-core :5106        goku-studio :5107
     │                       │                        │
     │  click "Agents"        │                        │
     │──────────────────────►│                        │
     │                       │  StudioRedirect        │
     │                       │  builds URL +_token    │
     │◄──────────────────────│                        │
     │  redirect to :5107/agents?_token=JWT            │
     │────────────────────────────────────────────────►│
     │                                                 │  bootstrapAuthBridge()
     │                                                 │  hydrate auth store
     │                                                 │  history.replaceState (strip)
     │                                                 │  render <App>
     │◄────────────────────────────────────────────────│
     │  :5107/agents  (no token in URL)                │
     │                                                 │
     │  click "Return to Runtime"                      │
     │────────────────────────────────────────────────►│
     │                                                 │  goToRuntime() builds URL +_token
     │◄────────────────────────────────────────────────│
     │  redirect to :5106/chat?_token=JWT              │
     │──────────────────────►│                         │
     │                       │  (same bootstrap if needed)
```
