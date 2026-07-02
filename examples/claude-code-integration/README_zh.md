# 在 CubeSandbox 中运行 Claude Code

本示例在 CubeSandbox 模板内运行 [Claude Code](https://docs.anthropic.com/en/docs/claude-code/overview)，并验证 Agent 运行环境、工作区状态和快照恢复链路。

默认 smoke test 不会调用 Anthropic API。它只检查 `claude --version`、创建一个小型 Git 工作区、创建 CubeSandbox 快照、从快照恢复并读取保留下来的文件。只有在需要真实调用 Claude Code 时，才设置 `RUN_CLAUDE_PROMPT=1`。

## 文件说明

- `Dockerfile` 构建包含 Node.js、npm、Git、ripgrep、固定版本 `@anthropic-ai/claude-code` 和非 root `cubesandbox` 用户的 Cube 镜像。
- `build_template.sh` 构建镜像并注册为 CubeSandbox 模板。
- `run_claude_code.py` 启动沙箱、可选注入 Claude 凭证，并验证快照恢复。
- `env.example` 记录本地环境变量。

## 构建并注册模板

```bash
cd examples/claude-code-integration

# 单机本地测试可以直接使用本地 Docker 镜像名。
# 多节点集群请设置 REGISTRY_IMAGE，确保每个 Cubelet 都能拉取该镜像。
REGISTRY_IMAGE=<your-registry>/cubesandbox-claude-code:latest ./build_template.sh
```

脚本会输出 `template_id`。写入 `.env`：

```bash
cp env.example .env
vim .env
```

必填配置：

```bash
CUBE_TEMPLATE_ID=tpl-...
E2B_API_URL=http://<cube-api-host>:3000
E2B_API_KEY=e2b_000000
```

可选 Claude 配置：

```bash
ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_BASE_URL=https://api.anthropic.com
```

## 运行 smoke test

```bash
pip install -r requirements.txt
python3 run_claude_code.py
```

预期输出包含：

```text
claude version: ...
skipping real Claude API call ...
snapshot: snap-...
restored file: hello from CubeSandbox
snapshot deleted
```

执行真实 Claude Code prompt：

```bash
RUN_CLAUDE_PROMPT=1 python3 run_claude_code.py
```

## 限制出站访问

Claude Code 运行时需要访问 Anthropic API，模板构建阶段需要访问 npm registry。沙箱运行时可以开启严格出站策略：

```bash
STRICT_EGRESS=1 python3 run_claude_code.py
```

脚本默认放通这些域名：

- `api.anthropic.com`
- `console.anthropic.com`
- `registry.npmjs.org`
- `github.com`
- `raw.githubusercontent.com`

如果使用 Anthropic 兼容网关，请把网关域名加入 `allow_out`，或设置 `ANTHROPIC_BASE_URL`。

## 交互式使用

交互式编码会话可以使用相同模板创建沙箱，并通过你的编排层或 envd process API 进入。建议把项目文件放在 `/workspace`；本示例会快照该路径，并把快照 ID 作为下一次 `template` 来恢复状态。镜像默认以非 root `cubesandbox` 用户运行，且 `/workspace` 对该用户可写。

## 常见问题

| 现象 | 常见原因 | 处理方式 |
| --- | --- | --- |
| `claude: command not found` | 模板不是从该镜像构建，或 npm 安装失败 | 重新构建镜像并重新执行 `cubemastercli tpl create-from-image` |
| `Template not found` | `CUBE_TEMPLATE_ID` 错误，或属于其他集群 | 通过 `cubemastercli tpl list` 核对 |
| Anthropic 鉴权失败 | 缺少或错误的 `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN` | 在 `.env` 导出密钥，或使用 CubeEgress 凭证注入 |
| 网络超时 | 运行时出站策略没有放通 LLM 端点 | 把 API 域名加入 `allow_out`，调试阶段也可关闭 `STRICT_EGRESS` |
| HTTPS 证书错误 | 模板没有信任 CubeEgress CA | 基于带 CA 的 Cube base image 构建，或配置 `SSL_CERT_FILE` |
| 快照恢复后缺少文件 | 状态写在沙箱文件系统外，或写入发生在快照之后 | 在 `create_snapshot()` 前写入状态，并放在 `/workspace` |
