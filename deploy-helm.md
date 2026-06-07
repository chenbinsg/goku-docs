# Goku-AIOS Helm Deployment — 5-Minute Quickstart

> Chart: `helm/goku-aios/` | appVersion: 1.9.21 | Kubernetes >= 1.26

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Helm | 3.12 |
| kubectl | matching cluster version |
| Kubernetes cluster | 1.26+ (EKS, GKE, AKS, k3s all work) |
| Ingress controller | nginx-ingress recommended |

---

## Step 1 — Create namespace

```bash
kubectl create namespace aios
```

---

## Step 2 — Generate secrets

```bash
# Generate a random 32-char JWT signing key
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
MYSQL_ROOT_PW=$(python3 -c "import secrets; print(secrets.token_hex(16))")
MYSQL_PW=$(python3 -c "import secrets; print(secrets.token_hex(16))")
```

---

## Step 3 — Install the chart

```bash
helm upgrade --install goku-aios ./helm/goku-aios \
  --namespace aios \
  --set secrets.secretKey="$SECRET_KEY" \
  --set secrets.mysqlRootPassword="$MYSQL_ROOT_PW" \
  --set secrets.mysqlPassword="$MYSQL_PW" \
  --set secrets.openaiApiKey="sk-..." \
  --set ingress.host="aios.yourdomain.com" \
  --wait --timeout=5m
```

That's it. Helm will:
1. Create the `goku-aios-secrets` Secret with all credentials.
2. Provision MySQL and uploads PersistentVolumeClaims.
3. Start MySQL (StatefulSet), Redis, backend, and frontend Deployments.
4. Run Alembic migrations via the `db-migrate` init container before the backend starts.
5. Expose the app via the Ingress at `aios.yourdomain.com`.

---

## Step 4 — Verify

```bash
# All pods Running/Completed
kubectl get pods -n aios

# Backend health
kubectl exec -n aios deployment/goku-aios-backend \
  -- curl -s http://localhost:8106/livez

# Open the UI
open http://aios.yourdomain.com
```

Default admin login: `admin` / (your `secrets.firstAdminPassword`, default `Admin@123456`)

---

## Common overrides

### Use a private container registry

```bash
--set global.imageRegistry=registry.example.com
```

### Pin a specific AIOS version

```bash
--set backend.image.tag=1.9.21 \
--set frontend.image.tag=1.9.21
```

### Enable TLS (cert-manager)

```bash
--set ingress.tls.enabled=true \
--set ingress.tls.secretName=aios-tls
```

Then annotate the Ingress for cert-manager:

```bash
--set 'ingress.annotations.cert-manager\.io/cluster-issuer=letsencrypt-prod'
```

### Scale backend manually (when autoscaling is off)

```bash
--set autoscaling.enabled=false \
--set backend.replicaCount=3
```

### Use an external MySQL / Redis

Simply point the secrets and config at an external endpoint:

```bash
# Disable the bundled MySQL StatefulSet by commenting out pvc-mysql.yaml,
# mysql-statefulset.yaml, and the mysql Service in service-backend.yaml,
# then supply a DATABASE_URL directly:
--set secrets.mysqlPassword="external-pw" \
--set 'backend.env.AUTO_SCHEMA_CREATE=false'
# And set DATABASE_URL via an extra env override in values.yaml
```

---

## Upgrading

```bash
helm upgrade goku-aios ./helm/goku-aios \
  --namespace aios \
  --reuse-values \
  --set backend.image.tag=1.9.22
```

The `db-migrate` init container runs `alembic upgrade head` automatically on every rollout.

---

## Uninstalling

```bash
helm uninstall goku-aios --namespace aios
```

> PersistentVolumeClaims (`goku-aios-mysql-data`, `goku-aios-uploads`) are **not** deleted by default. Delete them manually if you want to wipe all data:
>
> ```bash
> kubectl delete pvc -n aios -l app.kubernetes.io/instance=goku-aios
> ```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Backend CrashLoopBackOff at startup | `kubectl logs -n aios -l app.kubernetes.io/component=backend --previous` — likely a missing secret or DB not yet ready |
| `alembic upgrade head` fails | Verify `secrets.mysqlPassword` is correct; check MySQL pod is Running |
| Ingress returns 404 | Ensure `ingress.host` matches your DNS; verify nginx-ingress is installed |
| SSE events drop after 60s | Add `nginx.ingress.kubernetes.io/proxy-read-timeout: "300"` to ingress annotations (already in defaults) |
| Multi-worker SSE issues | Ensure `REDIS_URL` is set and Redis pod is healthy — events are published in-process by default |
