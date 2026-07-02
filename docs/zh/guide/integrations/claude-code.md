---
title: Claude Code 集成指南
author: CubeSandbox contributors
date: 2026-07-02
tags:
  - integration
  - claude-code
  - coding-agent
lang: zh-CN
---

# Claude Code 集成指南

本文说明如何把 Claude Code 运行在 CubeSandbox 中，让终端型编码 Agent 的文件编辑、命令执行、依赖安装和测试运行都发生在隔离、可复现的沙箱内。同一模式也适用于外部 Agent 编排系统：编排系统按需创建 CubeSandbox 沙箱，再让 Claude Code 通过沙箱 process API 检查或修改文件。

可运行示例位于 `examples/claude-code-integration/`。

## 集成对象与版本

- 集成对象：Claude Code，Anthropic 的终端编码 Agent。
- 安装方式：`npm install -g @anthropic-ai/claude-code`。
- 运行环境：Node.js、npm、Git、ripgrep，以及在 `49983` 端口运行 envd 的 Cube base image。
- CubeSandbox API：通过 `cubesandbox` 使用 E2B 兼容的 Python SDK 路径。

Claude Code 是交互式 CLI。示例默认采用非交互验证：检查 `claude --version`，准备 Git 工作区，创建沙箱快照，从快照恢复，并在设置 `RUN_CLAUDE_PROMPT=1` 时可选执行真实 Claude prompt。

## 前置条件

- 已部署 CubeSandbox 集群，并配置好 `cubemastercli`。
- 构建机器可以使用 Docker。
- 多节点集群需要一个所有 Cubelet 都能访问的镜像仓库。
- 示例 runner 需要 Python 3.10+。
- 可选 Anthropic 凭证：
  - 直连 API 使用 `ANTHROPIC_API_KEY`。
  - 如果你的 Claude Code 配置使用 token 鉴权，可使用 `ANTHROPIC_AUTH_TOKEN`。
  - 通过 Anthropic 兼容网关访问时，设置 `ANTHROPIC_BASE_URL`。

## 构建 Claude Code 模板

示例镜像会把 Claude Code 安装到 Cube base image 中：

```bash
cd examples/claude-code-integration
REGISTRY_IMAGE=<your-registry>/cubesandbox-claude-code:latest ./build_template.sh
```

单节点本地部署时，如果 Cubelet 能看到本地 Docker 镜像，可以不设置 `REGISTRY_IMAGE`。多节点部署时，请先推送镜像到所有节点可拉取的仓库。

脚本会用以下配置注册模板：

```bash
cubemastercli tpl create-from-image \
  --image <image> \
  --writable-layer-size 4G \
  --expose-port 49983 \
  --probe 49983 \
  --probe-path /health
```

记录输出的 template ID。

## 配置凭证与 Cube 访问

复制环境变量模板：

```bash
cp examples/claude-code-integration/env.example examples/claude-code-integration/.env
```

设置必填 CubeSandbox 参数：

```bash
CUBE_TEMPLATE_ID=tpl-...
E2B_API_URL=http://<cube-api-host>:3000
E2B_API_KEY=e2b_000000
```

如需真实调用 Claude Code，增加：

```bash
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

敏感配置有两种推荐注入方式：

- **SDK 环境变量注入**：通过 `Sandbox.create(env_vars=...)` 传入凭证。适合本地示例，配置简单，但密钥会对沙箱内进程可见。
- **CubeEgress 凭证注入**：配置 CubeEgress 规则，在访问 Anthropic 或你的网关时注入出站 `Authorization` header。这样原始密钥不会出现在沙箱文件系统或进程环境中，适合共享或多租户部署。

## 运行示例

```bash
cd examples/claude-code-integration
pip install -r requirements.txt
python3 run_claude_code.py
```

预期输出：

```text
claude version: ...
skipping real Claude API call ...
snapshot: snap-...
restored file: hello from CubeSandbox
snapshot deleted
```

执行真实 prompt：

```bash
RUN_CLAUDE_PROMPT=1 python3 run_claude_code.py
```

真实 prompt 路径需要 `ANTHROPIC_API_KEY` 或 `ANTHROPIC_AUTH_TOKEN`。

## 网络与出口策略

Claude Code 运行时需要出站 HTTPS 访问 Anthropic 或你配置的网关。模板构建阶段也需要访问 npm registry，除非你使用内部镜像源。

开放式开发沙箱可使用默认配置：

```python
Sandbox.create(template=template_id, allow_internet_access=True)
```

如需限制运行时出口，可在示例中设置 `STRICT_EGRESS=1`。脚本会使用 `allow_internet_access=False` 和域名白名单创建沙箱：

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

如果使用私有 LLM 网关，请放通该网关域名，替代或补充 `api.anthropic.com`。如果需要请求级过滤、审计或 header 注入，请按 Security Proxy 文档配置 CubeEgress `rules`。

## 会话保持与状态持久化

使用 CubeSandbox 快照保存 Claude Code 状态：

1. 在 `/workspace` 中运行 Claude Code。
2. 将源码、`.git`、任务笔记和生成产物保存在 `/workspace`。
3. 在合适检查点调用 `sandbox.create_snapshot()`。
4. 后续用 `Sandbox.create(template=snapshot_id)` 恢复。

示例使用如下流程：

```python
snapshot = sandbox.create_snapshot(name="claude-code-smoke")
snapshot_id = snapshot.snapshot_id

with Sandbox.create(template=snapshot_id) as restored:
    restored.commands.run("python3 /workspace/hello.py")
```

如果只是短时间挂起，可以使用 `sandbox.pause()` 和 `Sandbox.connect(sandbox_id)` 保留沙箱会话。若状态需要长时间存在，或需要克隆到多个后续沙箱，应使用快照。

## 典型使用场景

- **隔离运行编码 Agent**：把 Claude Code 本身放进 CubeSandbox，让文件修改、依赖安装、测试运行和生成产物都留在沙箱内。
- **执行 Agent 生成代码**：Claude Code 或其他编排器运行在沙箱外，只把不可信命令放到 CubeSandbox 中执行并回收结果。
- **长任务断点续跑**：在依赖安装、仓库 checkout、测试基线通过后创建快照，中断后从最后一个可用快照恢复。
- **并行探索**：从准备好的仓库创建一个快照，再克隆多个沙箱测试不同 Claude Code prompt 或分支。

## 注意事项

- Claude Code CLI 参数可能随版本变化。如果重视可复现性，请在模板中固定 `@anthropic-ai/claude-code` 版本。
- 交互式终端体验取决于你的编排层。示例使用非交互 process 调用，便于在 CI 和本地部署中验证。
- 域名白名单依赖 DNS 学习。使用域名 `allow_out` 时，应设置 `allow_internet_access=False` 或提供 deny-all fallback，避免未匹配公网流量默认放行。
- 以环境变量注入的密钥会对沙箱内进程可见。共享基础设施建议使用 CubeEgress 注入。

## 常见问题

| 现象 | 常见原因 | 处理方式 |
| --- | --- | --- |
| `claude: command not found` | 模板未基于 Claude Code 镜像构建，或 npm 安装失败 | 重新构建镜像并重新创建模板 |
| `Template not found` | `CUBE_TEMPLATE_ID` 错误，或连接了错误集群 | 检查 `cubemastercli tpl list` |
| 鉴权失败 | 缺少或错误的 Anthropic 凭证 | 设置 `ANTHROPIC_API_KEY`、`ANTHROPIC_AUTH_TOKEN`，或配置 CubeEgress 注入 |
| 网络超时 | 出站策略阻止了 LLM 端点 | 将网关域名加入 `allow_out`，或调试时关闭严格出口策略 |
| HTTPS 证书错误 | 模板不信任 CubeEgress CA | 基于带 CA 的 Cube base image 构建，或配置正确 CA 路径 |
| 镜像拉取失败 | Cubelet 无法拉取模板镜像 | 推送到所有节点可访问的镜像仓库并重新创建模板 |
| 快照恢复后缺少状态 | 文件在快照之后写入，或写到了沙箱文件系统外 | 在 `create_snapshot()` 前写入状态，并把项目文件放在 `/workspace` |

## 参考

- 示例：`examples/claude-code-integration/`
- CubeSandbox 模板：`docs/guide/templates.md`
- CubeSandbox 网络策略：`docs/guide/network-policy.md`
- CubeSandbox Security Proxy：`docs/guide/security-proxy.md`
- Claude Code 文档：<https://docs.anthropic.com/en/docs/claude-code/overview>
