# Application Layer

> [!NOTE]
> **Retired 2026-10** together with the OCI cluster. The status below is the state at retirement.

Argo CD is configured with an app-of-apps entry pointing at [`../apps/`](../apps/). Adding an Application manifest there and pushing to Git is the intended deployment path: Argo CD picks it up, applies it, self-heals drift, and prunes removed resources.

## Status at Retirement

`ollama-router` is the internal inference gateway. It is intentionally `ClusterIP`-only: no public ingress, no load balancer, and no router auth in front of it. Backend endpoints and API/auth keys are supplied by private Kubernetes Secrets created from ignored app-local `config/` files, not public GitOps files.

`k8s-manifest-reviewer` is the first public demo workload. It exposes a Cloudflare-proxied Ingress at `k8s-manifest-reviewer.maslanka.io`, calls `ollama-router` through the in-cluster service DNS name, runs `gpt-oss:20b`, and sets `nginx.ingress.kubernetes.io/proxy-body-size: "16k"` so oversized manifests are rejected before they reach the FastAPI form parser.

App inventory at retirement:

- `ollama-router` — namespace `ollama-router`, internal `ClusterIP`, no public Ingress, routes to local RTX 2080 Ti first with Ollama Cloud free-tier fallback.
- `k8s-manifest-reviewer` — namespace `k8s-manifest-reviewer`, public URL `k8s-manifest-reviewer.maslanka.io` (offline since 2026-10), model `gpt-oss:20b`, app limits 6,000 characters / 150 lines and Ingress body cap `16k`.

No monitoring stack is currently managed here; app manifests should stay lightweight and explicit.

## Deployment Contract

When apps are added, they should follow the same pattern:

- Application manifests live under `k8s-oci-cluster/apps`.
- App-specific runtime config lives under that app's `config/` directory: commit `.example` templates, ignore filled files without the `.example` suffix, and apply those local files before syncing the app.
- Platform Terraform is reserved for cluster core secrets/components, not per-app runtime secrets.
- Public ingress should stay behind Cloudflare and use cert-manager TLS.
- Resource requests should be realistic for the ARM free-tier nodes.
- Anything too heavy for the free tier should move back to the homelab or be removed rather than quietly degrading the cluster.
