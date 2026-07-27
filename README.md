# AI Lab

A working repository for AI-assisted engineering across DevOps, Kubernetes, homelab automation, and LLM-powered tools.

The repo is built around real systems rather than isolated demos: an OCI Always Free GitOps cluster, a Tailscale-connected homelab with peer agent control planes, local GPU inference, and a live LLM-backed Kubernetes review app. The [homelab/](homelab/) directory is the meta view: current architecture plus a public-safe changelog of infrastructure changes.

## Live Demo

### [Try the Kubernetes Manifest Reviewer →](https://k8s-manifest-reviewer.maslanka.io)

Paste a small Kubernetes manifest and get an AI-assisted security/reliability review. The public app runs on the OCI Kubernetes cluster, calls the in-cluster [`ollama-router`](https://github.com/maslankalm/ollama-router), and routes `gpt-oss:20b` inference to a local RTX 2080 Ti with Ollama Cloud free-tier fallback.

## Repo Map

```mermaid
flowchart LR
    REPO["ai-lab"]
    HOMELAB["homelab<br/>AI operations + local compute"]
    K8S["k8s-oci-cluster<br/>OCI Always Free GitOps"]
    REVIEWER["k8s-manifest-reviewer<br/>live Kubernetes YAML review"]
    ROUTER["ollama-router<br/>LLM backend routing"]
    CLOUDLLM["Ollama Cloud<br/>fallback inference"]

    AGENTS["OpenClaw + Hermes<br/>agent control planes"]
    LAB["Tailnet inference<br/>RTX 2080 Ti primary"]

    REPO --> HOMELAB
    REPO --> K8S
    K8S --> REVIEWER
    K8S --> ROUTER
    HOMELAB --> AGENTS
    HOMELAB --> LAB
    REVIEWER --> ROUTER
    ROUTER --> LAB
    ROUTER --> CLOUDLLM
```

## AI-assisted engineering

This repo started with Claude Code, then moved to OpenAI Codex with GPT-5.5 after practical comparison in daily use. Codex is now the main coding and operations assistant. Claude remains available through `opus-expert`, exposed through an OpenAI-compatible REST API and connected to OpenClaw as a model for critical review, second opinions, and deeper critique.

The human part is still the important part: architecture, requirements, tradeoffs, operations, and review. AI makes the implementation loop faster, but the work is grounded in infrastructure that actually runs.

## Start Here

| Area | What to inspect |
|---------|-------------|
| [homelab](homelab/) | Current AI operations architecture, Tailscale-connected Windows GPU rigs, Rigwarden wake/status control, and the public changelog showing how the lab evolved. |
| [k8s-oci-cluster](k8s-oci-cluster/) | Terraform-managed OCI Always Free Kubernetes cluster with nginx ingress, external-dns, cert-manager, Argo CD GitOps, internal `ollama-router`, and the public manifest reviewer app. |
| [ollama-router](https://github.com/maslankalm/ollama-router) | Standalone OpenAI-compatible FastAPI router for Ollama backends. This repo carries the OCI/Argo CD deployment manifests under `k8s-oci-cluster/apps/ollama-router`; the app code and GHCR image live in the separate public repository. |
| [k8s-manifest-reviewer](https://github.com/maslankalm/k8s-manifest-reviewer) | Public demo app that reviews Kubernetes YAML with `gpt-oss:20b`, local RTX 2080 Ti inference, and Ollama Cloud free-tier fallback through `ollama-router`. Deployment manifests live under `k8s-oci-cluster/apps/k8s-manifest-reviewer`. |
