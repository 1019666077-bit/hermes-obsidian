# Phase 2：Hermes Agent 本机安装与 Vault 整理（需 API Key）

面向中文创始人的 Phase-2 说明：已在 box 上从本地 clone 完成 **Hermes Agent 核心可编辑安装**，技能已就位。真正跑通 LLM 整理需要你自行粘贴 API Key（本仓库不包含、也不生成任何密钥）。

## 安装结果摘要

| 项 | 状态 |
|----|------|
| `uv` / `python3` | 已有（uv 0.12.9；系统 Python 3.13；venv 使用 uv 提供的 3.11.16） |
| 安装方式 | `cd hermes-agent && uv venv .venv && uv pip install -e "."`（**核心依赖**，未装 `[all]`） |
| 版本 | Hermes Agent **v0.21.0**（`hermes --version`） |
| CLI | `/workspace/hermes-obsidian/hermes-agent/.venv/bin/hermes` |
| 技能（仓库内） | `hermes-agent/skills/note-taking/obsidian-vault-organize/` |
| 技能（用户目录） | `~/.hermes/skills/note-taking/obsidian-vault-organize/` |
| 输出 vault | `/workspace/hermes-obsidian/hermes-output-vault` |
| 说明脚本 | `run_hermes_organize.sh` |

验证命令（任选）：

```bash
source /workspace/hermes-obsidian/hermes-agent/.venv/bin/activate
hermes --version
hermes --help
hermes chat --help
hermes skills list   # 应能看到 obsidian-vault-organize
```

---

## 1. 在 `~/.hermes/.env` 中设置模型 API Key

编辑（已有占位文件）：

```bash
nano ~/.hermes/.env
# 或: vim ~/.hermes/.env
```

任选一种提供商，**取消注释并粘贴真实 Key**（不要提交到 git）。默认模型可用 `hermes model` 交互选择，或在调用时用 `--provider` / `-m`。

### OpenRouter（多模型聚合，推荐起步）

```bash
OPENROUTER_API_KEY=sk-or-v1-你的密钥
```

然后例如：

```bash
hermes model
# 或一次性：
hermes chat -Q --oneshot --provider openrouter -m deepseek/deepseek-chat -q "你好"
```

### DeepSeek（官方直连）

```bash
DEEPSEEK_API_KEY=sk-你的密钥
# 可选覆盖（一般不必）：
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

```bash
hermes chat -Q --oneshot --provider deepseek -m deepseek-chat -q "你好"
```

### OpenAI 兼容端点（含自建 / 部分第三方）

```bash
OPENAI_API_KEY=sk-你的密钥
OPENAI_BASE_URL=https://api.deepseek.com/v1
# 或其它兼容网关，例如本地 vLLM / LM Studio 等
```

并在 `~/.hermes/config.yaml`（可用 `hermes config` / 复制 `cli-config.yaml.example`）里设：

```yaml
model:
  provider: custom   # 或 openai-api / auto（视端点而定）
  default: deepseek-chat
  base_url: "https://api.deepseek.com/v1"
```

也可用交互向导：`hermes setup` 或 `hermes model`。

> **重要：** 不要把真实 Key 写进本仓库的任何文件；只放在 `~/.hermes/.env`。

---

## 2. 跑一次 vault-organize（Key 配好之后）

推荐用仓库内脚本（会设置 `OBSIDIAN_VAULT_PATH` 并调用非交互 oneshot）：

```bash
cd /workspace/hermes-obsidian
./run_hermes_organize.sh
```

等价手工命令（核心是 **`hermes chat -Q --oneshot`**）：

```bash
source /workspace/hermes-obsidian/hermes-agent/.venv/bin/activate
export OBSIDIAN_VAULT_PATH=/workspace/hermes-obsidian/hermes-output-vault
mkdir -p "$OBSIDIAN_VAULT_PATH"

hermes chat -Q --oneshot --yolo \
  -s obsidian-vault-organize \
  -q "请使用技能 obsidian-vault-organize：把输入目录 /workspace/hermes-obsidian/fixtures/messy-input 整理成 Obsidian vault，输出目录必须是 ${OBSIDIAN_VAULT_PATH}。遵循技能中的目录结构与规则；不要编造事实。"
```

说明：

- `-Q` / `--quiet`：适合脚本；非 TTY 下也会自动 oneshot。
- `--oneshot`：答完即退出（批处理）。
- `-s obsidian-vault-organize`：预加载技能。
- `--yolo`：跳过危险命令审批（仅在你信任的本地整理任务中使用）。
- 交互模式：直接 `hermes`，再 `/skills` 或说「整理 fixtures/messy-input」。

完成后用 Obsidian「Open folder as vault」打开 `hermes-output-vault/`。

---

## 3. Fallback：继续用 `organize_vault.py`（无需 API）

若暂无 Key、额度不足、或 Hermes 调用失败，仍用 Phase 1 确定性脚本：

```bash
cd /workspace/hermes-obsidian
python3 organize_vault.py \
  --input  /workspace/hermes-obsidian/fixtures/messy-input \
  --output /workspace/hermes-obsidian/output-vault
```

`run_hermes_organize.sh` 在检测到无可用凭证时也会提示走这条路径。

---

## 4. 已知限制 / Blocker

1. **无 API Key 时无法真正跑通 LLM 整理** — 已故意不写入任何密钥；需你在 `~/.hermes/.env` 粘贴后重试。
2. **未安装 `[all]` extras** — 核心安装已足够 `hermes` CLI + 本地技能；消息网关 / 语音等可选功能需另装对应 extras。
3. **网络依赖** — 首次 `uv pip install` 已完成；后续模型推理需要出站访问对应 API。
4. Hermes 批处理路径以官方 `hermes chat -q ... --oneshot -Q` 为准，而非虚构的 `hermes organize` 子命令。

---

## 用户下一步（复制粘贴）

```bash
# 1) 写入 Key（示例：OpenRouter；换成你的真实值）
echo 'OPENROUTER_API_KEY=sk-or-v1-PASTE_HERE' >> ~/.hermes/.env

# 2) 激活并跑整理
source /workspace/hermes-obsidian/hermes-agent/.venv/bin/activate
cd /workspace/hermes-obsidian && ./run_hermes_organize.sh
```

或 DeepSeek：

```bash
echo 'DEEPSEEK_API_KEY=sk-PASTE_HERE' >> ~/.hermes/.env
source /workspace/hermes-obsidian/hermes-agent/.venv/bin/activate
hermes chat -Q --oneshot --provider deepseek -m deepseek-chat -q "ping"
```
