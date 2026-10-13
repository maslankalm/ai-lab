# Kubernetes on OCI Always Free

> [!NOTE]
> **Retired 2026-10.** The OCI cluster has been torn down and the public demo is offline.
> This directory is kept as working reference configuration: the Terraform and Argo CD
> setup below can still bring up the same Always Free cluster.

Terraform-managed Kubernetes platform built around Oracle Cloud's Always Free tier. The goal is to keep a real GitOps cluster online at near-zero cost while still using production-shaped building blocks: managed Kubernetes, ingress, DNS automation, TLS, and Argo CD.

The Terraform code is reusable: with an OCI account, Cloudflare zone, and the documented variables, another operator can use this directory to bring up their own Always Free Kubernetes cluster.

## What This Shows

- **Cost-aware cloud architecture** — OKE control plane, ARM worker nodes, and a small OCI load balancer sized for the free-tier envelope.
- **Terraform separation of concerns** — base cloud infrastructure lives in `infrastructure/`; cluster add-ons live in `platform/`.
- **GitOps operating model** — Argo CD is bootstrapped by Terraform and watches the repo for application manifests.
- **Public-safe secret handling** — platform/core secrets stay in Terraform; app-specific secrets use each app's ignored `config/` files plus committed `.example` templates.
- **Cloudflare-backed edge** — ingress traffic is restricted to Cloudflare CIDRs, DNS is automated by external-dns, and TLS is issued with cert-manager DNS-01 challenges.

## Architecture

Oracle Cloud's [Always Free tier](https://www.oracle.com/cloud/free/) is one of the most generous cloud offers available for experimenting — especially for compute. The OKE (Oracle Kubernetes Engine) control plane is always free, and the Ampere A1 ARM shapes provide solid resources at no cost.

Inspired by [nce/oci-free-cloud-k8s](https://github.com/nce/oci-free-cloud-k8s), rewritten with additional documentation and configuration changes.

- **Engine:** Oracle Kubernetes Engine (OKE) — free managed control plane
- **Worker nodes:** 2 nodes, each with 2 OCPUs / 12 GB RAM / 100 GB block storage (NVMe SSD)
- **Shape:** VM.Standard.A1.Flex (ARM Ampere A1, from the Always Free allocation of 4 OCPUs / 24 GB RAM)
- **Ingress:** nginx ingress controller with an OCI free-tier load balancer (Cloudflare-only source IPs)
- **DNS:** external-dns with Cloudflare provider for automatic DNS record management (proxied mode)
- **TLS:** cert-manager with Let's Encrypt certificates via Cloudflare DNS-01 challenge — enables Cloudflare Full (Strict) TLS mode for end-to-end encryption
- **GitOps:** Argo CD for continuous deployment from Git

The application layer is intentionally small but now runs real workloads: an internal `ollama-router` inference gateway and the public [Kubernetes Manifest Reviewer](https://k8s-manifest-reviewer.maslanka.io) demo. The reviewer uses `gpt-oss:20b` through the router, preferring local RTX 2080 Ti inference and falling back to Ollama Cloud free tier. The platform keeps the GitOps path lightweight and avoids monitoring-stack leftovers until they are actually needed.

See [Prerequisites](docs/prerequisites.md) before running Terraform.

## Usage

### 1. Deploy the infrastructure

```bash
cd infrastructure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your compartment_id and k8s_api_source_ip
terraform init
terraform apply
```

`terraform apply` creates a kubeconfig file at `~/.kube/k8s-oci-cluster-config`. Use it to interact with the cluster:

```bash
export KUBECONFIG=~/.kube/k8s-oci-cluster-config
kubectl get nodes
```

> [!TIP]
> **A1 capacity availability** — Free-tier A1 instances share a limited capacity pool and `terraform apply` may fail with an "Out of capacity" error. Consider upgrading to **Pay As You Go (PAYG)** — it uses the regular capacity pool while Always Free limits still apply.

> [!TIP]
> **Extending worker node drives** — OCI worker nodes don't use the full boot volume by default. Run `/usr/libexec/oci-growfs -y` on each node (e.g. via a shell session in [Lens](https://k8slens.dev/)).

![Cluster viewed in Lens](k8s-oci-cluster-lens.png)

### 2. Deploy platform services

Deploys the nginx ingress controller (with an OCI free-tier load balancer), external-dns for automatic Cloudflare DNS management, cert-manager for automatic TLS certificates, and Argo CD. See [Platform Components](docs/platform.md) for details.

```bash
cd platform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your domain, email, and required platform secrets
terraform init
terraform apply -target=helm_release.cert_manager  # first time only, installs CRDs
terraform apply
```

> [!NOTE]
> The first apply requires `-target=helm_release.cert_manager` because Terraform validates custom resources (like `ClusterIssuer`) against the cluster's CRDs at plan time. Once cert-manager is installed, subsequent applies work normally.

### 3. Deploy applications via GitOps

ArgoCD watches the `apps/` directory and automatically syncs applications to the cluster. Add Application manifests there and push to Git — ArgoCD picks them up, applies them, and prunes removed resources. See [Applications](docs/apps.md) for details.

Application manifests are managed by Argo CD. If an app needs private runtime config, follow that app's `config/` workflow first: copy the committed `.example` files to same-name local files without the `.example` suffix, fill real values, and apply those ignored local files before syncing the app.

```bash
# App manifests are managed by Argo CD.
# App private config is created from each app's ignored config/*.yaml files.
# Add/review manifests under apps/ and push when ready.
```
