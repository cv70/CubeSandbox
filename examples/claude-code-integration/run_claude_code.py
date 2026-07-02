# Copyright (c) 2026 Tencent Inc.
# SPDX-License-Identifier: Apache-2.0

import os
import sys

from cubesandbox import Sandbox

from env_utils import load_local_dotenv


load_local_dotenv()

REQUIRED_ENV = ["CUBE_TEMPLATE_ID", "E2B_API_URL"]
missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
if missing:
    sys.stderr.write(f"Missing required environment variables: {', '.join(missing)}\n")
    sys.stderr.write("Copy env.example to .env and fill in your CubeSandbox settings.\n")
    sys.exit(2)


def run_checked(sandbox: Sandbox, command: str, *, timeout: float = 60) -> str:
    result = sandbox.commands.run(command, timeout=timeout, cwd="/workspace")
    if result.exit_code != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.exit_code}: {command}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result.stdout.strip()


env_vars = {
    name: value
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")
    if (value := os.environ.get(name))
}

network = None
allow_internet_access = True
if os.environ.get("STRICT_EGRESS") == "1":
    allow_internet_access = False
    network = {
        "allow_out": [
            "api.anthropic.com",
            "console.anthropic.com",
            "registry.npmjs.org",
            "*.npmjs.org",
            "*.npmjs.com",
            "github.com",
            "*.githubusercontent.com",
        ],
    }


with Sandbox.create(
    template=os.environ["CUBE_TEMPLATE_ID"],
    timeout=900,
    env_vars=env_vars,
    allow_internet_access=allow_internet_access,
    network=network,
) as sandbox:
    print(f"sandbox: {sandbox.sandbox_id}")
    print("claude version:", run_checked(sandbox, "claude --version"))

    run_checked(
        sandbox,
        "git config --global init.defaultBranch main && "
        "git config --global user.email cube-sandbox@example.invalid && "
        "git config --global user.name 'CubeSandbox Example' && "
        "git init . && "
        "printf 'print(\"hello from CubeSandbox\")\\n' > hello.py && "
        "git add hello.py && git commit -m 'initial sandbox state' --allow-empty",
    )

    if os.environ.get("RUN_CLAUDE_PROMPT") == "1":
        if not env_vars.get("ANTHROPIC_API_KEY") and not env_vars.get("ANTHROPIC_AUTH_TOKEN"):
            raise RuntimeError("RUN_CLAUDE_PROMPT=1 requires ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN")
        print("running Claude Code prompt")
        print(
            run_checked(
                sandbox,
                "claude -p 'Inspect hello.py and reply with one short sentence.'",
                timeout=300,
            )
        )
    else:
        print("skipping real Claude API call; set RUN_CLAUDE_PROMPT=1 to enable it")

    snapshot = sandbox.create_snapshot(name="claude-code-smoke")
    snapshot_id = snapshot.snapshot_id
    print(f"snapshot: {snapshot_id}")

with Sandbox.create(template=snapshot_id, timeout=300) as restored:
    print(f"restored sandbox: {restored.sandbox_id}")
    print("restored file:", run_checked(restored, "python3 hello.py"))

Sandbox.delete_snapshot(snapshot_id)
print("snapshot deleted")
