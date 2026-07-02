---
title: Claude Code Integration Guide
author: CubeSandbox contributors
date: 2026-07-02
tags:
  - integration
  - claude-code
  - coding-agent
lang: en-US
---

# Claude Code Integration Guide

This guide shows how to run Claude Code inside CubeSandbox so terminal-based coding work happens in an isolated, reproducible sandbox. The same pattern also works when an external agent orchestrator creates CubeSandbox sandboxes on demand and asks Claude Code to inspect or modify files through the sandbox process API.

The runnable example is under `examples/claude-code-integration/`.

## Integration Target and Version

- Target: Claude Code, Anthropic's terminal coding agent.
- Tested installation path: `npm install -g @anthropic-ai/claude-code`.
- Runtime: Node.js, npm, Git, ripgrep, and a Cube base image with envd on port `49983`.
- CubeSandbox API: E2B-compatible Python SDK path via `cubesandbox`.

Claude Code is an interactive CLI. The example keeps the default validation non-interactive: it verifies `claude --version`, prepares a Git workspace, snapshots the sandbox, restores from that snapshot, and optionally runs a real Claude prompt when `RUN_CLAUDE_PROMPT=1` is set.

## Prerequisites

- A running CubeSandbox cluster and `cubemastercli` configured for it.
- Docker access on the build machine.
- A registry reachable by every Cubelet when running a multi-node cluster.
- Python 3.10+ for the example runner.
- Optional Anthropic credential:
  - `ANTHROPIC_API_KEY` for direct API access.
  - `ANTHROPIC_AUTH_TOKEN` if your Claude Code setup uses token-based auth.
  - `ANTHROPIC_BASE_URL` if traffic goes through an Anthropic-compatible gateway.

## Build the Claude Code Template

The example image installs Claude Code into a Cube base image:

```bash
cd examples/claude-code-integration
REGISTRY_IMAGE=<your-registry>/cubesandbox-claude-code:latest ./build_template.sh
```

For single-node local deployments, `REGISTRY_IMAGE` can be omitted if the Cubelet can see the local Docker image. For multi-node deployments, push the image to a registry first so every node can pull it.

The script registers the image with:

```bash
cubemastercli tpl create-from-image \
  --image <image> \
  --writable-layer-size 4G \
  --expose-port 49983 \
  --probe 49983 \
  --probe-path /health
```

Record the printed template ID.

## Configure Credentials and Cube Access

Copy the environment template:

```bash
cp examples/claude-code-integration/env.example examples/claude-code-integration/.env
```

Set the required CubeSandbox values:

```bash
CUBE_TEMPLATE_ID=tpl-...
E2B_API_URL=http://<cube-api-host>:3000
E2B_API_KEY=e2b_000000
```

For direct Claude Code calls, add:

```bash
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

There are two safe ways to handle sensitive values:

- **SDK env injection**: pass credentials through `Sandbox.create(env_vars=...)`. This is simple and works well for local examples, but the secret is visible to processes inside the sandbox.
- **CubeEgress credential injection**: configure a CubeEgress rule that injects the outbound `Authorization` header for Anthropic or your gateway. This keeps the raw secret outside the sandbox filesystem and process environment. Use this for shared or multi-tenant deployments.

## Run the Example

```bash
cd examples/claude-code-integration
pip install -r requirements.txt
python3 run_claude_code.py
```

Expected output:

```text
claude version: ...
skipping real Claude API call ...
snapshot: snap-...
restored file: hello from CubeSandbox
snapshot deleted
```

To run a real prompt:

```bash
RUN_CLAUDE_PROMPT=1 python3 run_claude_code.py
```

The prompt path requires `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`.

## Network and Egress Policy

Claude Code needs outbound HTTPS access to Anthropic or your configured gateway. The template build also needs npm registry access unless you mirror the package internally.

For open development sandboxes, keep the default:

```python
Sandbox.create(template=template_id, allow_internet_access=True)
```

For restricted runtime egress, set `STRICT_EGRESS=1` in the example. It creates the sandbox with `allow_internet_access=False` and a domain allowlist:

```python
Sandbox.create(
    template=template_id,
    allow_internet_access=False,
    network={
        "allow_out": [
            "api.anthropic.com",
            "console.anthropic.com",
            "registry.npmjs.org",
            "*.npmjs.org",
            "*.npmjs.com",
            "github.com",
            "*.githubusercontent.com",
        ],
    },
)
```

If you use a private LLM gateway, allow that gateway host instead of, or in addition to, `api.anthropic.com`. For request-level filtering, auditing, or header injection, add CubeEgress `rules` as described in the Security Proxy guide.

## Session Retention and State Persistence

Use CubeSandbox snapshots to preserve Claude Code state across sessions:

1. Run Claude Code in `/workspace`.
2. Keep source code, `.git`, task notes, and generated artifacts under `/workspace`.
3. Call `sandbox.create_snapshot()` after a useful checkpoint.
4. Resume later with `Sandbox.create(template=snapshot_id)`.

The example uses this flow:

```python
snapshot = sandbox.create_snapshot(name="claude-code-smoke")
snapshot_id = snapshot.snapshot_id

with Sandbox.create(template=snapshot_id) as restored:
    restored.commands.run("python3 /workspace/hello.py")
```

For shorter gaps, `sandbox.pause()` and `Sandbox.connect(sandbox_id)` can keep a sandbox session around without turning it into a reusable template. Use snapshots when the state must outlive the sandbox or be cloned into multiple follow-up sandboxes.

## Typical Usage Patterns

- **Isolated coding agent**: run Claude Code itself inside CubeSandbox so file edits, package installs, test runs, and generated artifacts stay contained.
- **Agent-generated code execution**: keep Claude Code or another orchestrator outside CubeSandbox, then create sandboxes only for executing untrusted commands and collecting results.
- **Long-running tasks with checkpoints**: snapshot after dependency installation, after repository checkout, or after a passing test baseline; resume from the last good snapshot after interruption.
- **Parallel exploration**: create one snapshot from a prepared repository and clone several sandboxes from it to test multiple Claude Code prompts or branches.

## Caveats

- Claude Code may change CLI flags over time. Keep the template rebuildable and pin `@anthropic-ai/claude-code` to a known version if reproducibility matters.
- Interactive terminal UX depends on your orchestrator. The example uses non-interactive process calls because they are easier to validate in CI and local deployments.
- Domain allowlists rely on DNS learning. When using `allow_out` with domains, keep `allow_internet_access=False` or include a deny-all fallback so unmatched public traffic is not allowed by default.
- Secrets injected as environment variables are visible inside the sandbox. Prefer CubeEgress injection for shared infrastructure.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `claude: command not found` | The template was not built from the Claude Code image, or npm install failed | Rebuild the image and recreate the template |
| `Template not found` | Wrong `CUBE_TEMPLATE_ID` or wrong cluster | Check `cubemastercli tpl list` |
| Authentication failure | Missing or invalid Anthropic credential | Set `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or configure CubeEgress injection |
| Network timeout | Egress policy blocks the LLM endpoint | Add the gateway domain to `allow_out`, or disable strict egress while debugging |
| HTTPS certificate error | CubeEgress CA is not trusted by the template | Build from a Cube base image with the CA installed or configure the proper CA path |
| Image pull failure | Cubelet cannot pull the template image | Push to a registry reachable by all nodes and recreate the template |
| Snapshot restore misses state | Files were written after snapshot creation or outside the sandbox filesystem | Write state before `create_snapshot()` and keep project files under `/workspace` |

## References

- Example: `examples/claude-code-integration/`
- CubeSandbox templates: `docs/guide/templates.md`
- CubeSandbox network policy: `docs/guide/network-policy.md`
- CubeSandbox Security Proxy: `docs/guide/security-proxy.md`
- Claude Code documentation: <https://docs.anthropic.com/en/docs/claude-code/overview>
