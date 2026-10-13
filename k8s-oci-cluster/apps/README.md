# GitOps Apps

> [!NOTE]
> **Retired 2026-10** together with the OCI cluster; these manifests are kept as reference.

Argo CD watches this directory through the app-of-apps configuration in `platform/argocd.tf`.

## Prepared apps

- `ollama-router.yaml` -> `ollama-router/`: internal-only Ollama router service using a Tailscale sidecar. Public manifests contain no Tailnet endpoints or API/auth keys; private bootstrap files live under `ollama-router/config/` and non-example config files are ignored by Git. Reusable app code lives in [`maslankalm/ollama-router`](https://github.com/maslankalm/ollama-router).
- `k8s-manifest-reviewer.yaml` -> `k8s-manifest-reviewer/`: public Kubernetes manifest reviewer demo using `gpt-oss:20b` through the in-cluster Ollama router and Cloudflare-proxied Ingress. The Ingress caps request bodies at `16k` because the app only accepts small demo manifests. Reusable app code lives in [`maslankalm/k8s-manifest-reviewer`](https://github.com/maslankalm/k8s-manifest-reviewer).

Add one subdirectory or Application manifest per workload when a service is ready to run on the OCI cluster.
