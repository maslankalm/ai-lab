# Homelab Changelog

Reverse-chronological record of every change to the homelab: cluster updates, new apps, Raspberry Pi work, networking, and AI/learning milestones.

---

## 2026-05-19

### Hermes promoted as the primary AI Lab control plane

- **What** — Decided to consolidate daily agent operations around Hermes and retire OpenClaw from the active path. OpenClaw remains useful as historical context, but Hermes is now the main operating surface because it is faster to iterate on and less fragile during upgrades.
- **Why** — The lab needs one dependable control plane for Discord-first operations, Kanban-style coordination, scheduled work, and local tooling access. Reducing the active agent surface also keeps upgrades and debugging simpler.

### Hermes upgraded for SuperGrok OAuth and frontier-model fallback

- **What** — Upgraded Hermes to the latest available release and configured SuperGrok / xAI OAuth support. SuperGrok is now the second frontier-model backend, with GPT-5.5 kept as the primary/default path and fallback behavior available if OpenAI has issues.
- **Why** — This gives the lab two subscription-backed frontier model families instead of depending on a single provider, while avoiding separate API-key plumbing for the SuperGrok path.

### Hermes proxy added as an OpenAI-compatible SuperGrok endpoint

- **What** — Added a dedicated `hermes-proxy` container to the Hermes Compose stack and exposed a local OpenAI-compatible `/v1` endpoint backed by the SuperGrok OAuth session. Health checks confirmed the proxy was authenticated and serving xAI model metadata.
- **Why** — Local tools can now point at a subscription-backed OpenAI-compatible endpoint instead of each app needing its own xAI integration. This keeps the proxy as normal Compose-managed infrastructure rather than an ad hoc process inside another service.

### Qwen3.6-35B-A3B running on RTX 2080 Ti via llama.cpp

- **What** — Brought up `Qwen3.6-35B-A3B` `UD-Q4_K_M` on the `rtx-i7` / RTX 2080 Ti rig with CUDA-backed `llama.cpp`, 8K context, automatic GPU-layer fitting, Flash Attention, q8 KV cache, and hybrid RAM + partial GPU offload.
- **Why** — The 11 GB RTX 2080 Ti cannot hold the whole 35B-class GGUF in VRAM, but the Windows Docker Desktop / WSL2 host has enough system RAM for a useful hybrid local-model playground.
- **Result** — The model loaded near the safe VRAM edge at roughly 10.27 GiB used / 0.75 GiB free. Warm requests measured about **17.6–22.5 generated tokens/s**, with prompt evaluation ranging from roughly **49 tok/s** on short prompts to **~265 tok/s** on a medium cached prompt. Vision projector support stays deferred until the text path is stable.

## 2026-05-15

### Kubernetes Manifest Reviewer public demo deployed

- **What** — Deployed the Kubernetes Manifest Reviewer as the first public demo workload on the OCI GitOps cluster. The app is served at <https://k8s-manifest-reviewer.maslanka.io> through Cloudflare-proxied nginx Ingress with cert-manager TLS, a `16k` ingress body cap, and Argo CD app-of-apps management.
- **Why** — Turns the AI Lab infrastructure into a usable portfolio demo: a real Kubernetes app running on the public cluster, using local RTX 2080 Ti inference through `ollama-router` with Ollama Cloud free-tier fallback.

### Ollama router connected cluster apps to local GPU inference

- **What** — Added `ollama-router` as an internal-only `ClusterIP` service on the OCI cluster, with a Tailscale sidecar reaching the local RTX 2080 Ti Ollama backend and Ollama Cloud free-tier fallback. The router stays deployment-agnostic; private endpoints and API keys live in app-local ignored config/Secrets.
- **Why** — Keeps public apps simple while proving the important architecture: cloud-hosted Kubernetes can use owned local GPU hardware over the private Tailnet without exposing inference services to the public internet.

### AI Lab public repo cleaned around the live demo

- **What** — Removed the older `hidden-jobs` experiment from `ai-lab`, promoted the live Kubernetes Manifest Reviewer link to the top-level README, and documented both GitOps apps under `k8s-oci-cluster/apps/`.
- **Why** — Keeps the repository focused on the strongest milestone: GitOps infrastructure, homelab-backed inference, and a running public AI/Kubernetes demo.

---

## 2026-05-12

### Local Ollama restored on GPU rigs

- **What** — Installed and validated Ollama containers on the local GPU rigs with persistent model storage and GPU passthrough. Direct API checks over Tailnet worked after access rules were adjusted.
- **Why** — Replaces the unreliable Ollama Cloud path with local inference capacity on owned hardware.

---

## 2026-05-11

### Tailscale introduced as private homelab backbone

- **What** — Connected the AI control plane, developer workstation, Raspberry Pi rig controller, and local GPU rigs through Tailscale. Tailnet reachability and remote GPU container access were validated end to end.
- **Why** — Gives the homelab a cleaner private network layer so the whole lab can be operated securely from anywhere, including while traveling, without exposing those services publicly.

### Local GPU rig fleet rebuilt and validated

- **What** — Rebuilt the local GPU rig setup around two Windows GPU machines, Tailnet Docker access, and GPU container validation from the AI control plane. Reboot behavior and remote Docker/GPU checks were tested end to end.
- **Why** — Turns the local hardware into a more reliable private inference pool instead of a single ad hoc machine.

### Rigwarden web UI added

- **What** — Added a small web UI to Rigwarden and redeployed it on the Raspberry Pi rig controller. Wake/status checks were validated against both GPU rigs.
- **Why** — Makes rig power/status control easier to inspect and operate without needing raw API calls.

---

## 2026-05-08

### Hermes updated for Kanban-based multi-agent coordination

- **What** — Updated Hermes to the latest available release and validated the dashboard, gateway, Discord command sync, and local container tooling after the upgrade.
- **Why** — Makes Hermes a peer operating surface alongside OpenClaw, with its Kanban board used to coordinate multi-agent infrastructure work instead of tracking everything through chat alone.

---

## 2026-05-04

### OpenClaw updated for Discord delivery reliability

- **What** — Updated OpenClaw to the latest minor release to address unreliable Discord final replies, where longer or tool-heavy agent runs often failed to return a final message. Follow-up checks showed explicit Discord announce delivery working across the main lanes, and normal delivery appears healthier after the upgrade.
- **Why** — Discord is the main control surface for the homelab AI stack, so completed work needs to reliably return to chat instead of disappearing into logs or background state.

### Ollama Cloud subscription discontinued

- **What** — Decided to discontinue the Ollama Cloud subscription after repeated reliability problems, especially frequent `503` errors even on the paid account.
- **Why** — Worker delegation is only useful when the model backend is dependable; an unreliable paid cloud delegate path adds supervision cost instead of reducing it.

---

## 2026-05-01

### OpenClaw operating memory refreshed

- **What** — Refreshed OpenClaw operating memory and docs to match the current worker model, thinking policy, recap automation, and long-running artifact conventions.
- **Why** — Keeps the agent control plane easier to operate as the homelab grows.

---

## 2026-04-30

### Daily recap automation fixed

- **What** — Fixed the daily recap automation after a failed run caused by an editing/tool mismatch. The job now runs in a more isolated mode with narrower tools and clearer append-only behavior.
- **Why** — Keeps daily homelab notes reliable without letting a tooling error turn a successful local update into a noisy failure report.

---

## 2026-04-29

### Hermes Discord integration hardened

- **What** — Set up Hermes with a Discord integration, then tightened the deployment so it stays limited to its intended chat scope.
- **Why** — Allows experimenting with Hermes alongside OpenClaw while reducing the chance that it responds in the wrong place.

---

## 2026-04-28

### rtx-i5: refreshed GPU worker validated

- **What** — Validated `rtx-i5` after a GPU/PSU refresh: Docker GPU runtime, Ollama, Vidscribe, local STT, and wake/shutdown control all worked after reboot and power-cycle testing.
- **Why** — Confirms the local GPU node is usable again for private inference and transcription workloads.

### Paperclip experiment removed

- **What** — Tested Paperclip as a possible agent workflow component, found it unsuitable for the current setup, and removed the experiment cleanly.
- **Why** — Keeps the homelab from accumulating experimental services that are noisy, unclear, or not ready to integrate.

---

## 2026-04-27

### Rigwarden moved to Raspberry Pi controller

- **What** — Moved Rigwarden from the HP Docker host to a Raspberry Pi colocated with the GPU rigs, then removed the old HP deployment after validating wake/status behavior.
- **Why** — Puts rig power control on a tiny always-on device near the hardware, reducing the need to keep heavier machines online.

### OpenClaw memory and procedure cleanup

- **What** — Archived historical benchmark docs, compacted long-term OpenClaw memory, and cleaned stale current-state references from active operating docs.
- **Why** — Keeps the agent operating context smaller, current, and easier to maintain as the homelab evolves.

---

## 2026-04-26

### OpenClaw: GPT-5.5-only Leah with lean internal workers

- **What** — Simplified the OpenClaw agent model so Leah is the only persistent user-facing agent, now backed by GPT-5.5 with a platform-wide "never below high" thinking policy. Specialist models remain available as internal workers rather than visible standalone agents: GLM 5.1 and MiniMax for coding, DeepSeek V4 Flash / Gemma / Kimi for research, plus GPT-5.5 workers and `opus-expert` for critique or escalation.
- **Why** — Reduces operational confusion, avoids stale visible worker sessions, and keeps the Discord control plane centered on one primary operator while preserving delegated labor for real work.

### Rigwarden: wake/status control for GPU rigs

- **What** — Built and deployed Rigwarden on the HP host as a Dockerized Wake-on-LAN and lightweight status API for `rtx-i5`. Validated stop/start power-cycle behavior after enabling WoL on the rig, then narrowed Rigwarden's service boundary to wake/status only. The service is intended to move later to a Raspberry Pi colocated with the rigs.
- **Why** — Keeps GPU rigs off by default to save electricity, while still allowing Leah/OpenClaw to bring local hardware online when a job actually needs it. The wake/status-only boundary also keeps the future Raspberry Pi controller small and low-risk.

### Vidscribe: internal video transcript service on `rtx-i5`

- **What** — Built and pushed Vidscribe as a Dockerized transcript artifact service. It accepts video URLs/IDs, prefers existing captions when available, writes structured transcript artifacts, and falls back to local faster-whisper STT on `rtx-i5` when captions are unavailable. Added HTTP artifact listing/download endpoints so other tools can consume transcripts through the API.
- **Why** — Provides a reusable video-to-transcript utility without copying transcripts into random directories or depending on manual container file access.

### Workspace and platform boundaries clarified

- **What** — Split real development work from OpenClaw's operating workspace so repositories, services, and project scripts live separately from agent memory, channel policies, mission notes, docs, helper scripts, and lightweight scratch. Also documented a Docker-first development rule for HP, rigs, Raspberry Pis, and future nodes.
- **Why** — Keeps code visible and manually operable, keeps OpenClaw's workspace focused on agent operations, and avoids unnecessary host OS mutation across the homelab.

---

## 2026-04-25

### OpenClaw: GPT-5.5 workstream lanes and long-run task cleanup

- **What** — Promoted GPT-5.5 as the main OpenClaw model, with GPT-5.4 retained only as fallback during the transition. Clarified Discord channel boundaries and retired the old "Overnight Research" procedure name in favor of simpler long-run task docs and reusable result artifacts.
- **Why** — Makes OpenClaw easier to operate across separate chat lanes while keeping long-running work auditable and resumable.

### GPU rig power-control plan

- **What** — Documented the plan to keep GPU rigs off by default and wake them only when needed, with a Raspberry Pi planned as a future colocated controller. Current routing remains cloud-first for supported Ollama workloads, with local GPU used for workloads that specifically need local hardware.
- **Why** — Reduces electricity usage while preserving access to local GPU capacity when it is useful.

---

## 2026-04-23

### rtx-i5: first private inference rig on an old desktop

- **What** — Repurposed an old i5-9400F / 32 GB / RTX 1080 desktop as `rtx-i5`, a private local-inference node. Ubuntu Server, NVIDIA driver stack, Docker with the NVIDIA container toolkit, and Ollama running in Docker with `--gpus all`. Validated headless (no display attached). LAN-only and private — no public exposure for inference endpoints.
- **Why** — Adds a GPU-backed local inference option alongside the Ollama cloud delegates, as a cost-free testbed for running models on owned hardware. Also establishes a repeatable bootstrap pattern to reuse on future private rigs.

### OpenClaw: per-lane model benchmarks for Ollama delegates

- **What** — Ran OpenClaw's benchmark pack across the Ollama cloud candidates and picked per-lane defaults instead of a single winner. Coding lane: GLM 5.1 leads with MiniMax as backup; Qwen3 Coder dropped from default coding duty for being too noisy and inefficient despite being technically capable. Research lane: a Kimi / Gemma / DeepSeek trio with role-specific assignments (DeepSeek for hard tradeoffs, Gemma for structured synthesis, Kimi for breadth and overnight runs).
- **Why** — The delegates added on 04-21 were configured by reputation, not evidence. A bounded benchmark (tiny edit, one-file fix, multi-step fix for coding; structured summary, comparative analysis, recommendation memo for research) gives a defensible routing rule and flags which models cost more supervision than they save.

---

## 2026-04-21

### opus-expert: Claude advisory system on HP

- **What** — Built `opus-expert` on the HP node — a Claude Code wrapper with a CLI (`ask-opus`) and an internal REST API. Supports one-shot queries and named advisory sessions with full thread continuity.
- **Why** — OpenClaw could not use the Claude subscription directly, so this keeps Claude available to the homelab within subscription limits. Sessions stay persistent, local, and auditable.

### OpenClaw: Ollama cloud delegates for coding, analysis, engineering

- **What** — Wired OpenClaw to Ollama's hosted models and set up three dedicated delegate agents, each with its own workspace and role brief: `qwen-coder` (Qwen3 Coder) for implementation and refactors, `gemma-analyst` (Gemma 4 31B) for tradeoff analysis and research, and `glm-engineer` (GLM 5.1) for deep debugging and systems investigation.
- **Why** — Not every task needs the primary assistant. Delegating narrow, well-scoped work to cheaper cloud models keeps costs down and frees the main thread for higher-value work. Each delegate has an explicit role and boundary so outputs stay reviewable.

---

## 2026-04-20 — HP homelab node running OpenClaw with OpenAI + Discord + SearXNG

- **What** — Added an HP Compaq Elite 8300 USDT as a dedicated Docker host for AI agents and automation. Running OpenClaw (AI agent platform) backed by an OpenAI Codex subscription, SearXNG as the web search backend, and a Discord integration for chat.
- **Why** — Dedicated node to experiment with AI agents, automate more, and keep agent workloads off other infrastructure.

---

## 2026-04-18 — Started documenting the homelab

- **What** — Created the `homelab/` directory with this changelog, an architecture overview, and a Mermaid diagram. The first step of the homelab is already in place: a Kubernetes cluster on Oracle Cloud's Always Free tier, driven by Claude Code through GitOps. From here on, every change that touches the homelab gets an entry.
- **Why** — Capturing the AI learning journey from the infrastructure side. Future-me (and anyone reading) should be able to see how the setup evolved, not just what it looks like today.
- **Links** — [`README.md`](README.md), cluster: [`../k8s-oci-cluster/`](../k8s-oci-cluster/), coding agent: [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview).
