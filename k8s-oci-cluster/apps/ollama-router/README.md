# Ollama Router GitOps app

Internal-only `ClusterIP` deployment for `ghcr.io/maslankalm/ollama-router:main`.

The public GitOps manifests intentionally do **not** include backend endpoints, Tailnet topology, Tailscale auth keys, or Ollama Cloud API keys. Runtime config is supplied by pre-created Kubernetes Secrets:

- `ollama-router-config` with key `config.yaml`
- `ollama-router-secrets` with keys `TS_AUTHKEY` and `OLLAMA_CLOUD_API_KEY`

The Deployment runs a Tailscale sidecar in kernel/TUN mode and advertises `tag:k8s`. Tailnet ACLs must allow `tag:k8s` to reach inference rigs on `11434`. In the live demo path, the router serves `gpt-oss:20b` from the local RTX 2080 Ti backend first and uses Ollama Cloud free tier as fallback.

Related docs: [`../README.md`](../README.md) lists all GitOps apps, and [`../../../homelab/README.md`](../../../homelab/README.md) explains the Tailnet/local GPU side of the setup.

## Private config workflow

`config/` contains both committed examples and ignored real local files:

- commit: `config/secrets.yaml.example`
- commit: `config/router-config-secret.yaml.example`
- ignore: `config/secrets.yaml`
- ignore: `config/router-config-secret.yaml`

Prepare local config:

```bash
cp k8s-oci-cluster/apps/ollama-router/config/secrets.yaml.example \
  k8s-oci-cluster/apps/ollama-router/config/secrets.yaml
cp k8s-oci-cluster/apps/ollama-router/config/router-config-secret.yaml.example \
  k8s-oci-cluster/apps/ollama-router/config/router-config-secret.yaml
# edit config/secrets.yaml and config/router-config-secret.yaml with real values
```

Create/update the namespace and required Secrets before Argo CD syncs this app. The Secret files set `metadata.namespace: ollama-router`, but Kubernetes still requires that namespace to exist first:

```bash
export KUBECONFIG=~/.kube/k8s-oci-cluster-config
kubectl apply -f k8s-oci-cluster/apps/ollama-router/namespace.yaml
kubectl apply -f k8s-oci-cluster/apps/ollama-router/config/secrets.yaml
kubectl apply -f k8s-oci-cluster/apps/ollama-router/config/router-config-secret.yaml
```

Do not commit non-example files under `config/`.
