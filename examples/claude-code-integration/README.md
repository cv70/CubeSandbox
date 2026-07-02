# Claude Code on CubeSandbox

This example runs [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview) inside a CubeSandbox template and verifies that the agent runtime, workspace state, and snapshot restore flow work end to end.

The default smoke test does not call Anthropic APIs. It checks `claude --version`, creates a small Git workspace, takes a CubeSandbox snapshot, restores from it, and reads the preserved file. Set `RUN_CLAUDE_PROMPT=1` only when you want to run a real Claude Code prompt.

## Files

- `Dockerfile` builds a Cube-ready image with Node.js, npm, Git, ripgrep, pinned `@anthropic-ai/claude-code`, and a non-root `cubesandbox` user.
- `build_template.sh` builds the image and registers it as a CubeSandbox template.
- `run_claude_code.py` starts the sandbox, injects optional Claude credentials, and verifies snapshot restore.
- `env.example` documents the local environment variables.

## Build and register the template

```bash
cd examples/claude-code-integration

# For single-node local testing, the local Docker image name can be enough.
# For multi-node clusters, set REGISTRY_IMAGE to an image visible to every Cubelet.
REGISTRY_IMAGE=<your-registry>/cubesandbox-claude-code:latest ./build_template.sh
```

The script prints a `template_id`. Put it in `.env`:

```bash
cp env.example .env
vim .env
```

Required values:

```bash
CUBE_TEMPLATE_ID=tpl-...
E2B_API_URL=http://<cube-api-host>:3000
E2B_API_KEY=e2b_000000
```

Optional Claude values:

```bash
ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

## Run the smoke test

```bash
pip install -r requirements.txt
python3 run_claude_code.py
```

Expected output includes:

```text
claude version: ...
skipping real Claude API call ...
snapshot: snap-...
restored file: hello from CubeSandbox
snapshot deleted
```

To execute a real Claude Code prompt:

```bash
RUN_CLAUDE_PROMPT=1 python3 run_claude_code.py
```

## Restricted egress

Claude Code must reach Anthropic APIs, and the template build needs npm registry access. At sandbox runtime you can restrict public egress:

```bash
STRICT_EGRESS=1 python3 run_claude_code.py
```

The script allows these domains:

- `api.anthropic.com`
- `console.anthropic.com`
- `registry.npmjs.org`
- `github.com`
- `raw.githubusercontent.com`

If you use an Anthropic-compatible gateway, also add its host to `allow_out` or set `ANTHROPIC_BASE_URL`.

## Interactive usage

For an interactive coding session, create a sandbox with the same template and attach through your orchestration layer or envd process API. Keep project files under `/workspace`; this example snapshots that path and restores it by using the snapshot ID as the next `template`. The image runs as the non-root `cubesandbox` user, and `/workspace` is writable by that user.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `claude: command not found` | Template was built from the wrong image or npm install failed | Rebuild the image and rerun `cubemastercli tpl create-from-image` |
| `Template not found` | `CUBE_TEMPLATE_ID` is wrong or belongs to another cluster | Check `cubemastercli tpl list` |
| Anthropic authentication fails | Missing or invalid `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` | Export the key in `.env` or use CubeEgress credential injection |
| Network timeout | Runtime egress policy does not allow the LLM endpoint | Add the API host to `allow_out`, or disable `STRICT_EGRESS` while debugging |
| HTTPS certificate error | CubeEgress CA is not trusted by the template | Build from Cube base image with the CA installed or configure `SSL_CERT_FILE` |
| Snapshot restore misses files | Work was written outside the sandbox filesystem or after snapshot creation | Write project state before `create_snapshot()` and keep it under `/workspace` |
