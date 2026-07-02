# syntax=docker/dockerfile:1.7
#
# Cube-ready image for running Claude Code inside a sandbox.
#
# Build:
#   docker build -t cubesandbox-claude-code:latest examples/claude-code-integration

ARG CUBE_BASE_IMAGE=ghcr.io/tencentcloud/cubesandbox-base:2026.16
FROM ${CUBE_BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG NODE_MAJOR=20

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        gnupg \
        jq \
        openssh-client \
        python3 \
        ripgrep \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && printf 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_%s.x nodistro main\n' "${NODE_MAJOR}" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && node --version \
    && claude --version \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspace /root/.claude \
    && printf '%s\n' \
        '# CubeSandbox Claude Code workspace' \
        '' \
        'This workspace is intentionally created inside the sandbox image.' \
    > /workspace/README.md

WORKDIR /workspace

EXPOSE 49983

CMD ["sleep", "infinity"]
