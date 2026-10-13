# Kubernetes Manifest Reviewer GitOps app

> [!NOTE]
> **Retired 2026-10.** The demo went offline when the OCI cluster was torn down. The app
> code stays in [`maslankalm/k8s-manifest-reviewer`](https://github.com/maslankalm/k8s-manifest-reviewer); these manifests are kept as reference.

Public demo deployment for [`ghcr.io/maslankalm/k8s-manifest-reviewer:main`](https://github.com/maslankalm/k8s-manifest-reviewer).

Was live at `k8s-manifest-reviewer.maslanka.io` until 2026-10.

The app reviews small Kubernetes YAML manifests with `gpt-oss:20b` and calls the in-cluster `ollama-router` service:

```text
k8s-manifest-reviewer -> ollama-router -> local RTX 2080 Ti / Ollama Cloud free-tier fallback
```

Related docs: [`../README.md`](../README.md) lists all GitOps apps, and [`../../../homelab/README.md`](../../../homelab/README.md) explains the Tailnet/local GPU side of the setup.

## Manifests

- `namespace.yaml` — app namespace
- `deployment.yaml` — single demo replica, no app secrets required
- `service.yaml` — internal `ClusterIP`
- `ingress.yaml` — Cloudflare-proxied public Ingress with cert-manager TLS

The Ingress sets `nginx.ingress.kubernetes.io/proxy-body-size: "16k"` so oversized form posts are rejected before they reach FastAPI. The app itself also limits custom manifests to 6,000 characters and 150 lines.

## Runtime config

The deployment uses only non-secret environment variables:

- `OLLAMA_ROUTER_URL` points at the internal `ollama-router` Kubernetes Service; see `deployment.yaml` for the exact cluster DNS value.
- `OLLAMA_MODEL=gpt-oss:20b`
- `LLM_REVIEW_ATTEMPTS=3`
- `RATE_LIMIT_REQUESTS=3`
- `RATE_LIMIT_WINDOW_SECONDS=300`

Ollama Cloud credentials and private backend endpoints stay inside the `ollama-router` app config, not this public demo app.
